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

## Status

Under construction, engine first. See the commit history for progress.
