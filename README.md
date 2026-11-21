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
| 4 | App | Desktop window over layers 1–3 (React in pywebview) | Edge WebView2 (built into Windows 11) |

Layer 2 sits behind a `Recorder` interface with three backends:

- **HLAE** (default): CS2 is launched through HLAE, which renders every frame
  at a fixed framerate straight into ffmpeg and writes the game's audio
  alongside, so clips are frame-exact with sound in sync.
- **Window capture** (fallback when HLAE is missing or cannot hook the CS2
  build): films the CS2 window in real time, takes the game's sound from
  whatever the speakers play (WASAPI loopback, no extra driver), and trims
  each clip by detecting where playback started.
- **Dry run**: logs exactly what would be recorded and launches nothing.

## Install

Download `auto-highlights-<version>-setup.exe` from the
[Releases page](https://github.com/grvig/auto-highlights/releases/latest) and
run it. The installer is not code-signed yet, so Windows SmartScreen asks
first: "More info", then "Run anyway". It installs for your Windows account only (no admin prompt) and adds
auto-highlights to the Start menu. The app opens on four steps: pick demos
(it finds the ones in CS2's replays folder and your Downloads, including
FACEIT's compressed `.dem.zst` downloads, and names them by map and score,
"Cache 13-11 W"), pick whose
plays, look over the plays it chose, then record and make the reel. "Your
reels" lists what it has made; "Settings" holds the output folder, reel
shape, usual length and music.

The side bar says whether recording is ready, and shows an arrow when a
newer release is out. The first time, it offers to
fetch the two tools recording needs: ffmpeg (the official Windows build,
checked against its published checksum) and HLAE (from its official GitHub
releases, kept up to date because CS2 updates break old builds).
`auto-highlights --setup` from a prompt does the same.

Where things live once installed:

| What | Where |
|---|---|
| Settings | `%LOCALAPPDATA%\auto-highlights\config.toml` (written on first run) |
| ffmpeg, HLAE | `%LOCALAPPDATA%\auto-highlights\tools` |
| Parse cache, raw clips, run logs | `%LOCALAPPDATA%\auto-highlights` |
| Finished reels | `Videos\auto-highlights` |

Every recording, edit and setup run keeps a log in the `logs` folder next to
the cache (the last 20), with every console command sent to CS2: the first
thing to look at when a recording goes wrong.

Check everything at once:

```powershell
auto-highlights --check
```

## Running from source

Windows, Python 3.11+ (required by awpy).

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

A `config.toml` beside the code takes precedence over the installed app's
settings; copy `config.template.toml` to start one. It is git-ignored.

The window's interface lives in `ui/` (React, TypeScript, Vite) and needs
Node.js 22 or newer:

```powershell
cd ui
npm install
npm test            # interface tests, no window needed
npm run build       # writes highlights\app\web, which the window loads
cd ..
python -m highlights --app
```

While working on the interface, `npm run dev` serves it with live reload and
`python -m highlights --app-dev http://localhost:5173` points the window at
it (with the WebView developer tools on).

Build the standalone app and its installer (needs PyInstaller, Inno Setup
and Node.js; the interface is built first):

```powershell
pip install pyinstaller
python packaging\build.py --out D:\auto-highlights\build --installer
```

This makes `dist\auto-highlights\auto-highlights.exe` (Python and every
dependency inside) and `installer\auto-highlights-<version>-setup.exe`.
Started with no arguments the exe opens the window; from a prompt with
arguments it is the command line below.

GitHub runs the Python and interface tests on every push to `main`. Pushing a tag that matches the
version in `highlights/__init__.py` (for example `v0.2.0`) builds the
installer on GitHub and publishes it as a release.

### FACEIT demos

FACEIT serves CS2 demos compressed as `.dem.zst` (older downloads use
`.dem.gz`). Pick them as they are, in the app or on the command line: they
are unpacked once into the cache folder and reused after that.

### When CS2 updates

Updates can break HLAE's hook until HLAE ships a fix (the app picks the fix
up by itself), and can stop CS2 playing demos recorded before the update.
`--check` shows when CS2 last updated. An HLAE older than the update is
flagged as a warning until it has recorded a clip on the new build.

When HLAE cannot hook the installed build (CS2 build 26798866 broke HLAE
2.193.0 on 20 Nov 2026), the run stops trying HLAE at the first clip and
records everything with window capture instead, in the same run. The app
remembers the build, so later runs go straight to window capture until HLAE
or CS2 updates, and `--check` says so.

## Usage

The whole thing in one line, for the Steam account signed in on this PC:

```powershell
auto-highlights "match1.dem" "match2.dem" --me --record --stitch
```

That plans your best plays across the demos, records them in CS2, and writes
about two minutes of them back to back: each fight from just before the
action to just after the last kill, hard cuts, your game sound, no text and
no effects, exported in 4:3 stretched to 16:9. Each reel gets its own timestamped name in
`output_dir`, so nothing is ever overwritten.

### Planning

```powershell
auto-highlights "path\to\match.dem"                # players and stats
auto-highlights "path\to\match.dem" --me           # every play, scored
auto-highlights "path\to\match.dem" --me --best 90 # the best 90 seconds
```

- Highlights are your frags: kills, multi-kills, aces and clutches.
  `--types all` adds deaths and utility.
- Plays are scored for impact (clutches, round swings), speed and
  cleanliness: one-taps and few shots per kill rank above spraying, and
  ordinary plays are left out rather than used as filler (`--min-score`).
- An ace that is also a clutch is filmed once, as one fight.
- `--best SECONDS` sets the reel length (recording defaults to 120 from
  config); `--all` keeps every play; `--order montage|chronological`.
- Clips follow the fighting: about 3 seconds before the action (further
  back if a firefight was already going), 2 seconds after the last kill, and
  any stretch over 5 seconds with no shots or hits is cut out, so quick
  multi-kills stay one continuous shot while slow rounds lose their walking.
  The lead-in and tail are in `[clips]` of `config.toml`;
  `scripts/dead_time.py` measures how much quiet time a reel would carry.

### Recording

```powershell
auto-highlights "match.dem" --me --dry-run --stitch    # preview, launches nothing
auto-highlights "match.dem" --me --record --stitch      # the real thing
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
- **App**: desktop window with the whole flow (demos, player, plays, record
  with progress and stop, your reels, settings, readiness and setup), tested
  headlessly; the first look on screen is still to come.
