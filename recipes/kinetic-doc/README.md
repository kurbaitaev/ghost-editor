# Kinetic doc

Black-and-white archive documentary with one red accent: words pop on as spoken in one centred line (a big heavy word
+ small words), pictures arrive as prints, windows and polaroids, punch lines get their own page. One grammar for three
kinds of video: (A) the speaker talking to camera, (B) a voice-over over designed pictures, (C) B-roll only + a voice-over.
Not the `kinetic` reel.json preset (full-screen type on a colour).

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog);
house.json is the fixed look, catalog.json what each reel used. Founded from four reference reels (@lightyear.residency,
@usvchq, @_otsan, @rit2raj_das), measured frame by frame.

## Build

A Python builder on scripts/lib/facereel.py: `kdoc.py` (class `KineticDoc`). A reel is a short generator in the
project that calls it (copy one of the worked examples; they are English and written for reading and copying: the
recording is yours, so re-time every word ref against your own words.json):

| format | example | needs |
|---|---|---|
| A talking head | `example/a_talking_head.py` (a 2-minute-rule tip, ~30 s) | assets/plate.mp4 (as shot), assets/voice.wav, build/words.json, build/face.json (`face_track.py` on the plate), build/cover_windows.json |
| B voice-over + pictures | `example/b_voiceover.py` (attention residue, ~35 s) | assets/voice.wav, build/words.json, assets/pics/ (B&W archive-style stills, `broll_gen.py`, the prompt prefix in the example) |
| C B-roll only | `example/c_broll.py` (walking without headphones, ~30 s) | assets/voice.wav, build/words.json, assets/clips/ (the user's own footage via `own_footage.py find` + `insert_prep.py --no-grade`), assets/pics/ (archive / AI stills) |

```bash
S=~/.claude/skills/ghost-editor
python3 reel.py $P                                   # writes $P/index.html, build/plan.json, beats.json, sfx_events.json
bash $S/scripts/hf.sh lint $P                        # 0 errors
python3 $S/recipes/seoul-list/snap.py beats $P       # look at every beat
python3 $S/scripts/components.py check --style kinetic-doc --project $P
python3 $S/scripts/finals.py preview $P --out <dir> --style "Kinetic doc" --code R01 --title "..."   # WAIT for the user's OK
```

The building blocks (all keyed to word refs, `K.t("word")`, `"word#2"`, `"^word"`):
- `K.picture(id, src, a, b, line, frame="print"|"window"|"full", label=..., push=..., his_face=..., tag=...)`
  (`his_face=True`: footage with the speaker on screen stays in colour)
- `K.burst(id, [(src, at), ..., (src, at, end)], line)`: the one montage burst, hook only
- `K.page(id, a, b, "grey"|"paper"|"type"|"black", [[(text, ref, "s"|"big"|"red"|"serif"[, px]), ...], ...])`
- `K.polaroids(id, a, b, [(src, label, ref), ...], line)`; `K.label(id, a, b, text, at=, sub=, host=)`;
  `K.counter(id, a, b, to, at=, unit=, host=)`; `K.punch(at, target=None)`; `K.swap(...)`; `K.strike(...)`;
  `K.erase("word", at)`; `K.quiet(t)` (no SFX from t: the payoff); `K.mark(tag)` (a slot component's name)
- `K.build(BIG={...}, RED={...}, SERIF={...})`: captions, sound, budgets (A: facereel's; B / C: every moment a scene),
  pace report, the components check.

Looks are baked into files under assets/kd/ (B&W copies, blurred backdrops, page grounds): HyperFrames' capture can
turn black when a page carries many CSS blurs, filters and gradients.

## Calls

- "kinetic doc"
- "black-and-white documentary"
