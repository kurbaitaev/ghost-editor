# POV montage: first-person footage cut into a story, with the editorial motion layer on top

Call it with: **"cut these POV clips into a reel"**, **"like the Lime ride"**, **"make a vlog reel from my glasses footage"**.

First made for the San Francisco Lime ride (Oakley Meta HSTN glasses, 7 clips, 13 min → 50 s), Sep 2026: ~/EXPERIMENTS/reel-sf-glasses.

**When to use:** several clips from smart glasses, a GoPro or a phone, a day or a trip, with a few spoken lines and moments.

## The grammar

1. **Find the story first.** Order clips by creation time; contact sheets at 1 frame/4–8 s; transcribe everything (whisper small, then
   medium on the lines you keep, then Gemini 2.5 Pro to confirm); ask the user for the moment they remember ("he tried to hit me").
   A flash-forward hook from the end ("У нас 39 минут, блин, я опоздал") + "15 минут назад" rewind works.
2. **One edit list (edl.json):** clip, source in/out, speed (1 for speech, 2–3× for riding), audio (voice / amb −14 dB / mute),
   and `freeze` segments (a held frame, silent). `assemble.py` crops 3:4 glasses footage to 9:16 (1647×2928 → 1080×1920, no upscale),
   bakes the speed-ups and writes one talk.mp4 + edl_map.json.
3. **Captions from verified source word times** (`gen_words.py`): words typed once with their source times, mapped through edl_map.json,
   so re-cuts keep them right.
4. **Motion layer = the editorial preset with an accent that fits the footage** (lime #A6FF00 with `brand.onAccent: "#111"`):
   - kinetic hook scene, dark background, white filler words, `pip` window, `pullback` short so the last word isn't covered
   - fly3d "15 минут назад / 13:24 / place" rewind with a glitch in
   - `behind` text on the one selfie (needs `matte: true`; delete assets/talk-matte.webm after every re-cut)
   - a cursor-click `card` for the fun fact ("GTA: San Andreas") and `stats` badges for times
   - B-roll stills from your own unused 4K frames (`image` scene), never 720p stock
5. **The moment:** freeze frame (1.4 s) + 1.3× zoom + record scratch + an emoji over a stranger's face (also anonymises them),
   then the line, then a reaction meme 2–3 s later. Music ducks to almost nothing under the freeze.
6. **Music** (life-is-a-dream for a sunny ride) with `music.duck` windows on every spoken line.

**Public edition note:** the example's reaction meme (`doakes-stare`) and `record-scratch` come from a private meme kit that is not
redistributed. Add your own clip with `scripts/meme_add.py` (only media you have the rights to) and use a Mixkit sound such as
`impact-1` or `whoosh-cine` for the freeze.

## Pipeline

```bash
S=~/.claude/skills/ghost-editor; P=~/EXPERIMENTS/<name>
# proxies + sheets + transcripts (see SKILL.md step 1-2); write $P/edl.json (format: example/edl.json)
cp $S/recipes/pov-montage/example/{assemble.py,gen_words.py} $P/   # edit SRC paths at the top of assemble.py
cd $P && python3 assemble.py && python3 gen_words.py              # gen_words: type the kept lines with source word times
python3 $S/scripts/face_track.py assets/talk.mp4 --out build/face.json
# reel.json: start from example/reel.json (style editorial + brand + beats), then
node $S/scripts/build.mjs $P && npx hyperframes lint && npx hyperframes snapshot --at <every beat>
npx hyperframes render -o build/reel.mp4 && python3 $S/scripts/qa.py $P build/reel.mp4
```

## Checks that caught real problems

- Mixkit's San Francisco clips are 720p and personal-use only: rejected. Your own 4K frames make better B-roll.
- The QA SFX stem used to include the music bed, so loud music read as loud effects (fixed in qa.py).
- Two meme sounds 5 s apart break the 8 s guideline; keep both only when they are the joke, and say so.
- The person cut-out (matte) is cached: after any re-cut delete it, or old cut-outs float over new footage.
- Speed-ups above 2× need chained atempo filters (assemble.py does it).
