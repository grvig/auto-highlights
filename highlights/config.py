"""Config loading and validation.

Reads config.toml (git-ignored, real values) which is shaped like the committed
config.template.toml. Kept dependency-free so layer 1 can import it without
dragging in the recorder stack.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class Config:
    cs2_root: Path
    output_dir: Path
    clips_dir: Path
    obs: ObsConfig
    clips: ClipConfig
    # Either a bare command found on PATH ("ffmpeg") or an absolute path to the
    # executable. Kept as a string, not a resolved Path, so a bare command is
    # not accidentally rewritten relative to the config file.
    ffmpeg_path: str = "ffmpeg"

    @property
    def cs2_executable(self) -> Path:
        return self.cs2_root / CS2_EXE_RELATIVE

    def verify_cs2_install(self) -> None:
        """Check cs2_root actually holds the game. Recording-only concern.

        The engine never calls this — parsing works with no game installed.
        """
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

        if problems:
            raise ConfigError(
                "Invalid config:\n" + "\n".join(f"  - {p}" for p in problems)
            )


def _require(table: dict, key: str, section: str) -> object:
    if key not in table:
        raise ConfigError(f"Missing '{key}' in [{section}] of {CONFIG_FILENAME}")
    return table[key]


def load_config(path: Path | str | None = None) -> Config:
    """Load and validate config, defaulting to config.toml at the repo root."""
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

    base = config_path.parent
    return Config(
        cs2_root=Path(str(_require(paths, "cs2_root", "paths"))),
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
    )


def _resolve(base: Path, value: str) -> Path:
    """Resolve relative paths against the config file, not the working dir."""
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (base / candidate).resolve()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
