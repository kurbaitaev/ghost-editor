# Swiss Grid

International Typographic Style in motion around a talking head: the 9:16 frame is a modular page with 6 columns, one
typeface (Inter) and one signal colour (red = the reel's one protagonist). The speaker's face, as shot, lives in one
band of the page between a paper header (caption row + chapter counter) and a paper page where their words are set
flush left, each word rising out of a clip rect on its spoken onset. Between face worlds the page wipes up into short
poster cards: giant numeral chapter cards, a grid being built, a grid that means something. Exact, quiet motion: one
precise ease and linear, no fades, knife cuts for deletions, and one exception (the protagonist) that leaves the grid.
Ported from LemoLab's MIT-licensed Swiss Motion Graphics style (lemo-opuscar `styles/swiss-motion`); see CREDITS.txt.

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog);
house.json is the fixed look, catalog.json what each reel used.

## Calls

- "Swiss Grid"
- "Swiss style" / "Swiss motion"
- "like a Swiss poster"

## What it needs

The approved cut: the plates as shot (wide + tight on the same timeline is best; one works), assets/voice.wav,
build/words.cut.json (edit seconds), and a face file per plate (`scripts/face_track.py <plate> --out
build/face_<name>.json`). No matte and no stock: the header and page never touch the speaker's head box. A real picture
only for a thing the speaker names (shown greyscale, at most ~3 a minute). Inter (OFL) and the SFX are copied from the
skill by the builder; there is no music bed.

## Build

A Python builder on `scripts/lib/facereel.py`: `swissgrid.py` (class `Grid`; its docstring lists every call and
sketches an English reel), reading the look from house.json. A reel is a short generator in the project that calls it.
The public edition has no worked example for this recipe yet: write `$P/tools/build.py` from the world list (SYSTEM.md
planning procedure) and the docstring.

```bash
S=~/.claude/skills/ghost-editor; PY=~/.venvs/media/bin/python
$PY $S/scripts/face_track.py $P/assets/wide.mp4 --out $P/build/face_wide.json      # one per plate
$PY $P/tools/build.py --project $P            # index.html, build/beats.json, plan.json, sfx_events.json, holds.txt
bash $S/scripts/hf.sh lint $P                 # 0 errors
bash $S/scripts/hf.sh snapshot $P -o $P/snaps --no-end --describe false --at <beat keys>   # look at every beat
$PY $S/scripts/finals.py preview $P --out $P/finals --style "Swiss Grid" --code R01 --title "..."   # WAIT for the user's OK
```

The calls: `face_world()` (the face + the page), `card()` (a full-screen poster card, <= 2.5 s), `text()` (the
speaker's words on their onsets, or a label), `note_row()`, `counter()`, `numeral()`, `rule()`, `slab()`, `dot()`,
`bar()`, `modules()`, `guides()`, `knife()` + `group()`, `minute_grid()`, `exception()`, `picture()`, `sfx()`, `build()`.

The build fails on: a word the speaker did not say (word refs and phrases are matched to the transcript), a glyph Inter
lacks, text under 48 px, any text box outside the safe area (y 120-1700, x <= 980), a page or header that touches the
head box, a card over 2.5 s, the face on screen under 65 %, more than 3 inserts a minute, a gap between worlds.

## Where things are

- Source: lemo-opuscar, styles/swiss-motion (STYLE.md, DEMO.md, demo/); the film was only watched (not part of the
  recipe).

## Credit

Adapted from "Swiss Motion Graphics" in lemo-opuscar by LemoLab (https://github.com/lemomo-ai/lemo-opuscar), MIT,
Copyright (c) 2026 LemoLab (LICENSE-lemo-opuscar.txt). The demo film, its music, voice and fonts are not copied.
