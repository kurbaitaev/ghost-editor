# Data Story

When the speaker's line carries a quantity, a chart draws itself on cream paper: a red-blue pencil draws every mark
(axes, bars, cells, dots), handwritten notes pin the speaker's words and the facts to the marks, the subtitle is the
chart's figure caption (mono kicker with the figure and its source, hairline rule, serif words on their onsets). Between
the pages the face as shot, with the caption on a paper band at the bottom and pencil notes on paper slips above the
head. Every number on screen is true and sourced; a chart with no verified number says SCHEMATIC and shows none. Ported
from Lemo-Opuscar's "Data Storytelling" style (styles/dataviz, MIT).

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog); house.json
is the fixed look, catalog.json what each reel used.

## Calls

- "Data Story"
- "data storytelling"
- "chart reel", "draw the numbers"

## What it needs

The approved cut: the plates as shot (any number, same timeline: alt / wide / tight), assets/voice.wav,
build/words.cut.json (edit seconds), build/face.json per plate (`scripts/face_track.py <plate> --out ...`; the notes are
guarded against the face core). The data: a primary or official source for every number (paper, agency page), with its
date. A real picture only for a thing the speaker names (e.g. a book cover). No matte, no music, no stock footage.
Fonts (Caveat, Playfair Display, JetBrains Mono) and SFX are copied from the skill by the builder.

## Build

A Python builder on scripts/lib/facereel.py: `datastory.py` (class `DataStory`, pages as `Layer`; the docstring lists
every call and sketches an English reel about caffeine with real FDA numbers), drawing with `engine.js` (the source's
Canvas engine adapted to 1080x1920, inlined into index.html and painted from one paused GSAP timeline, so every frame is
a pure function of t). The public edition has no worked example for this recipe yet: write `$P/tools/build.py` from
build/plan.txt and the docstring.

```bash
S=~/.claude/skills/ghost-editor; PY=~/.venvs/media/bin/python
$PY $P/tools/build.py --project $P             # index.html, build/spec.json, beats.json, plan.json, sfx_events.json
bash $S/scripts/hf.sh lint $P                   # 0 errors
bash $S/scripts/hf.sh snapshot $P --at <beat times> --no-end --describe false -o $P/build/snap   # look at every beat
$PY $S/scripts/finals.py preview $P --out $P/finals --style "Data Story" --code R01 --title "..."   # WAIT for the user's OK
```

The calls: `R.talk(plate, t0, t1)` (the face world), `R.note(text, x, y, at, dur, color, align, deco)` (a pencil note
on a slip above the head), `R.page(id, t0, t1, push)` -> Page with `title`, `sub`, `mono`, `type`, `hand`, `stroke`,
`ring`, `leader`, `under`, `strike`, `wave`, `heart`, `dot`, `bar`, `cell`, `box`, `fill`, `hatch`, `img`, `push`, and
the generators `plot_frame`, `bars`, `day_grid`, `print_`; `R.picture()`, `R.captions(starts, kickers)`, `R.sound()`,
`R.beat()`, `R.build()`.

## Where things are

- Source: Lemo-Opuscar, styles/dataviz (STYLE.md, DEMO.md, demo/engine.js); its film was only watched and is not
  copied here.

## Credit

Adapted from Lemo-Opuscar by LemoLab, https://github.com/lemomo-ai/lemo-opuscar, styles/dataviz (MIT, (c) 2026 LemoLab;
LICENSE-lemo-opuscar.txt). Details in CREDITS.txt.
