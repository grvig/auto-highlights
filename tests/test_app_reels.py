"""Tests for listing finished reels."""

from highlights.app.reels import list_reels


def test_reels_are_listed_newest_first_with_their_extras(tmp_path):
    (tmp_path / "semi_highlights_2026-11-16_0839.mp4").write_bytes(b"x" * 2_000_000)
    (tmp_path / "semi_highlights_2026-11-16_0839.thumbnail.png").write_bytes(b"png")
    (tmp_path / "semi_highlights_2026-11-16_0839.chapters.txt").write_text("00:00 ACE (Round 5)\n")
    (tmp_path / "semi_highlights_2026-11-17_1015_2.mp4").write_bytes(b"x")
    (tmp_path / "test_A_nuke_pro_music.mp4").write_bytes(b"x")  # not a reel name
    reels = list_reels(tmp_path)
    assert [r["made"] for r in reels] == ["2026-11-17T10:15", "2026-11-16T08:39"]
    older = reels[1]
    assert older["player"] == "semi" and older["megabytes"] == 2.0
    assert older["thumbnail"].endswith(".thumbnail.png") and older["chapters"].startswith("00:00")
    assert reels[0]["thumbnail"] is None and reels[0]["chapters"] is None


def test_names_with_underscores_keep_the_whole_player_name(tmp_path):
    (tmp_path / "Uber_hu_highlights_2026-11-16_0839.mp4").write_bytes(b"x")
    assert list_reels(tmp_path)[0]["player"] == "Uber_hu"


def test_a_missing_folder_has_no_reels(tmp_path):
    assert list_reels(tmp_path / "nope") == []
