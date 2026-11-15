"""Assembling recorded clips into the finished, edited reel.

Order of work: caption and trim each clip, render title and outro cards in the
clips' format, join everything with crossfades, then lay the music under it.
Beat sync decides the trims, so cuts land on the music before anything is
rendered.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from highlights.editor import beats as beat_tools
from highlights.editor.cards import card_command, outro_lines, title_lines
from highlights.editor.effects import effect_filters
from highlights.editor.captions import caption_filter, caption_for, replay_caption
from highlights.editor.music import check_music, music_command
from highlights.editor.probe import MediaInfo, probe
from highlights.editor.transitions import DEFAULT_TRANSITION, join_command, transition_seconds
from highlights.recorder.base import RecordedClip

logger = logging.getLogger(__name__)

TITLE_SECONDS = 2.5
OUTRO_SECONDS = 2.5
# Seconds of post-roll beat sync may trim off the end of a clip.
TRIMMABLE_SECONDS = 0.6

Runner = Callable[[Sequence[str]], object]
Prober = Callable[[Path], MediaInfo]


def _run(args: Sequence[str]) -> object:
    return subprocess.run(list(args), check=True, capture_output=True)


@dataclass(frozen=True)
class EditOptions:
    player_name: str
    captions: bool = True
    cards: bool = True
    transition: str = DEFAULT_TRANSITION
    music: Path | None = None
    # Map name for each demo, keyed by the demo path a clip came from.
    maps: dict[Path, str] = field(default_factory=dict)
    # The player's kills across the whole reel, for the outro card.
    kills_shown: int | None = None
    # Zoom in on headshots and flash on every kill.
    punch_ins: bool = False
    flashes: bool = False


class ReelBuilder:
    def __init__(
        self,
        options: EditOptions,
        work_dir: Path,
        ffmpeg: str = "ffmpeg",
        runner: Runner = _run,
        prober: Prober | None = None,
        beat_finder: Callable[[Path], list[float]] | None = None,
    ) -> None:
        self.options = options
        self.work_dir = Path(work_dir)
        self.ffmpeg = ffmpeg
        self._run = runner
        self._probe = prober or (lambda path: probe(path, ffmpeg))
        self._beats = beat_finder or (
            lambda path: beat_tools.beat_times(beat_tools.load_samples(path, ffmpeg))
        )

    def build(self, clips: list[RecordedClip], output: Path) -> Path:
        usable = [c for c in clips if c.succeeded and c.output_path.is_file()]
        if not usable:
            raise ValueError("No recorded clips to edit")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        infos = [self._probe(c.output_path) for c in usable]
        width, height = infos[0].width or 1440, infos[0].height or 1080
        self._size = (width, height, round(infos[0].fps or 60))
        fps = round(infos[0].fps or 60)

        durations = [info.duration for info in infos]
        fade = transition_seconds(durations) if self.options.transition != "cut" else 0.0
        if self.options.music:
            check_music(self.options.music)
            lead_in = (TITLE_SECONDS - fade) if self.options.cards else 0.0
            durations = beat_tools.snap_durations(
                durations, self._beats(self.options.music), fade,
                [TRIMMABLE_SECONDS] * len(durations), lead_in,
            )

        parts = [self._prepare(n, c, d) for n, (c, d) in enumerate(zip(usable, durations), 1)]
        if self.options.cards:
            maps = sorted({m for m in self.options.maps.values() if m})
            parts.insert(0, self._card("title", title_lines(self.options.player_name, maps, len(
                {c.request.index for c in usable})), TITLE_SECONDS, width, height, fps))
            parts.append(self._card("outro", outro_lines(self.options.player_name, self.options.kills_shown),
                                    OUTRO_SECONDS, width, height, fps))
            durations = [TITLE_SECONDS, *durations, OUTRO_SECONDS]

        joined = self.work_dir / "joined.mp4" if self.options.music else output
        self._run(join_command(parts, durations, joined, width, height, fps,
                               self.options.transition if fade else "fade", self.ffmpeg, fade))
        if self.options.music:
            total = sum(durations) - fade * (len(durations) - 1)
            self._run(music_command(joined, self.options.music, output, total, ffmpeg=self.ffmpeg))
        logger.info("Edited reel written to %s", output)
        return output

    def _prepare(self, number: int, clip: RecordedClip, duration: float) -> Path:
        """Caption the first window of each moment and apply its beat trim."""
        request = clip.request
        window = request.window
        width, height, fps = getattr(self, "_size", (1440, 1080, 60))
        filters = effect_filters(
            [window.screen_seconds(t) for t in window.headshot_ticks] if self.options.punch_ins else [],
            [window.screen_seconds(t) for t in window.kill_ticks] if self.options.flashes else [],
            width, height, fps,
        )
        caption = None
        if self.options.captions and request.camera_name and request.window.pov_steamid:
            caption = replay_caption(request.camera_name)
        elif self.options.captions and request.part == 1:
            caption = caption_for(request.moment, self.options.player_name,
                                  self.options.maps.get(Path(request.demo_path)))
        if caption:
            filters.append(caption_filter(caption, self.work_dir / f"captions_{number:03d}"))
        prepared = self.work_dir / f"part_{number:03d}.mp4"
        args = [self.ffmpeg, "-y", "-loglevel", "error", "-i", str(clip.output_path),
                "-t", f"{duration:.3f}"]
        if filters:
            args += ["-vf", ",".join(filters)]
        args += ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", str(prepared)]
        self._run(args)
        return prepared

    def _card(self, name, lines, duration, width, height, fps) -> Path:
        path = self.work_dir / f"{name}.mp4"
        self._run(card_command(lines, path, self.work_dir, duration, width, height, fps, self.ffmpeg))
        return path
