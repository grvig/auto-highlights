"""Tests for the KeyValues (.vdf) reader."""

import pytest

from highlights.steam.vdf import VdfError, get_ci, loads

LIBRARY_FOLDERS = r'''
"libraryfolders"
{
	"0"
	{
		"path"		"C:\\Program Files (x86)\\Steam"
		"apps"
		{
			"228980"		"361231214"
		}
	}
	"1"
	{
		"path"		"D:\\SteamLibrary"
		"apps"
		{
			"730"		"69961875579"
		}
	}
}
'''


def test_parses_steam_library_folders():
    data = loads(LIBRARY_FOLDERS)
    libraries = data["libraryfolders"]
    assert libraries["1"]["path"] == "D:\\SteamLibrary"
    assert "730" in libraries["1"]["apps"]


def test_unquoted_tokens_and_comments():
    data = loads('// a comment\nroot { key value  "other" "x y" }')
    assert data == {"root": {"key": "value", "other": "x y"}}


def test_escaped_quotes_inside_strings():
    assert loads(r'"k" "say \"hi\""') == {"k": 'say "hi"'}


def test_case_insensitive_lookup():
    data = loads('"Users" { "MostRecent" "1" }')
    assert get_ci(data, "users") == {"MostRecent": "1"}
    assert get_ci(data, "missing") is None


@pytest.mark.parametrize(
    "bad",
    ['"a" { "b" "c"', '"a" "b" }', '"a"', '{ "a" "b" }', '"unterminated'],
)
def test_malformed_input_raises(bad):
    with pytest.raises(VdfError):
        loads(bad)
