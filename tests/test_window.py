"""Tests for the desktop window, with pywebview faked (no window opens)."""

import pytest

from highlights.app.window import Bridge, WindowError, index_path, open_window


class FakeApi:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, args))
            return {"called": name}
        return call


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class FakeWindow(str):
    def __new__(cls):
        window = super().__new__(cls, "window")
        window.events = type("Events", (), {"shown": FakeEvent()})()
        return window


class FakeWebview:
    def __init__(self):
        self.created, self.started = None, None

    def create_window(self, title, url, **kwargs):
        self.created = (title, url, kwargs)
        self.window = FakeWindow()
        return self.window

    def start(self, **kwargs):
        self.started = kwargs


def built(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html>")
    return tmp_path


def test_the_window_shows_the_built_interface_through_the_bridge(tmp_path):
    webview = FakeWebview()
    open_window(FakeApi(), webview, web_dir=built(tmp_path))
    title, url, kwargs = webview.created
    assert title == "auto-highlights" and url.endswith("index.html")
    assert isinstance(kwargs["js_api"], Bridge)
    assert kwargs["js_api"]._window == "window"
    assert webview.started is not None


def test_a_dev_server_can_stand_in_for_the_built_files(tmp_path):
    webview = FakeWebview()
    open_window(FakeApi(), webview, web_dir=tmp_path / "missing", dev_url="http://localhost:5173")
    assert webview.created[1] == "http://localhost:5173"


def test_a_missing_build_is_explained(tmp_path):
    with pytest.raises(WindowError, match="npm run build"):
        index_path(tmp_path)


def test_the_bridge_passes_calls_through_to_the_api():
    api = FakeApi()
    bridge = Bridge(api)
    assert bridge.plan(["a.dem"], "76561", {"seconds": 60}) == {"called": "plan"}
    assert api.calls == [("plan", (["a.dem"], "76561", {"seconds": 60}))]
    assert bridge.version()["version"]


def test_the_page_only_sees_the_bridge_methods():
    # pywebview hides names starting with an underscore from the page.
    public = {name for name in dir(Bridge(FakeApi())) if not name.startswith("_")}
    assert public == {
        "version", "check_update", "open_releases", "check", "setup", "settings", "save_settings", "find_demos", "analyze", "describe_demo",
        "plan", "render", "job", "cancel", "reels", "show_in_folder", "thumbnail", "play", "open_logs",
        "pick_demos", "pick_music", "pick_folder",
    }


class FakeDialogWindow:
    def __init__(self, answer):
        self.answer, self.asked = answer, []

    def create_file_dialog(self, kind, **options):
        self.asked.append((kind, options))
        return self.answer


def test_demos_are_picked_with_a_dem_filter():
    from webview import FileDialog

    bridge = Bridge(FakeApi())
    window = FakeDialogWindow(("C:/a.dem", "C:/b.dem"))
    bridge._attach(window)
    assert bridge.pick_demos() == {"paths": ["C:/a.dem", "C:/b.dem"]}
    kind, options = window.asked[0]
    assert kind == FileDialog.OPEN and options["allow_multiple"]
    assert "*.dem;" in options["file_types"][0] and "*.dem.zst" in options["file_types"][0]


def test_cancelled_or_windowless_pickers_answer_nothing():
    bridge = Bridge(FakeApi())
    assert bridge.pick_music() == {"path": None}  # no window yet
    bridge._attach(FakeDialogWindow(None))
    assert bridge.pick_folder() == {"path": None}
    assert bridge.pick_demos() == {"paths": []}


def test_a_single_pick_given_as_text_still_works():
    bridge = Bridge(FakeApi())
    bridge._attach(FakeDialogWindow("D:/music/track.mp3"))
    assert bridge.pick_music() == {"path": "D:/music/track.mp3"}


def test_the_window_keeps_its_browser_profile_in_the_app_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    webview = FakeWebview()
    (tmp_path / "web").mkdir()
    open_window(FakeApi(), webview, web_dir=built(tmp_path / "web"))
    assert webview.started["storage_path"] == str(tmp_path / "auto-highlights" / "webview")


def test_the_app_icon_is_set_once_the_window_shows(tmp_path, monkeypatch):
    from highlights.app import window as window_module

    set_on = []
    monkeypatch.setattr(window_module, "set_window_icon", lambda w: set_on.append(w))
    webview = FakeWebview()
    open_window(FakeApi(), webview, web_dir=built(tmp_path))
    for handler in webview.window.events.shown.handlers:
        handler()
    assert set_on == [webview.window]
    assert window_module.ICON.is_file()


def test_a_window_without_a_native_form_keeps_its_icon_quietly():
    from highlights.app.window import set_window_icon

    assert set_window_icon(object()) is False


def test_the_running_mutex_can_be_held():
    import sys

    from highlights.app.window import hold_running_mutex

    handle = hold_running_mutex("auto-highlights-test-mutex")
    assert (handle is not None) == (sys.platform == "win32")
