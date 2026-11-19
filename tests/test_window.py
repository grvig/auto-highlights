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


class FakeWebview:
    def __init__(self):
        self.created, self.started = None, None

    def create_window(self, title, url, **kwargs):
        self.created = (title, url, kwargs)
        return "window"

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
        "version", "check", "setup", "settings", "save_settings", "find_demos", "analyze",
        "plan", "render", "job", "cancel", "reels", "show_in_folder",
    }
