# POV montage: first-person footage cut into a story, with the editorial motion layer on top

Call it with: **"cut these POV clips into a reel"**, **"make a vlog reel from my glasses footage"**.

First made for a first-person scooter ride across a city (smart-glasses footage, 7 clips, 13 min → 50 s).

**When to use:** several clips from smart glasses, a GoPro or a phone, a day or a trip, with a few spoken lines and moments.

## The grammar

1. **Find the story first.** Order clips by creation time; contact sheets at 1 frame/4–8 s; transcribe everything (whisper small, then
   medium on the lines you keep, then Gemini 2.5 Pro to confirm); ask the user for the moment they remember ("someone tried to hit me").
   A flash-forward hook from the end (a line like "39 minutes left and I'm late") + a "15 minutes earlier" rewind works.
2. **One edit list (edl.json):** clip, source in/out, speed (1 for speech, 2–3× for riding), audio (voice / amb −14 dB / mute),
   and `freeze` segments (a held frame, silent). `assemble.py` crops 3:4 glasses footage to 9:16 (1647×2928 → 1080×1920, no upscale),
   bakes the speed-ups and writes one talk.mp4 + edl_map.json.
3. **Captions from verified source word times** (`gen_words.py`): words typed once with their source times, mapped through edl_map.json,
   so re-cuts keep them right.
4. **Motion layer = the editorial preset with an accent that fits the footage** (lime #A6FF00 with `brand.onAccent: "#111"`):
   - kinetic hook scene, dark background, white filler words, `pip` window, `pullback` short so the last word isn't covered
   - fly3d "15 minutes earlier / 13:24 / place" rewind with a glitch in
   - `behind` text on the one selfie (needs `matte: true`; delete assets/talk-matte.webm after every re-cut)
   - a cursor-click `card` for the fun fact and `stats` badges for times
   - B-roll stills from your own unused 4K frames (`image` scene), never 720p stock
5. **The moment:** freeze frame (1.4 s) + 1.3× zoom + record scratch + an emoji over a stranger's face (also anonymises them),
   then the line, then a reaction meme 2–3 s later. Music ducks to almost nothing under the freeze.
6. **Music** (life-is-a-dream for a sunny ride) with `music.duck` windows on every spoken line.

**Public edition note:** the reaction meme and the record-scratch sound in step 5 come from a private meme kit that is not
redistributed. Add your own clip with `scripts/meme_add.py` (only media you have the rights to) and use a Mixkit sound such as
`impact-1` or `whoosh-cine` for the freeze. The worked example does that: `impact-1` on the freeze and a Mixkit reaction sound
(`reaction-fail-trombone`) where the meme would go.

## Formats (worked example in example/: edl.json, assemble.py, gen_words.py, reel.json, script.txt)

- **edl.json:** `{"segments": [...]}` in edit order. A segment is `{"clip": "<id>", "a": <source in, s>, "b": <source out, s>,
  "speed": 1, "audio": "voice" | "amb" | "mute", "note": "..."}`; a freeze is `{"clip": "<id>", "freeze": <source s>, "dur": 1.4,
  "audio": "mute", "note": "..."}`.
- **assemble.py** (write it per project, with the clip id → source file map at the top): each segment cut to a whole number of
  30 fps frames in both picture and audio (source edges snapped to the frame grid, so the concat cannot drift), 3:4 clips
  centre-cropped to 9:16, speed-ups baked in (chained `atempo` above 2×), voice segments high-passed and lightly denoised at full
  level, ambience 14 dB down, speed-ups silent, the whole program normalised to −16 LUFS (two-pass loudnorm, TP −1.5).
  Writes assets/talk.mp4 and build/edl_map.json: per segment `i`, `clip`, `src_a`, `src_b`, `speed` (0 for a freeze),
  `edit_start`, `edit_end`, `note`.
- **gen_words.py:** the kept lines typed once as `(clip, [(word, source start, source end), ...])`, mapped to edit time through
  build/edl_map.json (words whose source moment is not in the cut are skipped), written as build/words.fixed.json
  (whisper-style `segments[].words[]` with `word`, `start`, `end`).
- **reel.json:** `"style": "editorial"`, `"source": "assets/talk.mp4"`, `"words": "build/words.fixed.json"`, `"matte": true`
  (for `behind`), a `brand` block (`accent`, `accentDark`, `ink`, `onAccent`, `capSize`, `font`), one take over the whole
  pre-assembled montage (`"takes": [{"a": 0, "b": <length>}]`), `zoom.pushes` for the moment, `captions` (`group`, `y`,
  `highlight`), `music` with `duck` windows, and `beats`: scenes of kind `kinetic`, `fly3d`, `image`, `card`, `stats`, plus
  `behind`, `emoji` and `meme` beats.

## Pipeline

```bash
S=~/.claude/skills/ghost-editor; P=~/reels/<name>
# proxies + sheets + transcripts (see SKILL.md step 1-2); write $P/edl.json (format: example/edl.json)
cp $S/recipes/pov-montage/example/{assemble.py,gen_words.py} $P/   # edit SRC / PHONE at the top of assemble.py
cd $P && python3 assemble.py && python3 gen_words.py              # gen_words: type the kept lines with source word times
python3 $S/scripts/face_track.py assets/talk.mp4 --out build/face.json
# reel.json: start from example/reel.json (style editorial + brand + beats), then
node $S/scripts/build.mjs $P && $S/scripts/hf.sh lint && $S/scripts/hf.sh snapshot --at <every beat>
$S/scripts/hf.sh render -o build/reel.mp4 && python3 $S/scripts/qa.py $P build/reel.mp4
```

## Checks that caught real problems

- Mixkit's San Francisco clips are 720p and personal-use only: rejected. Your own 4K frames make better B-roll.
- The QA SFX stem used to include the music bed, so loud music read as loud effects (fixed in qa.py).
- Two meme sounds 5 s apart break the 8 s guideline; keep both only when they are the joke, and say so.
- The person cut-out (matte) is cached: after any re-cut delete it, or old cut-outs float over new footage.
- Speed-ups above 2× need chained atempo filters (assemble.py does it).

## Worked example

`example/` holds an English montage, "lost my lunch to a seagull": a seaside walk in first person, five smart-glasses clips
and one phone selfie cut by `edl.json` into 14 segments (39 s + a 2 s outro): the flash-forward hook as a `kinetic` scene
with the speaker in a round window, a `fly3d` "20 minutes earlier / 12:40 / the pier" rewind with a glitch in, a `behind`
word on the selfie, an `image` scene from a still of the speaker's own unused footage, a cursor-click `card` for the fun
fact, `stats` badges for the times, the moment (the gull dives in, a 1.4 s freeze with a 1.3× push, `impact-1` and an emoji
over the gull), the reaction sound right after the line and a comment-prompt end card; editorial captions (`group` 4, two
`highlight` words), `happy-times` ducked under every spoken line, `sfxProfile: "restrained"` (7 hits, about 10 a minute).
`script.txt` lists the seven spoken lines with their clip and source seconds. It is for reading and copying: the clips are
yours to supply. Map your files in `assemble.py` (`SRC`, `PHONE`), re-time `edl.json` and the words in `gen_words.py` from
your own sheets and transcripts, then every beat time in `reel.json` (they are edit times on the assembled montage,
build/edl_map.json). Editorial captions pair lines two by two across the whole reel (a `tags` pill heads a block of up to
three), so a sentence with an odd number of lines hands its last line to the next sentence's block, and it stays on screen
through a mute montage in between: check each `eblock`'s `data-start`/`data-duration` in index.html, and keep every sentence
an even number of lines with `group` and the commas you type in gen_words.py (the example puts a comma after "seaside" for
that). A dry run (test-pattern clips with a synthetic voice; whisper times typed into gen_words.py) assembles, builds
(BiRefNet matte for the behind word) and lints with 0 errors; it has not been rendered with real footage.
