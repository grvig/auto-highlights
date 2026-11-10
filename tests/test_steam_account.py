"""Tests for reading the signed-in Steam account."""

from highlights.steam.account import LOGIN_USERS, signed_in_account


def write_users(steam, body):
    path = steam / LOGIN_USERS
    path.parent.mkdir(parents=True)
    path.write_text('"users" {' + body + "}", encoding="utf-8")


def user(steamid, persona, most_recent="0", timestamp="0", login="secret_login"):
    return (
        f'"{steamid}" {{ "AccountName" "{login}" "PersonaName" "{persona}" '
        f'"MostRecent" "{most_recent}" "Timestamp" "{timestamp}" }}'
    )


def test_most_recent_account_is_chosen(tmp_path):
    write_users(
        tmp_path,
        user("76561198000000001", "alt", timestamp="200")
        + user("76561198000000002", "main", most_recent="1", timestamp="100"),
    )
    account = signed_in_account(tmp_path)
    assert account.steamid == "76561198000000002"
    assert account.persona_name == "main"


def test_falls_back_to_latest_timestamp_without_a_flag(tmp_path):
    write_users(
        tmp_path,
        user("76561198000000001", "older", timestamp="100")
        + user("76561198000000002", "newer", timestamp="300"),
    )
    assert signed_in_account(tmp_path).persona_name == "newer"


def test_login_name_is_never_exposed(tmp_path):
    write_users(tmp_path, user("76561198000000001", "shown", most_recent="1"))
    account = signed_in_account(tmp_path)
    assert "secret_login" not in repr(account)


def test_missing_file_gives_none(tmp_path):
    assert signed_in_account(tmp_path) is None


def test_no_accounts_gives_none(tmp_path):
    write_users(tmp_path, "")
    assert signed_in_account(tmp_path) is None
