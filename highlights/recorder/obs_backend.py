"""The real recorder backend: CS2 playback captured by OBS.

Ties the two halves together for one clip at a time — seek and spectate in the
game, roll OBS around the window, then move OBS's output to the clip's proper
filename. Failures are returned as failed clips rather than raised, so one bad
moment does not abandon the rest of the plan.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from highlights.recorder.base import ClipRequest, RecordedClip
from highlights.recorder.cs2_controller import Cs2Controller, Cs2Error
from highlights.recorder.obs_client import ObsClient, ObsError

logger = logging.getLogger(__name__)


class ObsRecorder:
    """Records clips by driving CS2 while OBS captures the screen."""

    name = "obs"

    def __init__(
        self,
        cs2: Cs2Controller,
        obs: ObsClient,
        output_dir: Path | str,
        launch_cs2: bool = False,
    ) -> None:
        self.cs2 = cs2
        self.obs = obs
        self.output_dir = Path(output_dir)
        self.launch_cs2 = launch_cs2
        self._loaded_demo: Path | None = None
        self._spectating: str | None = None

    def open(self) -> None:
        """Connect to CS2 and OBS and prepare the output folder."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.launch_cs2:
            self.cs2.launch()
        logger.info("[%s] attaching to CS2", self.name)
        self.cs2.attach()
        logger.info("[%s] connecting to OBS", self.name)
        self.obs.connect()
        self.obs.set_record_directory(self.output_dir)

    def close(self) -> None:
        """Tear both sides down, tolerating either already being gone."""
        try:
            self.obs.close()
        except Exception as error:  # never mask the original failure
            logger.debug("[%s] OBS close failed: %s", self.name, error)
        try:
            self.cs2.quit()
        except Exception as error:
            logger.debug("[%s] CS2 quit failed: %s", self.name, error)

    def _ensure_demo_loaded(self, demo_path: Path) -> None:
        if self._loaded_demo == demo_path:
            return
        self.cs2.load_demo(demo_path)
        self._loaded_demo = demo_path
        # A fresh demo drops any camera lock.
        self._spectating = None

    def _ensure_spectating(self, steamid: str) -> None:
        if self._spectating == steamid:
            return
        self.cs2.spectate(steamid)
        self._spectating = steamid

    def _place_output(self, written: Path | None, request: ClipRequest) -> Path:
        """Move OBS's output to the clip's intended filename."""
        target = request.output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if written is None or not written.exists():
            logger.warning(
                "[%s] OBS reported no usable file for #%03d", self.name, request.index
            )
            return target
        if written.resolve() == target.resolve():
            return target
        logger.info("[%s] moving %s -> %s", self.name, written.name, target.name)
        shutil.move(str(written), str(target))
        return target

    def record_clip(self, request: ClipRequest) -> RecordedClip:
        """Record one moment, returning a failed clip rather than raising."""
        logger.info("[%s] recording %s", self.name, request)
        try:
            self._ensure_demo_loaded(request.demo_path)
            self._ensure_spectating(request.spectate_steamid)
            self.cs2.seek_to(request.start_tick)

            self.obs.start_recording()
            try:
                self.cs2.play_window(
                    request.start_tick, request.end_tick, timescale=request.speed
                )
            finally:
                # Always stop the recording, even if playback threw, so OBS is
                # not left rolling into the next clip.
                written = self.obs.stop_recording()

            output = self._place_output(written, request)
        except (Cs2Error, ObsError, OSError) as error:
            logger.error("[%s] clip #%03d failed: %s", self.name, request.index, error)
            return RecordedClip(
                request=request,
                output_path=request.output_path,
                succeeded=False,
                error=str(error),
            )

        logger.info("[%s] clip #%03d done -> %s", self.name, request.index, output)
        return RecordedClip(request=request, output_path=output, succeeded=True)
