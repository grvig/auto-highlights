"""Tests for noticing a newer release on GitHub (GitHub faked)."""

import json

from highlights.app.updates import RELEASES_PAGE, check_for_update, version_tuple


def answering(tag, url=None):
    body = {"tag_name": tag, "html_url": url or f"{RELEASES_PAGE}/tag/{tag}"}
    return lambda requested: json.dumps(body).encode()


def test_a_newer_release_is_offered_with_its_page():
    found = check_for_update("1.0.0", answering("v1.0.1"))
    assert found == {"available": True, "version": "1.0.1", "url": f"{RELEASES_PAGE}/tag/v1.0.1"}


def test_the_same_or_an_older_release_is_not():
    assert check_for_update("1.0.0", answering("v1.0.0")) == {"available": False}
    assert check_for_update("1.2.0", answering("v1.1.9")) == {"available": False}


def test_offline_or_odd_answers_mean_no_update():
    def offline(url):
        raise OSError("no route to host")

    assert check_for_update("1.0.0", offline) == {"available": False}
    assert check_for_update("1.0.0", lambda url: b"<html>") == {"available": False}
    assert check_for_update("1.0.0", answering("nightly")) == {"available": False}


def test_only_this_projects_release_page_is_ever_linked():
    found = check_for_update("1.0.0", answering("v2.0.0", url="https://example.com/evil"))
    assert found["url"] == RELEASES_PAGE


def test_versions_compare_as_numbers():
    assert version_tuple("v1.10.0") > version_tuple("1.9.9")
    assert version_tuple("1.0") == (1, 0)
