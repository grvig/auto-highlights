"""Tests for the VConsole2 wire protocol."""

from highlights.recorder.vconsole import HEADER, VERSION, extract_output, pack_command

# The 28-byte prefix of a real PRNT payload captured from CS2.
PREFIX = (
    b"\xe3\x193/" + b"\x00" * 7 + b"\x02\x00\xff\x00\xff\x00\x02\x05A" + b"\x00" * 4 + b" \x01\x00\x00"
)


def prnt(text: str) -> bytes:
    payload = PREFIX + text.encode("utf-8") + b"\x00"
    return HEADER.pack(b"PRNT", VERSION, HEADER.size + len(payload), 0) + payload


def test_prefix_matches_the_captured_layout():
    assert len(PREFIX) == 28


def test_pack_command_builds_a_cmnd_chunk():
    chunk = pack_command("demo_pause")
    kind, version, length, handle = HEADER.unpack_from(chunk)
    assert (kind, version, handle) == (b"CMND", VERSION, 0)
    assert length == len(chunk) == 12 + len("demo_pause") + 1
    assert chunk.endswith(b"demo_pause\x00")


def test_extracts_text_from_prnt_chunks():
    lines, _ = extract_output(prnt("Connection in progress...\n") + prnt("Demo Skipping finished at tick 26000"))
    assert lines == ["Connection in progress...", "Demo Skipping finished at tick 26000"]


def test_ignores_other_chunk_types_between_prints():
    other = HEADER.pack(b"CVRB", 0x00020007, 20, 0) + b"\x01" * 8
    lines, _ = extract_output(prnt("a") + other + prnt("b"))
    assert lines == ["a", "b"]


def test_partial_chunk_is_kept_for_the_next_read():
    whole = prnt("Demo paused at engine time 28376, demo tick 26323")
    lines, rest = extract_output(prnt("first") + whole[:20])
    assert lines == ["first"]
    assert rest == whole[:20]
    lines, _ = extract_output(rest + whole[20:])
    assert lines == ["Demo paused at engine time 28376, demo tick 26323"]


def test_non_latin_console_text_survives():
    lines, _ = extract_output(prnt("spec_player 臻咘踔"))
    assert lines == ["spec_player 臻咘踔"]
