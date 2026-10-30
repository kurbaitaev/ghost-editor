# Halftone Dossier

A talking-head reel read out as a retro print case file on its subject: cream archive paper, overprinted halftone
dots in four flat inks, heavy black-serif headlines with a misregistered pink shadow that pop in glyph by glyph,
rubber stamps that slam with a page shake, drawn exhibits with thick navy outlines that boil at 10 fps, a case-file
HUD and a navy caption bar that carries every spoken word. The speaker's face, as shot, sits between the pages: on the speaker's face only
the HUD, the caption bar under the speaker's chin, headlines behind the speaker's head (matte) and one closing stamp below the speaker's face.
Ported from LemoLab's MIT-licensed style "Halftone Dossier" (github.com/lemomo-ai/lemo-opuscar, styles/halftone-dossier).

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog);
house.json is the fixed look, catalog.json what each reel used.

## Calls

- "Halftone Dossier"
- "case file style"
- "dossier reel"

## What it needs

The approved cut (any talking head with a subject that can be "put on file": a habit, a product, a tool, a myth): one
plate as shot (the alt cut works: it already alternates the speaker's framings), its matte webm with alpha for the headlines
behind the speaker's head (scripts/matte.py; only the time ranges you use need it), assets/voice.wav, build/words.cut.json (edit
seconds). Pictures only when the speaker names a real thing (a book cover, a product): shown as a pinned print, never halftoned.
Everything else is drawn by the builder. Fonts and SFX are copied from the skill; paper, grain, stamp ink and halftone
layers are generated into assets/gen/.

## Build

A Python builder, `dossier.py` (class `Dossier`; its docstring lists every call), reading the look from house.json.
A reel is a short generator in the project. The public edition has no worked example for this recipe yet: write it from
the usage block in dossier.py's docstring (`python3 dossier.py` prints it), SYSTEM.md (slots, planning procedure) and the
catalog, then

```bash
S=~/.claude/skills/ghost-editor; PY=~/.venvs/media/bin/python
$PY $P/tools/build.py                          # index.html, build/beats.json, build/coverage.txt
bash $S/scripts/hf.sh lint $P                   # 0 errors
bash $S/scripts/hf.sh snapshot $P -o $P/build/snap --no-end --describe false --at <beat times>   # look at every beat
$PY $S/scripts/finals.py preview $P --out $P/finals --style "Halftone Dossier" --code R01 --title "..."   # WAIT for the user's OK
```

The calls: `face()`, `behind()`, `face_stamp()`, `card()`, then per page `ht()`, `headline()`, `text()`, `svg()`
(boil=True for props), `numeral()`, `stamp()`, `shake()`, `flash()`, `pushin()`, `pop()`, `rise()` and the exhibit
generators `mugshot()`, `photo_exhibit()`, `notifications()`, `board()`, `task_verdict()`, `space_grid()`; then
`captions()`, `chips()`, `wipes()`, `sfx()`, `build()`.

## Where things are

- Source: https://github.com/lemomo-ai/lemo-opuscar, styles/halftone-dossier (STYLE.md, DEMO.md, demo/).

Credit: adapted from "Halftone Dossier" by LemoLab (lemo-opuscar, MIT, Copyright (c) 2026 LemoLab); see CREDITS.txt
and LICENSE-lemo-opuscar.txt.
