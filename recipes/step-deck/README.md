# Step Deck

A tips reel as a numbered deck over a talking head: every spoken word lands on its onset, sized by importance and set
behind the speaker's head; between face shots the reel cuts every 1-2 s to flat full-screen cards (navy word cards,
white word pages, a cream icon card, B&W paper prints of the line's objects, line drawings); a hook stack of the first
three lines in three worlds; one step card per tip with a giant italic numeral that shrinks into place (navy,
off-white, electric blue); a flat ending with at most one gradient word. From a reel by @ant.lon, replicated frame by
frame.

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog);
house.json is the fixed look, catalog.json what each reel used.

## Calls

- "Step Deck"
- "like the ant.lon reel"
- "steps reel"

## What it needs

An approved cut with a list in it (2-5 steps or tips): the plates as shot (wide + tight best), a matte per plate
(`scripts/matte.py` -> assets/<plate>-matte.webm, so the words hide behind the speaker's head), assets/voice.wav,
build/words.cut.json (edit seconds), build/cover_windows.json. Pictures made per line: B&W object stills for one
montage (`broll_gen.py`, no people), at most one metaphor clip (`broll_fetch.py`, 1080p or better), line drawings in
SVG. Fonts, SFX and the bed are copied from the skill by the builder.

## Build

A Python builder, `stepdeck.py` (class `Deck`; its docstring lists every call), reading the look from house.json.
A reel is a short generator in the project that calls it. The public edition has no worked example for this recipe
yet: write $P/tools/build.py (an argparse script taking --project) from the usage block in stepdeck.py's docstring, build/plan.txt and SYSTEM.md, then

```bash
S=~/.claude/skills/ghost-editor; PY=~/.venvs/media/bin/python
$PY $P/tools/build.py --project $P             # index.html, build/beats.json, build/coverage.txt
bash $S/scripts/hf.sh lint $P                   # 0 errors
bash $S/scripts/hf.sh snapshot $P --at <beat times> --no-end   # look at every beat on one sheet
python3 $S/scripts/components.py check --style step-deck --project $P
$PY $S/scripts/finals.py preview $P --out $P/finals --style "Step Deck" --code R01 --title "..."   # WAIT for the user's OK
$PY $S/scripts/finals.py render $P --out $P/finals --style "Step Deck" --code R01 --title "..."    # only after the user's yes
```

The calls: `face()` (the face, captions behind the head; push / fade / pushin / punch), `navy()`, `page()` (exit to
white), `card_words()`, `montage()` + `make_prints()`, `disk()`, `title()`, `panel()`, `broll()`, `step()`,
`push_out()`, `counter()`, `keyword()` (the gradient outro word), the motion helpers `pop_in()`, `jump()`, `rack()`,
`box_grow()`, `blur_out()`, then `plates()`, `sfx()`, `build()`. Caption specs are strings: `"B T +T /ST Sf"`.

## Where things are

- The reference: a "hook stacking" tutorial reel by @ant.lon (55 s), studied frame by frame; the study's element and
  transition labels (E1-E29, X1-X9) are kept in stepdeck.py, house.json and catalog.json as names for the devices.
