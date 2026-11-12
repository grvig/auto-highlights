"""Valve's VConsole2 wire protocol, as CS2 speaks it on its -netconport.

The port carries binary chunks, not text: a 4-byte type, a 32-bit version, a
big-endian 16-bit total length (header included) and a 16-bit handle, then the
payload. Commands go out as CMND chunks; console output comes back as PRNT
chunks whose text starts 28 bytes into the payload.

Other chunk types arrive too (the game's cvar list among them) and are not
always walkable by length, so output is found by scanning for PRNT headers
rather than by trusting every length field in the stream.
"""

from __future__ import annotations

import struct

HEADER = struct.Struct(">4sIHH")
VERSION = 0x00D40000
PRNT = b"PRNT"
PRNT_TEXT_OFFSET = 28


def pack_command(command: str) -> bytes:
    """A CMND chunk that runs one console command."""
    payload = command.encode("utf-8") + b"\x00"
    return HEADER.pack(b"CMND", VERSION, HEADER.size + len(payload), 0) + payload


def _prnt_text(payload: bytes) -> str:
    body = payload[PRNT_TEXT_OFFSET:] if len(payload) > PRNT_TEXT_OFFSET else payload
    return body.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()


def extract_output(buffer: bytes) -> tuple[list[str], bytes]:
    """Console lines from every complete PRNT chunk, plus bytes to keep.

    The returned remainder starts at a PRNT chunk that has not fully arrived
    yet (or holds the last few bytes, in case a header is split across reads),
    so the caller can prepend it to the next read.
    """
    lines: list[str] = []
    position = buffer.find(PRNT)
    while position != -1:
        if position + HEADER.size > len(buffer):
            return lines, buffer[position:]
        _, _, length, _ = HEADER.unpack_from(buffer, position)
        if length < HEADER.size:
            position = buffer.find(PRNT, position + 4)
            continue
        end = position + length
        if end > len(buffer):
            return lines, buffer[position:]
        text = _prnt_text(buffer[position + HEADER.size:end])
        if text:
            lines.append(text)
        position = buffer.find(PRNT, end)
    return lines, buffer[-3:]
