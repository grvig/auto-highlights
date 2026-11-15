"""CS2 console command vocabulary.

Every string this project sends to the game lives here. When a CS2 update
breaks recording — and it will — this is the first and usually only file to
change. Nothing here performs I/O; these are pure builders so they can be
asserted on in tests without the game running.

Verified against a live CS2 build on 2026-11-11. Commands CS2 does not know
print nothing at all, so a silently ignored command shows up in the log as a
missing confirmation rather than an error.
"""

from __future__ import annotations

# A SteamID64 is an account ID plus this constant. Spectator commands address
# players by the account ID, not the 64-bit form the demo carries.
STEAM_ID64_BASE = 76561197960265728

# spec_mode values as CS2 numbers them (ObserverMode_t): 2 is first person
# ("in eye"), 3 the chase camera, 4 a free roaming camera. CS:GO used 4 for
# in-eye, and sending that in CS2 parks a free camera wherever it happens to
# be, which a live recording on 2026-11-15 caught.
SPEC_MODE_FIRST_PERSON = 2
SPEC_MODE_THIRD_PERSON = 3


class CommandError(ValueError):
    """Raised when a command cannot be built from the given arguments."""


def account_id_from_steamid64(steamid: str | int) -> int:
    """Convert a SteamID64 into the account ID spectator commands expect."""
    try:
        value = int(steamid)
    except (TypeError, ValueError) as error:
        raise CommandError(f"Not a numeric SteamID64: {steamid!r}") from error
    if value <= STEAM_ID64_BASE:
        raise CommandError(f"SteamID64 out of range: {value}")
    return value - STEAM_ID64_BASE


# Folder under game/csgo that playdemo reads from. Absolute paths are not
# reliable, so demos are staged here first.
REPLAYS_FOLDER = "replays"

# Console settings for clean footage: no build stamp, telemetry, x-ray or
# target names, only the kill feed, and sound kept while unfocused.
MOVIE_SETUP = (
    "sv_cheats 1",
    "cl_draw_only_deathnotices 1",
    "r_show_build_info 0",
    "cl_hud_telemetry_frametime_show 0",
    "cl_hud_telemetry_ping_show 0",
    "cl_hud_telemetry_net_misdelivery_show 0",
    "cl_trueview_show_status 0",
    "spec_show_xray 0",
    "hud_showtargetid 0",
    "snd_mute_losefocus 0",
)


def play_demo(demo_name: str) -> str:
    """Load and start playing a demo staged in the replays folder."""
    stem = str(demo_name).strip()
    if stem.lower().endswith(".dem"):
        stem = stem[:-4]
    if not stem:
        raise CommandError("Demo name is empty")
    if any(c in stem for c in '"/\\;'):
        raise CommandError(f"Demo name must be a bare file name: {demo_name!r}")
    return f"playdemo {REPLAYS_FOLDER}/{stem}"


def goto_tick(tick: int) -> str:
    """Seek playback to an absolute tick."""
    if tick < 0:
        raise CommandError(f"Tick cannot be negative: {tick}")
    return f"demo_gototick {int(tick)}"


def pause() -> str:
    return "demo_pause"


def resume() -> str:
    return "demo_resume"


def set_timescale(scale: float) -> str:
    """Set playback speed. 1.0 is real time; lower is slow motion."""
    if scale <= 0:
        raise CommandError(f"Timescale must be positive: {scale}")
    return f"demo_timescale {scale:g}"


def step_ticks(ticks: int) -> str:
    """Play exactly this many ticks in real time, then pause.

    CS2 answers with "Demo paused at engine time E, demo tick T" when done.
    """
    if ticks <= 0:
        raise CommandError(f"Tick count must be positive: {ticks}")
    return f"demo_step_tick {int(ticks)}"


def spectate_player(name: str) -> str:
    """Lock the camera to one player by in-game name.

    CS2 has no spectate-by-account command, so names are used, quoted so
    spaces and non-Latin names survive.
    """
    clean = str(name).replace('"', "").strip()
    if not clean:
        raise CommandError("Player name is empty")
    return f'spec_player "{clean}"'


def toggle_demo_ui() -> str:
    """Show or hide the demo playback bar; it reappears on every load."""
    return "demoui"


def spectator_mode(mode: int = SPEC_MODE_FIRST_PERSON) -> str:
    return f"spec_mode {int(mode)}"


def disconnect() -> str:
    """Stop playback and leave the demo."""
    return "disconnect"


def hide_hud(hidden: bool = True) -> str:
    """Toggle the spectator HUD, for cleaner footage."""
    return f"cl_draw_only_deathnotices {1 if hidden else 0}"
