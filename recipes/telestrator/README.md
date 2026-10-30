# Telestrator

A TV football-analysis segment over a talking head: the speaker's footage plays live, freezes on the word that carries
a finding and gets drawn on (a ring under the hand, marker arrows, a red zone for the space around the speaker, one
label card), always around the face, never on it; yellow slanted wipes cut to dark tactics boards where the object of
the line (a phone, a cup, a book, a list) is played, frozen, rewound and drawn on; a studio packaging on every frame
(corner bug with LIVE / ANALYSIS / REPLAY, a source clock, a matchup bar naming the reel's two sides, a subtitle bar).
Ported from the MIT style "Sports Telestrator" of lemo-opuscar by LemoLab (https://github.com/lemomo-ai/lemo-opuscar,
styles/telestrator).

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog);
house.json is the fixed look, catalog.json what each reel used. CREDITS.txt and LICENSE-lemo-opuscar.txt: the source.

## Calls

- "Telestrator"
- "like a football analysis show"
- "freeze and draw"

## What it needs

The cut as plates (assets/*.mp4, 1080x1920; wide + tight best), assets/voice.wav, build/words.cut.json (edit seconds),
and a matte for each frozen frame only (`scripts/matte.py <plate> -o build/freeze/<plate>_fz-matte.webm --ranges ...`).
A line with an object the boards can play (phone, app, list, book). A real picture only when the speaker names it (a
cover). Fonts (Inter Tight, Oswald, JetBrains Mono: Cyrillic, OFL) and SFX are copied from the skill by the builder.
The packaging words (show name, modes, the matchup's two sides) are in house.json `packaging`: set the matchup for
each reel.

## Build

A Python builder, `telestrator.py` (class `Show` + `Scene`; the docstring lists every call and sketches an English
reel), reading the look from house.json. A reel is a short generator that calls it. The public edition has no worked
example for this recipe yet: write the generator from the plan (SYSTEM.md planning procedure) and the docstring.

```bash
S=~/.claude/skills/ghost-editor; PY=~/.venvs/media/bin/python
mkdir -p $P/build/freeze
~/.venvs/ghost-matte/bin/python $S/scripts/matte.py $P/assets/alt.mp4 -o $P/build/freeze/alt_fz-matte.webm \
    --ranges 3.80-3.95,14.25-14.40,27.75-27.90 --pad 0.1          # only the frozen frames
$PY $P/tools/build.py --project $P                                    # index.html, build/beats.json, build/coverage.txt
bash $S/scripts/hf.sh lint $P                                         # 0 errors
bash $S/scripts/hf.sh snapshot $P -o $P/build/snap --no-end --at <beat times>   # look at every beat
$PY $S/scripts/finals.py preview $P --out $P/finals --style "Telestrator" --code R01 --title "..."   # WAIT for the user's OK
```

Keep the generator's sys.path line pointing at the recipe (`sys.path.insert(0, "<skill>/recipes/telestrator")`),
write the segments from the plan in its docstring, and measure each freeze frame's face box on a full-res still.

The calls: `mode()`, `clock()`, `wipe()`, `flip()`, `subs()`, `sfx()`; scenes `live_scene()`, `freeze()`, `board()`,
`split()` with the drawing grammar `ring()`, `marker()` (solid / dashed), `zone()`, `spot()`, `label()`, `stamp()`,
`chalk()`, `html()`; then `close()` each scene and `build()`.

## Where things are

- Source: lemo-opuscar, styles/telestrator (STYLE.md, DEMO.md, demo/); the film was only watched (not part of the
  recipe).

Credit: style grammar and drawing rules adapted from "Sports Telestrator", lemo-opuscar by LemoLab, MIT licence.
