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

The whole thing in one line, for the Steam account signed in on this PC:

```powershell
python -m highlights.cli "match1.dem" "match2.dem" --me --record --stitch
```

That plans your best plays across the demos, records them in CS2, and writes
about two minutes of them back to back: whole fights (the walk-up, every kill,
a beat after), hard cuts, your game sound, no text and no effects, exported
in 4:3 stretched to 16:9. Each reel gets its own timestamped name in
`output_dir`, so nothing is ever overwritten.

### Planning

```powershell
python -m highlights.cli "path\to\match.dem"                # players and stats
python -m highlights.cli "path\to\match.dem" --me           # every play, scored
python -m highlights.cli "path\to\match.dem" --me --best 90 # the best 90 seconds
```

- Highlights are your frags: kills, multi-kills, aces and clutches.
  `--types all` adds deaths and utility.
- Plays are scored for impact (clutches, round swings), speed and
  cleanliness: one-taps and few shots per kill rank above spraying, and
  ordinary plays are left out rather than used as filler (`--min-score`).
- An ace that is also a clutch is filmed once, as one fight.
- `--best SECONDS` sets the reel length (recording defaults to 120 from
  config); `--all` keeps every play; `--order montage|chronological`.
- How much of each fight to keep is in `[clips]` of `config.toml`.

### Recording

```powershell
python -m highlights.cli "match.dem" --me --dry-run --stitch    # preview, launches nothing
python -m highlights.cli "match.dem" --me --record --stitch      # the real thing
```

CS2 is launched through HLAE at 1440x1080, each clip is rendered frame by
frame with game audio, the game is closed and your CS2 settings are put back
exactly as they were (a backup is kept next to the clips folder).

- The HUD is clean by default: crosshair and kill feed. Demo playback can
  only show CS2's spectator HUD, never your own; `--spectator-hud` keeps it.
- `--aspect` picks the shape: `stretched` (default), `4:3`, `pillarbox`,
  `16:9`, or `vertical`.
- `--resume` keeps clips an interrupted run already finished; `--edit-only`
  re-edits the clips on disk without touching the game.
- HLAE is updated from its official GitHub releases before every recording
  (CS2 updates break old builds); `--update-hlae` does it on demand.

### Optional extras

None of these are on by default; the default reel is plain.

- `--music song.mp3` (your own file) under the game sound, ducking under
  gunshots, with cuts pulled onto the beat; `--music-start` skips an intro.
- `--transition fade|fadeblack|...` instead of hard cuts.
- `--captions` names each play on screen; `--cards` adds title and outro
  cards.
- `--victim-cams` replays quick multi-kills from each victim's eyes.
- `--slowmo`, `--punch-ins`, `--flashes` (or `--pro` for all three), and
  `--teaser`.

Next to every reel the app writes a `.chapters.txt` (timestamps for a YouTube
description) and a 1280x720 `.thumbnail.png`. Loudness is levelled to
-16 LUFS as one steady gain, with true peaks limited so gunshots never clip.

## Status

- **Engine**: complete and verified against real matchmaking demos: kills,
  multi-kills, aces, clutches, deaths, utility, scoring (impact, speed and
  shot accuracy), whole-fight clip windows, best-of selection and
  multi-demo plans.
- **Recorder**: proven end to end on a live CS2 (2026-11-16): HLAE and the
  window-capture fallback both record every clip with sound; slow-motion
  ramps render smoothly at 150 fps; victim cams follow the right player; the
  game is closed and the player's settings are put back.
- **Editor**: plain hard-cut reels by default; captions, cards, transitions,
  music, effects, chapters and thumbnails available as options. All checked
  on real footage.
- **App**: not started.
