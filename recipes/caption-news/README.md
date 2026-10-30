# Caption News

Social-video news that reads with the sound off, on a talking head. The speaker's face as shot is the ground; huge
captions are the lead actor, slammed in 2-3 chunks on the word onsets, one keyword per caption on a honey block that
wipes left to right; the hook lands on frame 4; a title sting (a honey ruled page over the bottom band) becomes the
channel bug; when the speaker names a source, a document beat on a dark desk with highlighter sweeps, the title re-set in a honey
block and a source tag; lists become a lit grid or a ruled list on the ledger sheet. Ported from the MIT-licensed
lemo-opuscar style "Caption News" (styles/caption-news, demo "The Bee Ledger") and adapted to a vertical talking head.

Read SYSTEM.md first; house.json is the fixed look, catalog.json what each reel used.

## Calls

- "Caption News"
- "news captions", "like a news short", "sound-off news"

## What it needs

The cut: assets/tight.mp4 (+ wide.mp4) as shot on one timeline, assets/voice.wav, build/words.cut.json (edit seconds).
For a document beat, the source itself (a cover, a page, a screenshot of the real document) at a size it can be shown at
1:1 or less. No matte (captions sit under the speaker's chin), no stock footage, no music. Fonts (Inter Tight, OFL) and SFX
(library/sfx, licensed only) are copied by the builder.

## Build

The public edition has no worked example for this recipe yet: write the reel's build.py from the usage block in
captionnews.py's docstring (`python3 captionnews.py` prints it), SYSTEM.md (slots, planning procedure) and the catalog, then

```bash
S=~/.claude/skills/ghost-editor; PY=~/.venvs/media/bin/python
$PY $P/tools/build.py                       # index.html, build/beats.json, build/coverage.txt (checks every word is shown)
bash $S/scripts/hf.sh lint $P               # 0 errors (nested-structure warnings are expected)
bash $S/scripts/hf.sh snapshot $P --at <beat times> --no-end --describe false   # look at every beat
$PY $S/scripts/finals.py preview $P --out $P/finals --style "Caption News" --code R01 --title "..."   # WAIT for the user's OK
```

Builder: `captionnews.py`, class `News` (docstring lists every call): `plates()`, `cap()` (the caption card, hook=True for
frame 4), `sting()` (title page -> bug), `doc()` (the document says it, with `source()`), `grid()` (lit grid),
`ruled_list()`, `sfx()`, `build()`. Measuring writes build/ttf once with a Python that has fontTools + brotli (falls
back to ~/.venvs/ghost-captions).

## Credit

Adapted from lemo-opuscar by LemoLab (https://github.com/lemomo-ai/lemo-opuscar, styles/caption-news), MIT licence,
Copyright (c) 2026 LemoLab: see CREDITS.txt and LICENSE-lemo-opuscar.txt.
