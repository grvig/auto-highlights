"""The desktop window: the web interface in a native window, backed by AppApi.

pywebview shows the built interface (highlights/app/web, made by `npm run
build` in ui/) in Edge WebView2, which ships with Windows 11. The page calls
Python through `window.pywebview.api`; only the methods of Bridge are
reachable from it, so the page cannot wander into the rest of the app.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from highlights import __version__
from highlights.app.api import AppApi
from highlights.appdirs import app_data_dir

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"
ICON = Path(__file__).parent / "icon.ico"
TITLE = "auto-highlights"
SIZE = (1180, 780)
MIN_SIZE = (900, 620)
BACKGROUND = "#101216"  # the page's own background, so opening never flashes white
DEMO_FILES = ("CS2 demos (*.dem;*.dem.zst;*.dem.gz)", "All files (*.*)")
MUSIC_FILES = ("Music (*.mp3;*.wav;*.flac;*.ogg;*.m4a)", "All files (*.*)")


class WindowError(RuntimeError):
    """Raised when the window cannot be shown (no pywebview, no built UI)."""


def index_path(web_dir: Path = WEB_DIR) -> Path:
    index = Path(web_dir) / "index.html"
    if not index.is_file():
        raise WindowError(
            f"The app's interface is not built ({index} is missing). "
            "Run `npm install` and `npm run build` in the ui folder."
        )
    return index


class Bridge:
    """What the page may call. Every method returns JSON-friendly data."""

    def __init__(self, api: AppApi) -> None:
        self._api = api
        self._window: Any = None

    def _attach(self, window: Any) -> None:  # underscore: hidden from the page
        self._window = window

    # --- passed straight through -------------------------------------------

    def version(self) -> dict:
        return {"version": __version__}

    def check(self) -> dict:
        return self._api.check()

    def setup(self) -> dict:
        return self._api.setup()

    def settings(self) -> dict:
        return self._api.settings()

    def save_settings(self, changes: dict) -> dict:
        return self._api.save_settings(changes)

    def find_demos(self) -> dict:
        return self._api.find_demos()

    def analyze(self, paths: list[str]) -> dict:
        return self._api.analyze(paths)

    def plan(self, paths: list[str], steamid: str, options: dict | None = None) -> dict:
        return self._api.plan(paths, steamid, options)

    def render(self, paths: list[str], steamid: str, options: dict | None = None) -> dict:
        return self._api.render(paths, steamid, options)

    def job(self, job_id: str) -> dict:
        return self._api.job(job_id)

    def cancel(self, job_id: str) -> dict:
        return self._api.cancel(job_id)

    def reels(self) -> dict:
        return self._api.reels()

    def show_in_folder(self, path: str) -> dict:
        return self._api.show_in_folder(path)

    def thumbnail(self, path: str) -> dict:
        return self._api.thumbnail(path)

    def play(self, path: str) -> dict:
        return self._api.play(path)

    def open_logs(self) -> dict:
        return self._api.open_logs()

    # --- native pickers ------------------------------------------------------

    def pick_demos(self) -> dict:
        """Let the player browse for demos that were not found automatically."""
        return {"paths": self._dialog("OPEN", allow_multiple=True, file_types=DEMO_FILES)}

    def pick_music(self) -> dict:
        chosen = self._dialog("OPEN", file_types=MUSIC_FILES)
        return {"path": chosen[0] if chosen else None}

    def pick_folder(self) -> dict:
        chosen = self._dialog("FOLDER")
        return {"path": chosen[0] if chosen else None}

    def _dialog(self, kind: str, **options: Any) -> list[str]:
        if self._window is None:
            return []
        from webview import FileDialog  # noqa: PLC0415 - only when a window exists

        chosen = self._window.create_file_dialog(getattr(FileDialog, kind), **options)
        if isinstance(chosen, str):  # some platforms answer a single pick as a string
            chosen = [chosen]
        return [str(path) for path in chosen or ()]


def set_window_icon(window: Any, icon: Path = ICON) -> bool:
    """Put the app icon on the window's title bar and taskbar button.

    The packaged exe already carries it; run from source the window would
    otherwise show Python's. Best effort: a missing icon is no reason to fail.
    """
    try:
        importlib.import_module("clr")  # pythonnet, which pywebview uses on Windows
        from System import Action  # noqa: PLC0415 - exists once clr is loaded
        from System.Drawing import Icon  # noqa: PLC0415

        form = window.native
        form.Invoke(Action(lambda: setattr(form, "Icon", Icon(str(icon)))))
        return True
    except Exception as error:  # noqa: BLE001 - any failure just keeps the default icon
        logger.debug("Could not set the window icon: %s", error)
        return False


def storage_dir() -> Path:
    """The window's own WebView2 profile, beside the app's other data rather
    than in pywebview's shared default folder."""
    return app_data_dir() / "webview"


def open_window(api: AppApi | None = None, webview: Any = None, web_dir: Path = WEB_DIR,
                dev_url: str | None = None, debug: bool = False) -> None:
    """Show the window and block until it is closed.

    dev_url points the window at a running `npm run dev` server instead of
    the built files, for working on the interface.
    """
    if webview is None:
        try:
            import webview  # noqa: PLC0415 - only the window needs it
        except ImportError as error:
            raise WindowError("pywebview is not installed: pip install pywebview") from error
    url = dev_url or str(index_path(web_dir))
    bridge = Bridge(api or AppApi())
    window = webview.create_window(
        TITLE, url, js_api=bridge, width=SIZE[0], height=SIZE[1], min_size=MIN_SIZE,
        background_color=BACKGROUND, text_select=False,
    )
    bridge._attach(window)
    window.events.shown += lambda: set_window_icon(window)
    logger.info("Opening the app window (%s)", url)
    webview.start(debug=debug, private_mode=False, storage_path=str(storage_dir()))
