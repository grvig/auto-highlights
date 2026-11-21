# Changelog

## 1.0.0 - 2026-11-21

First public release.

### What it does

- Turns CS2 demos into a highlight reel of your own plays: real in-game
  footage, cut from just before the action to just after the last kill,
  exported 4:3 stretched to 16:9 by default (or 4:3, 16:9, vertical).
- Finds demos on its own in CS2's replays folder and your Downloads,
  including FACEIT's compressed `.dem.zst` downloads, and lists them by map
  and score ("Cache 13-11 W").
- Picks your best plays across one or more matches: multi-kills, clutches,
  aces, one-taps and wallbangs, scored by impact, and trimmed to the length
  you choose.
- Records each play in CS2 through HLAE, frame by frame with the game's sound.
  When HLAE cannot hook a new CS2 build, it switches to window capture by
  itself, with the speakers' sound, and goes back to HLAE once HLAE updates.
- Puts your CS2 settings back exactly as they were after every recording.
- Downloads ffmpeg and HLAE on first run and keeps HLAE up to date.
- Tells you when a newer release is out.

### Known limits

- Windows 10/11 only, with CS2 installed through Steam.
- The installer is not code-signed yet, so Windows SmartScreen asks for a
  confirmation ("More info" > "Run anyway") the first time.
- Recording takes over CS2 while it runs; leave the PC alone until it is done.
- Window capture (the fallback) records in real time and its sound can sit up
  to a tenth of a second off the picture; HLAE recordings are frame-exact.
- Matchmaking demos still have to be downloaded from CS2's Watch tab first.
