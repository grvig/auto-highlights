"""Config loading and validation.

Reads config.toml (git-ignored, real values) which is shaped like the committed
config.template.toml. Kept dependency-free so layer 1 can import it without
dragging in the recorder stack.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from highlights.steam.locate import find_cs2_root

CONFIG_FILENAME = "config.toml"
TEMPLATE_FILENAME = "config.template.toml"

# Relative to cs2_root — used to verify the path points at a real install
# rather than one of Steam's empty leftover stub folders.
CS2_EXE_RELATIVE = Path("game/bin/win64/cs2.exe")


class ConfigError(Exception):
    """Raised when the config is missing, malformed, or points somewhere wrong."""


@dataclass(frozen=True)
class ObsConfig:
    host: str
    port: int
    password: str


@dataclass(frozen=True)
class ClipConfig:
    pre_roll_seconds: float
    post_roll_seconds: float


# Recording backends: HLAE renders frame-perfect footage with synced audio;
# "window" captures the game window in real time when HLAE is unavailable.
RECORDERS = ("hlae", "window")


@dataclass(frozen=True)
class RecordingConfig:
    recorder: str = "hlae"
    # HLAE install folder (holding HLAE.exe). None means the bundled copy.
    hlae_path: Path | None = None
    # Render size. 4:3 by default, stretched to 16:9 on export, the way
    # stretched-res players see the game.
    width: int = 1440
    height: int = 1080
    framerate: int = 60
    # Export shape for finished reels; see highlights.stitcher.aspect.
    aspect: str = "stretched"


@dataclass(frozen=True)
class Config:
    # None when it was neither configured nor found automatically.
    cs2_root: Path | None
    output_dir: Path
    clips_dir: Path
    obs: ObsConfig
    clips: ClipConfig
    # Either a bare command found on PATH ("ffmpeg") or an absolute path to the
    # executable. Kept as a string, not a resolved Path, so a bare command is
    # not accidentally rewritten relative to the config file.
    ffmpeg_path: str = "ffmpeg"
    # True when cs2_root came from auto-detection rather than config.toml.
    cs2_root_detected: bool = False
    # Parsed-demo cache. Defaults to a sibling of clips_dir so it lands on the
    # same drive the user picked for media rather than the system drive.
    cache_dir: Path | None = None
    recording: RecordingConfig = RecordingConfig()

    @property
    def resolved_cache_dir(self) -> Path:
        return self.cache_dir or self.clips_dir.parent / "cache"

    @property
    def cs2_executable(self) -> Path | None:
        return None if self.cs2_root is None else self.cs2_root / CS2_EXE_RELATIVE

    def verify_cs2_install(self) -> None:
        """Check cs2_root actually holds the game. Recording-only concern.

        The engine never calls this — parsing works with no game installed.
        """
        if self.cs2_executable is None:
            raise ConfigError(
                "Could not find CS2 automatically. Set cs2_root in [paths] of "
                f"{CONFIG_FILENAME} to the folder containing game/bin/win64/cs2.exe."
            )
        if not self.cs2_executable.is_file():
            raise ConfigError(
                f"No cs2.exe under cs2_root: {self.cs2_root}\n"
                f"Expected: {self.cs2_executable}\n"
                "Steam can leave an empty stub folder with the same name in "
                "another library — point cs2_root at the one with the executable."
            )

    def validate(self) -> None:
        """Check the config values themselves make sense.

        Value-level only — it does not touch the filesystem or the network, so
        it is safe to call before any game or OBS is running. Raises
        ConfigError listing every problem at once, rather than failing on the
        first one deep inside a run.
        """
        problems: list[str] = []

        if not (1 <= self.obs.port <= 65535):
            problems.append(f"obs.port {self.obs.port} is not in 1-65535")
        if not self.obs.password:
            problems.append("obs.password is empty")
        if self.clips.pre_roll_seconds < 0:
            problems.append("clips.pre_roll_seconds is negative")
        if self.clips.post_roll_seconds < 0:
            problems.append("clips.post_roll_seconds is negative")
        if not self.ffmpeg_path.strip():
            problems.append("paths.ffmpeg is empty")
        rec = self.recording
        if rec.recorder not in RECORDERS:
            problems.append(f"recording.recorder must be one of {', '.join(RECORDERS)}")
        if rec.width < 320 or rec.height < 240:
            problems.append(f"recording size {rec.width}x{rec.height} is too small")
        if not (24 <= rec.framerate <= 240):
            problems.append(f"recording.framerate {rec.framerate} is not in 24-240")

        if problems:
            raise ConfigError(
                "Invalid config:\n" + "\n".join(f"  - {p}" for p in problems)
            )


def _require(table: dict, key: str, section: str) -> object:
    if key not in table:
        raise ConfigError(f"Missing '{key}' in [{section}] of {CONFIG_FILENAME}")
    return table[key]


def load_config(
    path: Path | str | None = None,
    locate_cs2: Callable[[], Path | None] = find_cs2_root,
) -> Config:
    """Load and validate config, defaulting to config.toml at the repo root.

    cs2_root is optional: when it is left out, the CS2 install is found through
    Steam's library list instead.
    """
    config_path = Path(path) if path else repo_root() / CONFIG_FILENAME

    if not config_path.is_file():
        raise ConfigError(
            f"No config at {config_path}\n"
            f"Copy {TEMPLATE_FILENAME} to {CONFIG_FILENAME} and fill in your values."
        )

    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    paths = raw.get("paths", {})
    obs = raw.get("obs", {})
    clips = raw.get("clips", {})
    recording = raw.get("recording", {})

    base = config_path.parent
    configured_cs2 = paths.get("cs2_root")
    cs2_root = Path(str(configured_cs2)) if configured_cs2 else locate_cs2()
    return Config(
        cs2_root=cs2_root,
        output_dir=_resolve(base, str(paths.get("output_dir", "./output"))),
        clips_dir=_resolve(base, str(paths.get("clips_dir", "./clips"))),
        obs=ObsConfig(
            host=str(obs.get("host", "localhost")),
            port=int(obs.get("port", 4455)),
            password=str(_require(obs, "password", "obs")),
        ),
        clips=ClipConfig(
            pre_roll_seconds=float(clips.get("pre_roll_seconds", 3.0)),
            post_roll_seconds=float(clips.get("post_roll_seconds", 2.0)),
        ),
        ffmpeg_path=str(paths.get("ffmpeg", "ffmpeg")),
        cs2_root_detected=not configured_cs2 and cs2_root is not None,
        cache_dir=_resolve(base, str(paths["cache_dir"])) if paths.get("cache_dir") else None,
        recording=RecordingConfig(
            recorder=str(recording.get("recorder", "hlae")),
            hlae_path=_resolve(base, str(paths["hlae"])) if paths.get("hlae") else None,
            width=int(recording.get("width", 1440)),
            height=int(recording.get("height", 1080)),
            framerate=int(recording.get("framerate", 60)),
            aspect=str(recording.get("aspect", "stretched")),
        ),
    )


def _resolve(base: Path, value: str) -> Path:
    """Resolve relative paths against the config file, not the working dir."""
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (base / candidate).resolve()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
