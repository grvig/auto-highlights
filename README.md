# auto-highlights

Turns a Counter-Strike 2 demo (`.dem`) into a highlight reel of real in-game
footage for one chosen player.

Pick a demo, pick one of the 10 players, tick the highlight types you want
(kills, multi-kills, aces, clutches, deaths, utility impact), and get a single
stitched video back.

## Architecture

Four decoupled layers. The engine never imports the recorder, and runs with no
game and no OBS present.

| Layer | Name | Does | Needs |
|---|---|---|---|
| 1 | Engine | Parses the demo into an ordered **clip plan** of highlight moments | Nothing but Python |
| 2 | Recorder | Drives CS2 playback while OBS records, one raw clip per moment | CS2 + OBS running |
| 3 | Stitcher | Concatenates raw clips into the final reel | ffmpeg |
| 4 | GUI | CustomTkinter front end over layers 1–3 | — |

Layer 2 sits behind a `Recorder` interface so an alternate backend (HLAE) can
replace OBS without touching layers 1, 3, or 4. It also has a dry-run backend
that logs exactly what it would record without launching anything.

## Setup

Windows, Python 3.11+ (required by awpy).

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Then copy the config template and fill in your own paths:

```powershell
copy config.template.toml config.toml
```

`config.toml` is git-ignored — it holds your OBS websocket password and
machine-specific paths. `config.template.toml` is the committed shape.

### External dependencies

- **CS2** — only needed for recording (layer 2). Parsing works without it.
- **OBS Studio** with the obs-websocket plugin — enable it under
  *Tools → WebSocket Server Settings*. Note the port and password.
- **ffmpeg** — needed for stitching (layer 3), must be on PATH.

## Usage

Layer 1 works on its own — no CS2, no OBS. Inspect a demo:

```powershell
python -m highlights.cli "path\to\match.dem"
```

```
Map        : de_nuke
Demo type  : GOTV (SourceTV Demo)
Tickrate   : 64
Rounds     : 24
Kills      : 184

Players (10):
  #   SIDE  NAME                        K    D    K/D
  --------------------------------------------------
  1   CT    ICECUBE                    12   18   0.67
  ...
```

Your own demos live under `<cs2_root>\game\csgo\replays\`.

Plan a chosen player's highlights:

```powershell
python -m highlights.cli "path\to\match.dem" --player semi --types clutch,ace,multi_kill
```

```
Highlight plan for semi
Types      : clutch, ace, multi_kill
Moments    : 4  (239s of footage)
  #   RND   TIME TYPE        DESCRIPTION
  ------------------------------------------------------------
  1     5  07:06 clutch      1v3 clutch (won)
  2     5  08:28 ace         ACE (5 kills)
  3    12  19:13 clutch      1v1 clutch (won)
  4    12  19:33 multi_kill  Triple kill (3 kills)
```

`--types` accepts `kill`, `multi_kill`, `ace`, `clutch`, `death`, `utility`
(comma-separated, or `all`). Single kills already shown inside a multi-kill,
ace, or clutch are dropped so footage is not recorded twice.

## Status

**Engine (Layer 1) is complete and verified against real matchmaking demos.**

- Parsing: header, roster, rounds, kills, damage, flashes.
- Detectors: single kills, multi-kills, aces, clutches (last-alive win),
  deaths, and utility impact (multi-enemy flashes, HE/molotov damage).
- Clip-plan builder composes selected detectors into one ordered, deduped plan.

Deferred: "meaningful smoke" detection (Milestone 2) — judging a smoke's
usefulness needs more heuristics than the other utility signals, so it is left
out rather than shipped as noise. Next up is Layer 2, the recorder.

See the commit history for detail.
