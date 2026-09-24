---
name: ghost-editor
description: AI video editor for talking-head reels. Turns a raw phone recording of someone talking to camera (retakes, pauses, false starts) into a finished vertical 1080x1920 reel for Instagram, TikTok or Shorts: best take of each sentence, pause trimming, word-timed captions that never cover the face and stay inside the platform safe area, motion scenes on the spoken word, sound effects and music mixed against the voice, in seven styles (clean, editorial, meme, cinematic, launch, kinetic, pop). It can also reverse-engineer a reference edit the user likes and apply that style to their recording. Use when the user hands over a talking-head video and says "edit this", "make a reel", "make it look like this video", "add captions/motion graphics/sound effects", "pick the best takes", "remove the pauses", or asks for a re-cut. Not for landscape screen recordings.
---

# ghost-editor

One recording in, one reel out. The creative work is choosing takes and
planning beats. The scripts do everything else the same way every time: cut
math, zoom tweens, captions, SFX levels, asset copying, QA. Nothing on
screen says anything the speaker did not say. A meme is a reaction, so it
lands ON or just AFTER the punchline, never before it.

Skill dir: `~/.claude/skills/ghost-editor` (below: `$S`). A reel project is any
directory (`$P`); `build.mjs` copies what it needs into `$P/assets` so the
project renders on its own.

## Pipeline

```
prep.sh        -> $P/assets/talk.mp4        1080x1920 30 fps, voice at -16 LUFS
transcribe.py  -> $P/build/words.whisper.json + take table (all takes)
face_track.py  -> $P/build/face.json          (captions and cards never cover the face)
choose takes   -> $P/reel.json takes        (references/take-selection.md)
plan beats     -> $P/reel.json beats/zoom   (references/reel-json.md)
build.mjs      -> $P/index.html             + SFX table + rule warnings
lint + snapshot, look at the frames
render         -> $P/build/reel.mp4
qa.py          -> levels, SFX-vs-voice on a stem, silences, contact sheet
deliver        -> ~/Desktop/<name>-reel.mp4
```

### 0. Check the toolchain once per session
`bash $S/scripts/doctor.sh`: tools, GEMINI_API_KEY and the media library,
each with its fix. On a fresh machine run `python3 $S/scripts/library_restore.py`
first (SFX, memes and music aren't in git). Say what is missing; don't
improvise around it.

### 1. Prep and look
```bash
bash $S/scripts/prep.sh <IMG_xxxx.MOV> $P
ffmpeg -v error -i $P/assets/talk.mp4 -vf "fps=1/10,scale=216:384,tile=6x3" -frames:v 1 -update 1 $P/build/sheet.jpg
```
Look at the sheet. Check that it is the right person (show the frames
and confirm with the user when there is any doubt). Note where the face
sits (the zoom origin, default `50% 29%`), where the chin is (the card band
starts at y 990), and how bright the wall is.

### 2. Transcribe everything
```bash
python3 $S/scripts/transcribe.py $P/assets/talk.mp4 --out $P/build/words.whisper.json --lang en
```
The table is the take map in original seconds; `*` marks restart phrases
("okay, again"). Fix mangled names later in `captions.fixes`.

### 2b. Track the face
```bash
python3 $S/scripts/face_track.py $P/assets/talk.mp4 --out $P/build/face.json
```
Always. The build places captions, cards and reactions around the face, inside the platform's safe area.

### 3. Choose takes (`references/take-selection.md`)
Ask for the script if there is one. Pick the take of each sentence that is
fluent and later, keep one-breath runs as one take, and cut on WORD times:
`a` = first word - 0.10..0.15, `b` = last word + 0.20..0.30. When a meme
will follow a line, end that take 0.6 to 1 s after the last word so the
meme sound has air. Aim for 45 to 75 s.

### 3b. A single clean take?
If the recording is already one good take, don't pick takes by hand:
`python3 $S/scripts/autocut.py $P/assets/talk.mp4 --noise -30` prints `takes` with the pauses removed.

### 4. Pick a style, plan beats (`references/styles.md`, `references/reel-json.md`)
Seven presets: `clean`, `editorial`, `meme`, `cinematic`, `launch`, `kinetic`, `pop`.
Ask the user which one (show `examples/gallery/` or the showcase video) or pick by
the speaker's energy. Start from `examples/gallery/<style>.reel.json`.
To match a reference edit: `python3 $S/scripts/reference_study.py <their-edit.mp4> --out <dir> [--raw <raw>]`
writes a 1 fps contact sheet, full-res frames every 2 s and Gemini 2.5 Pro's
second-by-second edit log with a mapping onto our beats. Treat the log as a
draft: verify type, sizes and framing against the frames. Then map every scene
to a word time. Start from the closest file in `examples/`.
Walk the transcript sentence by sentence. For each one, ask what the speaker
just made the viewer imagine, and show it on the word. Leave some sentences bare;
silence in the band makes the next card land. Memes: 1 to 3 per minute, on
punchlines, from the library:
```bash
python3 $S/scripts/meme_find.py "the line with the punchline"
python3 $S/scripts/meme_find.py --list
```
If the library has nothing that fits, say so and offer to add one (step 9).
Don't force a meme.

### 5. Build
```bash
node $S/scripts/build.mjs $P
```
Read its output: the edit timeline (a missing word means a cut inside it),
the caption text, the SFX table (time, sound, role, volume, why) and the
WARNINGS. Fix every warning in reel.json or explain why it stays.

### 6. Lint and look
```bash
cd $P && npx hyperframes lint          # must be 0 errors; sub-composition/track-density warnings are fine
npx hyperframes snapshot --at <edit seconds of each beat landing, each cut, the end card>
```
Edit seconds = the take's edit start (printed) + (original t - take a).
Look at `snapshots/contact-sheet.jpg`: cards on the chin, text wrapping,
the meme clipped by the frame edge, captions colliding with a card.

### 7. Render and QA
```bash
npx hyperframes render -o build/reel.mp4 --quiet
python3 $S/scripts/qa.py $P build/reel.mp4
```
QA renders an SFX-only stem and prints each hit's peak against the voice
and its role target. Targets: ui ≈ -14, whoosh -12, impact -8, meme -3 dB
vs voice p95 peak; flags anything louder than the voice or inaudible. It
also checks loudness (-16 ±1.5 LUFS, TP ≤ -0.5), silences > 0.8 s inside
the speech, and writes `build/contact.jpg`. It never adds gain.

### 8. Deliver
Copy to `~/Desktop/<name>-reel.mp4` (plus a 720p preview under 30 MB if
asked). Handover: the takes chosen (original seconds and why), the beats and
memes in plain words, the SFX count per minute, anything QA flagged, and the
obvious follow-ups (music from the platform's library at post time, a
different meme, the URL for the end card).

### 9. Library work
```bash
python3 $S/scripts/trends.py                 # what's new on imgflip / Know Your Meme, what we lack
python3 $S/scripts/meme_add.py <id> <url|file> --tags ... --use ... --triggers ... --trend hot
python3 $S/scripts/sfx_fetch.py --only <id> --force   # after editing KIT in sfx_fetch.py
python3 $S/scripts/audition.py --open         # soundboard + meme wall for a human listen
```
Always look at a new meme's `preview.png` before using it. Sounds with a
`review` flag in the manifest have not been confirmed by ear.
`references/sound-and-memes.md` has the mixing reasoning, sources, licences
and the dead ends not to retry.

## Rules that came from getting it wrong

- Transcribe the whole recording; choose takes from the table, never by scrubbing.
- Cut on word times, never whisper segment times.
- Snap zooms, not crossfades, between takes of the same sentence.
- Voice loudness is fixed in prep, before SFX. Never lift the finished mix.
- SFX level is relative to this voice (build measures it). Never hand-tune `data-volume`.
- A meme sound never sits on top of a word. Give it a pause.
- No meme sound twice in one reel. Meme sounds: 1 to 3 per minute.
- One card in the band and one thing in the reaction slot at a time.
- No em dashes in on-screen text.
- Meme sounds and green-screen clips are unlicensed rips: fine for IG and
  TikTok, not for YouTube (Content ID). Say so if the user mentions YouTube.

## Files

- `scripts/prep.sh` transcode + voice loudnorm
- `scripts/transcribe.py` whisper (PATH) → words json + take table
- `scripts/build.mjs` reel.json → HyperFrames index.html, SFX mixing and rules
- `scripts/qa.py` render QA with SFX stem level check
- `scripts/sfx_fetch.py` build/refresh the SFX kit (Mixkit + yt-dlp), normalized, manifest
- `scripts/meme_add.py` add a meme clip/still (key, crop, alpha WebM, preview)
- `scripts/meme_find.py` shortlist memes and meme sounds for a line
- `scripts/trends.py` trending meme names not yet in the library
- `scripts/audition.py` HTML soundboard + meme wall
- `scripts/doctor.sh` checks tools, key and library, with fixes
- `scripts/reference_study.py` reverse-engineer a reference edit (sheet, frames, Gemini edit log)
- `references/reference-study-prompt.md` the edit-log prompt (improve it here)
- `examples/` real reel.json files from shipped reels (motion EN, motion RU, memes RU)
- `README.md` install, agent setup (Claude Code / Codex / any agent), quick start
- `scripts/lib/motion.mjs` scenes (card, stats, fly3d, image, sentence), scene transitions, editorial captions, music bed
- `scripts/autocut.py` pause-trimmed takes for a single clean take
- `scripts/broll_gen.py` AI still B-roll with Gemini (9:16), same key as gemini-analyze
- `library/music/` licensed music beds + manifest
- `library/sfx/` kit + manifest.json; `library/memes/<id>/` clips + meta.json
- `templates/fonts/` Geist (OFL)
- `references/reel-json.md` the spec and beat types
- `references/take-selection.md` choosing takes (adapted from mariagorskikh/talking-head-reel, MIT)
- `references/sound-and-memes.md` mixing, sources, licences, dead ends
