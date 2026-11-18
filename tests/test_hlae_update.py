"""Tests for installing HLAE releases, with GitHub faked."""

import io
import json
import zipfile

import pytest

from highlights.recorder.hlae_release import HlaeRelease, ReleaseError, installed_version
from highlights.recorder.hlae_update import ensure_current, install_release, latest_release


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


GOOD = make_zip({"HLAE.exe": b"exe", "x64/AfxHookSource2.dll": b"dll"})


def fake_github(version="2.193.0", archive=GOOD):
    name = f"hlae_{version.replace('.', '_')}.zip"
    listing = {"tag_name": f"v{version}", "assets": [
        {"name": name, "size": len(archive), "browser_download_url": f"https://dl/{name}"}]}

    def fetch(url):
        return json.dumps(listing).encode() if "api.github.com" in url else archive
    return fetch


def test_fresh_install_writes_the_version(tmp_path):
    label, changed = ensure_current(tmp_path / "hlae", fake_github())
    assert (label, changed) == ("2.193.0", True)
    assert (tmp_path / "hlae" / "HLAE.exe").read_bytes() == b"exe"
    assert installed_version(tmp_path / "hlae") == (2, 193, 0)
    assert not list(tmp_path.glob("*.zip"))  # download cleaned up


def test_current_install_is_left_alone(tmp_path):
    ensure_current(tmp_path / "hlae", fake_github())
    assert ensure_current(tmp_path / "hlae", fake_github()) == ("2.193.0", False)


def test_update_keeps_the_previous_copy(tmp_path):
    ensure_current(tmp_path / "hlae", fake_github("2.192.0"))
    ensure_current(tmp_path / "hlae", fake_github("2.193.0"))
    assert installed_version(tmp_path / "hlae") == (2, 193, 0)
    assert installed_version(tmp_path / "hlae.previous") == (2, 192, 0)


def test_broken_archive_leaves_the_working_copy(tmp_path):
    ensure_current(tmp_path / "hlae", fake_github("2.192.0"))
    with pytest.raises(ReleaseError, match="no HLAE.exe"):
        ensure_current(tmp_path / "hlae", fake_github("2.193.0", make_zip({"readme.txt": b"x"})))
    assert installed_version(tmp_path / "hlae") == (2, 192, 0)


def test_truncated_download_is_rejected(tmp_path):
    release = HlaeRelease((2, 193, 0), "https://dl/x.zip", len(GOOD) + 10)
    with pytest.raises(ReleaseError, match="expected"):
        install_release(release, tmp_path / "hlae", lambda url: GOOD)


def test_archive_paths_cannot_escape(tmp_path):
    evil = make_zip({"HLAE.exe": b"exe", "../outside.txt": b"x"})
    with pytest.raises(ReleaseError, match="Unsafe"):
        ensure_current(tmp_path / "hlae", fake_github(archive=evil))
    assert not (tmp_path / "outside.txt").exists()


def test_network_failure_is_explained():
    def offline(url):
        raise OSError("no route")
    with pytest.raises(ReleaseError, match="Could not check"):
        latest_release(offline)
