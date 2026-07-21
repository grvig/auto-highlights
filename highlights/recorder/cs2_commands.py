"""CS2 console command vocabulary.

Every string this project sends to the game lives here. When a CS2 update
breaks recording — and it will — this is the first and usually only file to
change. Nothing here performs I/O; these are pure builders so they can be
asserted on in tests without the game running.

Verification status: these follow Source/CS2 demo-playback conventions but
have not been confirmed against a live CS2 build. The console transport logs
every command it sends, so a rejected command shows up plainly in the log.
"""

from __future__ import annotations

# A SteamID64 is an account ID plus this constant. Spectator commands address
# players by the account ID, not the 64-bit form the demo carries.
STEAM_ID64_BASE = 76561197960265728

# spec_mode values. 4 is first person ("in eye"), which is what a POV
# highlight reel wants; 5 is the chase/third-person camera.
SPEC_MODE_FIRST_PERSON = 4
SPEC_MODE_THIRD_PERSON = 5


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


def play_demo(demo_path: str) -> str:
    """Load and start playing a demo.

    The path is quoted because demos routinely sit under paths with spaces,
    such as "Counter-Strike Global Offensive".
    """
    if not str(demo_path).strip():
        raise CommandError("Demo path is empty")
    return f'playdemo "{demo_path}"'


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


def spectate_player(steamid: str | int) -> str:
    """Lock the camera to one player by SteamID64."""
    return f"spec_player_by_accountid {account_id_from_steamid64(steamid)}"


def spectator_mode(mode: int = SPEC_MODE_FIRST_PERSON) -> str:
    return f"spec_mode {int(mode)}"


def disconnect() -> str:
    """Stop playback and leave the demo."""
    return "disconnect"


def hide_hud(hidden: bool = True) -> str:
    """Toggle the spectator HUD, for cleaner footage."""
    return f"cl_draw_only_deathnotices {1 if hidden else 0}"
