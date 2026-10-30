# Hologram HUD

A talking-head reel cut between the speaker's face as shot and full-screen HUD scenes. The thing the speaker talks about (a phone, a book,
the habits they list) is scanned into a glowing line wireframe on a projector pad. Target boxes lock onto its parts,
values roll in from garbage glyphs and turn amber on the frame they become true, and finished values dock as toggle chips
in a rail that stays to the end. One interface covers both worlds: the edge chrome and the HUD subtitle sit on the speaker's face
shots too, never on the speaker's face. Ported from Lemo-Opuscar "Sci-fi Hologram HUD" (MIT, LemoLab), see CREDITS.txt.

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog).
house.json holds the fixed look. catalog.json records what each reel used.

## Calls

- "Hologram HUD"
- "hologram reel", "HUD style", "like the e-bike spec scan"

## What it needs

The approved cut: one or more plates of the same timeline (assets/wide.mp4, tight.mp4, alt.mp4), assets/voice.wav and
build/words.cut.json (edit seconds). It needs no matte, because nothing ever sits over the speaker's face. Each HUD scene needs an
object for the spoken noun, built as a wireframe model in engine/holohud.js (MODELS: phone, book, basics; add new ones with
rr / piece / cylX / place). It can use at most one real printed object (a book cover), drawn on the wireframe in its own
colour. Fonts (Exo 2 from fonts/, JetBrains Mono from templates/fonts) and SFX (library, licensed only) are copied by the
builder. There is no music bed.

## Build

The Python builder is `hologramhud.py` (class `Hud`, scenes from `Hud.scene()`; its docstring lists every call). The
engine `engine/holohud.js` is inlined into index.html: one canvas painted from a paused GSAP timeline (seek-safe, no
timers). The public edition has no worked example for this recipe yet: write the reel's build.py from the usage block
in hologramhud.py's docstring (`python3 hologramhud.py` prints it), SYSTEM.md (slots, planning procedure) and the catalog,
then

```bash
S=~/.claude/skills/ghost-editor; PY=~/.venvs/media/bin/python
$PY $P/tools/build.py                          # index.html, build/beats.json, build/coverage.txt
bash $S/scripts/hf.sh lint $P                   # 0 errors (one warning: the file is long, the engine is inlined)
bash $S/scripts/hf.sh snapshot $P --at <beat times> --no-end --describe false   # look at every beat
$PY $S/scripts/finals.py preview $P --out $P/finals --style "Hologram HUD" --code R01 --title "..."   # WAIT for the user's OK
```

The calls are `face()`, `scene()`, then on a scene `obj()`, `cam()`, `lock()`, `card()`, `marker()`, `title()`, `status()`,
`beam()`, `pad_spin()`. On the reel: `chip()`, `sub()`, `glitch()`, `image()`, `sfx()`, `build()`.

## Credit

Adapted from Lemo-Opuscar styles/hologram-hud (https://github.com/lemomo-ai/lemo-opuscar), MIT, Copyright (c) 2026
LemoLab: the STYLE.md spec and the holo.js / hud.js engine code. The licence is in LICENSE-lemo-opuscar.txt. Their demo
film and models are not copied.
