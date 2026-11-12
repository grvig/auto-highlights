# auto-highlights

Turns Counter-Strike 2 demos (`.dem`) into a highlight reel of real in-game
footage for one chosen player.

Pick one or more demos, pick a player (or let it find you), choose the
highlight types you want (kills, multi-kills, aces, clutches, deaths, utility
impact), and get a single edited video back, by default in 4:3 stretched to
16:9.

## Architecture

Four decoupled layers. The engine never imports the recorder, and runs with no
game installed.

| Layer | Name | Does | Needs |
|---|---|---|---|
| 1 | Engine | Parses demos into a scored, ordered **clip plan** of highlight moments | Nothing but Python |
| 2 | Recorder | Plays each moment in CS2 and renders it to a clip with game audio | CS2 + HLAE |
| 3 | Stitcher | Joins clips into the reel and exports it in the chosen shape | ffmpeg |
| 4 | App | Desktop front end over layers 1–3 | — |

Layer 2 sits behind a `Recorder` interface with three backends:

- **HLAE** (default): CS2 is launched through HLAE, which renders every frame
  at a fixed framerate straight into ffmpeg and writes the game's audio
  alongside, so clips are frame-exact with sound in sync.
- **Window capture** (fallback when HLAE is missing): films an already running
  CS2 window in real time and trims each clip by detecting where playback
  started.
- **Dry run**: logs exactly what would be recorded and launches nothing.

## Setup

Windows, Python 3.11+ (required by awpy).

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Then copy the config template and adjust it if needed:

```powershell
copy config.template.toml config.toml
```

`config.toml` is git-ignored and holds machine-specific paths;
`config.template.toml` is the committed shape. The CS2 install and your Steam
account are found automatically.

### External dependencies

- **CS2** — only needed for recording. Parsing works without it.
- **HLAE** — only needed for recording. Point `paths.hlae` at the folder
  holding `HLAE.exe` (the app installer bundles it).
- **ffmpeg** — needed for recording and stitching; on PATH, or its path set in
  `config.toml`.

Check everything at once:

```powershell
python -m highlights.cli --check
```

## Usage

Inspect a demo (no game needed):

```powershell
python -m highlights.cli "path\to\match.dem"
```

Plan a player's highlights:

```powershell
python -m highlights.cli "path\to\match.dem" --player semi --types clutch,ace,multi_kill
```

`--types` accepts `kill`, `multi_kill`, `ace`, `clutch`, `death`, `utility`
(comma-separated, or `all`). `--me` picks the signed-in Steam account. Pass
several demos to plan across matches. `--best 60` keeps the strongest 60
seconds; `--order` arranges them as a montage or chronologically.

Moments from the same round are merged, so an ace that is also a clutch is
filmed once. Multi-kills get victim-cam replays from the victims' eyes.

### Recording

See what would be captured, without launching anything:

```powershell
python -m highlights.cli "match.dem" --player semi --best 60 --dry-run -v
```

Record and stitch for real:

```powershell
python -m highlights.cli "match.dem" --player semi --best 60 --record --stitch
```

This launches CS2 through HLAE at 1440x1080, renders each clip, closes the
game, and puts your CS2 settings back exactly as they were (a backup is kept
next to the clips folder). Clips land in `clips_dir`, numbered in plan order.
The reel is written to `output_dir` as `<player>_highlights.mp4`.

`--aspect` picks the reel's shape: `stretched` (default, 4:3 filling 16:9),
`4:3`, `pillarbox`, `16:9`, or `vertical`.

## Status

- **Engine**: complete and verified against real matchmaking demos — kills,
  multi-kills, aces, clutches, deaths, utility impact, scoring, best-of
  selection, multi-demo plans and victim-cam replays.
- **Recorder**: the CS2 control path (binary console protocol, confirmed seeks,
  tick-exact stepped playback, spectating by name) and HLAE rendering were
  proven against a live CS2 with standalone scripts; the backends in this repo
  are their port and are unit-tested.
- **Stitcher**: joins clips and exports every aspect profile with ffmpeg.
- **App**: not started.
