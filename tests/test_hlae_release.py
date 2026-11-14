"""Tests for reading HLAE releases and versions."""

import pytest

from highlights.recorder.hlae_release import (
    VERSION_FILE,
    HlaeRelease,
    ReleaseError,
    installed_version,
    needs_update,
    parse_version,
    release_from_listing,
)

# Shape of GitHub's answer for advancedfx v2.193.0 (2026-11-07).
LISTING = {
    "tag_name": "v2.193.0",
    "assets": [
        {"name": "hlae_2_193_0.zip.asc", "size": 235, "browser_download_url": "https://x/a.asc"},
        {"name": "HLAE_Setup.exe", "size": 8303808, "browser_download_url": "https://x/setup.exe"},
        {"name": "hlae_2_193_0.zip", "size": 9136528,
         "browser_download_url": "https://github.com/advancedfx/advancedfx/releases/download/v2.193.0/hlae_2_193_0.zip"},
    ],
}


def test_the_portable_zip_is_chosen_over_the_installer():
    release = release_from_listing(LISTING)
    assert release.version == (2, 193, 0)
    assert release.zip_url.endswith("hlae_2_193_0.zip")
    assert release.label == "2.193.0"


def test_a_release_without_a_zip_is_rejected():
    with pytest.raises(ReleaseError):
        release_from_listing({"tag_name": "v9", "assets": [LISTING["assets"][1]]})


def test_versions_parse_with_or_without_v():
    assert parse_version("v2.193.0") == (2, 193, 0)
    assert parse_version("2.10.3\n") == (2, 10, 3)
    assert parse_version("nonsense") is None


def test_installed_version_comes_from_the_marker(tmp_path):
    assert installed_version(tmp_path) is None
    (tmp_path / VERSION_FILE).write_text("2.192.1", encoding="utf-8")
    assert installed_version(tmp_path) == (2, 192, 1)


def test_update_needed_only_for_newer_releases():
    latest = HlaeRelease((2, 193, 0), "u", 1)
    assert needs_update(None, latest)
    assert needs_update((2, 192, 9), latest)
    assert not needs_update((2, 193, 0), latest)
    assert not needs_update((3, 0, 0), latest)
