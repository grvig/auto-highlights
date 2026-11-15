"""The fallback recording backend: real-time capture of the CS2 window.

Shares the HLAE backend's flow (demo loading, seeking, re-takes) and swaps
only the take: ffmpeg films the window while the demo steps in real time,
then the played stretch is found by freeze detection and cut out.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from highlights.recorder import window_capture as wc
from highlights.recorder.base import ClipRequest
from highlights.recorder.cs2_controller import Cs2Error
from highlights.recorder.hlae_backend import LEAD_TICKS, HlaeRecorder

RAW_NAME = "raw.mkv"

Popen = Callable[..., "subprocess.Popen[bytes]"]
Probe = Callable[[Sequence[str]], str]


def _probe(args: Sequence[str]) -> str:
    return subprocess.run(list(args), capture_output=True, text=True).stderr


class WindowRecorder(HlaeRecorder):
    """Records clips by capturing the CS2 window while the demo plays."""

    name = "window"

    def __init__(
        self,
        *args,
        audio_device: str | None = None,
        popen: Popen = subprocess.Popen,
        probe: Probe = _probe,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.audio_device = audio_device
        self._popen = popen
        self._probe = probe

    def _record_take(self, request: ClipRequest) -> tuple[Path, int | None]:
        start = max(1, request.start_tick - LEAD_TICKS)
        if not self.cs2.seek_to(start):
            raise Cs2Error(f"CS2 never confirmed the seek to tick {start}")
        self._sleep(0.4)
        self.cs2.spectate(request.spectate_name)
        self._sleep(0.5)
        take_dir = self._take_dir(request)
        take_dir.mkdir(parents=True)
        capture = self._popen(
            wc.capture_command(take_dir / RAW_NAME, self.framerate, self.audio_device, self.ffmpeg),
            stdin=subprocess.PIPE,
        )
        try:
            self._sleep(1.2)  # gfxcapture needs a moment before its first frame
            landed = self.cs2.play_ticks(request.end_tick - start)
            self._sleep(0.2)
        finally:
            capture.communicate(b"q", timeout=30)
        return take_dir, landed

    def _finish(self, request: ClipRequest, take_dir: Path) -> None:
        tickrate = self.cs2.tickrate
        start = max(1, request.start_tick - LEAD_TICKS)
        raw = take_dir / RAW_NAME
        played = (request.end_tick - start) / tickrate
        log = self._probe(wc.freeze_probe_command(raw, self.ffmpeg))
        begin = wc.motion_start(log, played) + (request.start_tick - start) / tickrate
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(wc.trim_command(
            raw,
            request.output_path,
            begin,
            (request.end_tick - request.start_tick) / tickrate,
            self.framerate,
            self.ffmpeg,
            speed=request.speed,
            has_audio=self.audio_device is not None,
            ramps=self._ramp_seconds(request),
            ramp_speed=request.window.ramp_speed,
        ))
