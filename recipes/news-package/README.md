# News Package

The speaker's talking head as the anchor of a one-story TV news segment: a sting whose plate flies into the corner and
becomes the channel bug, a lower-third strap on the speaker's chest (lemon category tab, paper headline, ink end block)
that stays from the first story to the recap and flips its words, a rundown of the reel's points that opens the segment
and comes back ticked off at the end, and between face shots full-frame package cards on ink that carry one fact each
(a document, a split-flap board, check rows, accent-edged cards, a schematic threshold line, proportion bars), joined by
a lemon band wipe between parts and hard cuts inside a part. Ported from the MIT-licensed lemo-opuscar style "Broadcast
News Package" (https://github.com/lemomo-ai/lemo-opuscar, styles/news-package) and adapted from a 16:9 bulletin with no
anchor to a 9:16 talking head.

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog);
house.json is the fixed look, catalog.json what each reel used.

## Calls

- "News Package"
- "like a TV news segment"
- "news bulletin style"

## What it needs

The cut as shot: one or more 1080x1920 framings of the same timeline (alt / wide / tight; switching between them on the
speaker's jump cuts is the only "camera"), assets/voice.wav, build/words.cut.json (edit seconds). No matte: nothing sits
behind the speaker's head. A list or a run of points in the script (3-5) for the rundown. Pictures only when the speaker
names a real thing (a book cover, a document); everything else is drawn in code. Fonts (Fira Sans, Fira Sans Extra
Condensed, IBM Plex Mono, all OFL with Cyrillic) and SFX are copied by the builder.

## Build

A Python builder, `newspackage.py` (class `Bulletin`; its docstring lists every call and sketches an English segment),
reading the look from house.json. A reel is a short generator in the project that calls it. The public edition has no
worked example for this recipe yet: write `$P/tools/build.py` from build/plan.txt, the docstring and SYSTEM.md.

```bash
S=~/.claude/skills/ghost-editor; PY=~/.venvs/media/bin/python
$PY $P/tools/build.py --project $P             # index.html, build/beats.json, build/coverage.txt
bash $S/scripts/hf.sh lint $P                   # 0 errors
bash $S/scripts/hf.sh snapshot $P --at <beat times> --no-end --describe false   # look at every beat
$PY $S/scripts/finals.py preview $P --out $P/finals --style "News Package" --code R01 --title "..."   # WAIT for the user's OK
```

The calls: `sting()` (plate -> bug), `face()` + `face_strap()` (enter / set / flip), `card()` + `wipe()`, the package
parts `rundown()`, `eyebrow()`, `push_text()`, `stamp()`, `corner_tag()` (via `card(tag=...)`), `bracket()`, and the
graphics `document()`, `flap_board()`, `check_rows()`, `accent_cards()`, `threshold()`, `proportion()`, `cells()`;
then `plates()`, `sfx()`, `build()`. Strap states are `Strap(tab, head, sub, source)`; every word is checked to be
>= 48 px and to have its glyph in the font. `Bulletin(..., lang=)` sets the page language (default "ru"; pass "en" for
an English reel).

## Where things are

- Source: lemo-opuscar, styles/news-package (STYLE.md, DEMO.md, demo/main.js); the reference film was only watched
  (not part of the recipe).
- Fonts: fonts/ (woff2 subsets for the page, OFL texts beside them) and fonts/ttf/ (the full TTFs for measuring; IBM
  Plex Mono is served from its TTF, see CREDITS.txt).

## Credit

Package system, component geometry and palette adapted from lemo-opuscar "Broadcast News Package" by LemoLab (MIT,
Copyright (c) 2026 LemoLab; LICENSE-lemo-opuscar.txt). The demo film (CC BY 4.0) and its media are not copied.
Details: CREDITS.txt.
