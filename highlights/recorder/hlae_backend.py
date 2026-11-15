"""The recording backend: CS2 under HLAE, rendering every frame to ffmpeg.

Per clip: seek a little before the window, point the camera, arm an HLAE
take, step exactly the window's ticks, end the take, then trim the lead-in
off and mux the game audio. A take that stops far from where it should is
recorded again, because a dropped seek would otherwise film the wrong round.
"""

from __future__ import annotations

import logging
import math
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from highlights.recorder import mirv
from highlights.recorder.base import ClipRequest, RecordedClip
from highlights.recorder.cs2_controller import Cs2Controller, Cs2Error

logger = logging.getLogger(__name__)

# Ticks recorded before each window so the first real frame is fully drawn.
LEAD_TICKS = 32
# How far the step may stop from the window's end and still count.
LANDING_TOLERANCE_TICKS = 10
TAKES_PER_CLIP = 2
# Upper bound on rendering rate for slowed footage; beyond it frames are
# repeated instead (render time grows with every extra frame).
MAX_RENDER_RATE = 240

Runner = Callable[[Sequence[str]], object]


def _run(args: Sequence[str]) -> object:
    return subprocess.run(list(args), check=True, capture_output=True)


class HlaeRecorder:
    """Records clips by rendering CS2 demo playback through HLAE."""

    name = "hlae"

    def __init__(
        self,
        cs2: Cs2Controller,
        output_dir: Path | str,
        launch_args: Sequence[str] | None = None,
        framerate: int = 60,
        ffmpeg: str = "ffmpeg",
        runner: Runner = _run,
        sleeper: Callable[[float], None] = time.sleep,
        keep_takes: bool = False,
        restore_commands: Sequence[str] = (),
    ) -> None:
        self.cs2 = cs2
        self.output_dir = Path(output_dir)
        self.launch_args = list(launch_args) if launch_args else None
        self.framerate = framerate
        self.ffmpeg = ffmpeg
        self._run = runner
        self._sleep = sleeper
        # Raw takes hold the full lead-in and a wav; once a clip is finished
        # they are only kept when debugging.
        self.keep_takes = keep_takes
        # Put the player's own settings back before the game saves them.
        self.restore_commands = list(restore_commands)
        self._loaded: Path | None = None
        # Takes started in this game session; numbers each take's preset.
        self._takes = 0

    def open(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.launch_args:
            self.cs2.launch(args=self.launch_args)
            self.cs2.attach_when_ready()
            self._sleep(8.0)  # the menu keeps loading after the console opens
        else:
            self.cs2.attach()

    def close(self) -> None:
        try:
            self.cs2.console.send_all(mirv.stop_commands())
            self.cs2.console.send_all(self.restore_commands)
        except Exception as error:  # never mask the original failure
            logger.debug("[%s] stopping streams failed: %s", self.name, error)
        self.cs2.quit()

    def record_clip(self, request: ClipRequest) -> RecordedClip:
        logger.info("[%s] recording %s", self.name, request)
        try:
            self._ensure_demo(request.demo_path)
            for take in range(1, TAKES_PER_CLIP + 1):
                take_dir, landed = self._record_take(request)
                if landed is not None and abs(landed - request.end_tick) <= LANDING_TOLERANCE_TICKS:
                    break
                logger.warning("[%s] take %d stopped at %s, wanted %d",
                               self.name, take, landed, request.end_tick)
            self._finish(request, take_dir)
        except (Cs2Error, OSError, subprocess.CalledProcessError) as error:
            logger.error("[%s] %s failed: %s", self.name, request.label, error)
            return RecordedClip(request, request.output_path, succeeded=False, error=str(error))
        if not self.keep_takes:
            self._remove_takes(request)
        return RecordedClip(request, request.output_path, succeeded=True)

    def _remove_takes(self, request: ClipRequest) -> None:
        """Delete this clip's raw take folders (only ones this app created)."""
        takes = self.output_dir / "takes"
        stem = request.output_path.stem
        for folder in takes.glob(f"{stem}*"):
            if folder.is_dir() and (folder.name == stem or folder.name.startswith(f"{stem}_")):
                shutil.rmtree(folder, ignore_errors=True)

    def _ensure_demo(self, demo_path: Path) -> None:
        if self._loaded == Path(demo_path):
            return
        self.cs2.load_demo(self.cs2.stage_demo(demo_path))
        self._loaded = Path(demo_path)

    def render_rate(self, request: ClipRequest) -> int:
        """Frames per second to render. Slowed footage needs more frames to
        stay smooth, so ramped clips render at framerate / ramp speed."""
        window = request.window
        slowest = window.speed * (window.ramp_speed if window.ramps else 1.0)
        if slowest >= 1.0:
            return self.framerate
        return min(MAX_RENDER_RATE, math.ceil(self.framerate / slowest))

    def _ramp_seconds(self, request: ClipRequest) -> tuple[tuple[float, float], ...]:
        tickrate = self.cs2.tickrate
        return tuple(
            ((start - request.start_tick) / tickrate, (end - request.start_tick) / tickrate)
            for start, end in request.window.ramps
        )

    def _take_dir(self, request: ClipRequest) -> Path:
        base = self.output_dir / "takes" / request.output_path.stem
        candidate, n = base, 1
        while candidate.exists():  # HLAE numbers takes inside, so start fresh
            n += 1
            candidate = base.with_name(f"{base.name}_{n}")
        return candidate

    def _record_take(self, request: ClipRequest) -> tuple[Path, int | None]:
        start = max(1, request.start_tick - LEAD_TICKS)
        if not self.cs2.seek_to(start):
            raise Cs2Error(f"CS2 never confirmed the seek to tick {start}")
        self._sleep(0.4)
        self.cs2.spectate(request.spectate_name)
        self._sleep(0.5)
        take_dir = self._take_dir(request)
        take_dir.mkdir(parents=True)
        self._takes += 1
        self.cs2.console.send_all(mirv.start_commands(take_dir, self._takes, self.render_rate(request)))
        refusals = [line for line in self.cs2.console.read_lines(0.5) if "AFXERROR" in line]
        if refusals:
            self.cs2.console.send_all(mirv.stop_commands())
            raise Cs2Error(f"HLAE refused the take: {refusals[0]}")
        try:
            landed = self.cs2.play_ticks(request.end_tick - start)
        finally:
            self.cs2.console.send_all(mirv.stop_commands())
        self._sleep(2.0)  # let HLAE's ffmpeg flush and close the file
        return take_dir, landed

    def _finish(self, request: ClipRequest, take_dir: Path) -> None:
        tickrate = self.cs2.tickrate
        lead = request.start_tick - max(1, request.start_tick - LEAD_TICKS)
        video = take_dir / mirv.VIDEO_NAME
        if not video.is_file() or video.stat().st_size == 0:
            raise Cs2Error(f"HLAE wrote no video for this take ({video})")
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(mirv.finish_command(
            take_dir,
            request.output_path,
            skip_seconds=lead / tickrate,
            duration_seconds=(request.end_tick - request.start_tick) / tickrate,
            speed=request.speed,
            ffmpeg=self.ffmpeg,
            ramps=self._ramp_seconds(request),
            ramp_speed=request.window.ramp_speed,
        ))
        logger.info("[%s] %s -> %s", self.name, request.label, request.output_path)
