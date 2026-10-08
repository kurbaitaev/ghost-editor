# Clean OS: talking head edited like an Apple ad that lives inside your phone

Call it with: **"edit this in Clean OS"** (or "Clean OS style", "like One Normal Day").

First made for "Один обычный день" (C007, Oct 2026): ~/EXPERIMENTS/reel-c007. The look was reverse-engineered from @yashmotions'
"Apple-style clean talking-head edit" (IG DUQzZ_kE3O7): breakdown in reel-c007/BREAKDOWN.md, open-source sources in
reel-c007/research/OPEN-SOURCE.md.

**When to use:** reflective or explanatory monologues where each sentence names something the viewer can *see on a phone*
(a date, a notification, a search, a photo, a message). Calm-to-medium energy. Not for hype or meme content.

## The grammar (keep all of it)

1. **Two shot sizes from one 4K camera.** Wide = the full frame; tight = a 1.6× crop around the face (1350×2400 → 1080×1920,
   downscale only). Switch at phrase changes every 2–4 s; each shot has a slow push (1.00→1.05). The cut to wide gets a soft whoosh.
2. **Word cards, not subtitles.** 1–3 words at a time, centred on the chest (y≈1250), lowercase, Inter. Entry: blur 14→0 px,
   scale 0.82→1, 0.22 s, power3.out. Exit: 0.12 s blur-out. Sizes: s 64/600, m 96/700, it 170 italic 700, xl 230/800,
   stack 130 (2nd line italic 300), xl-sub (hero 300/800 + thin italic sub-line 46/300). Tracking −0.03 to −0.06 em.
   A quiet pop on every card (pop-1/2/3 at 0.05–0.07).
3. **Literal phone scenes on #FAFAFA** (speaker hidden, voice continues), 3–4 per 40 s, each illustrating exactly the sentence:
   date picker wheel, lock screen with notifications landing on the words, search bar typing + a loading bar that stalls,
   Photos "Воспоминания" card. Enter 0.26 s rise + tech-digital-whoosh; exit 0.18 s fade. iOS blue #0A84FF, black #111.
4. **Red Figma selection box.** rgba(239,68,68,.38) fill, 3 px #EF4444 border, white corner handles, dashed full-width guides,
   a "Text" label tag, a macOS cursor flying in from bottom-right and clicking (click-1). For words the speaker *rejects*:
   add the strike line and dim them. For words to *focus on*: select only.
5. **One "data" moment:** perspective text over the horizon (rotateX 28°, 3 lines, last one 190 italic 800) plus a white ring
   draining 100→0 % beside the head.
6. **One script word:** Great Vibes, 300 px, wiped in left→right with a thin italic sub-line.
7. **Sound:** a small sound on every graphic entrance (pop, tick, click, keyboard, notification/ding, shutter, ui-confirm),
   nothing on bare cuts. Ambient bed (`vastness`) at volume 0.16. Final −14 to −16 LUFS, TP ≤ −1.
8. **Colour:** keep the footage's own mood (dusk stays dusk); only clean it (contrast 1.05, saturation 0.92, slightly cool).
   The white phone scenes give the "Apple" contrast. Soft dark fade on the bottom 45 %.

## Pipeline

```bash
S=~/.claude/skills/ghost-editor; R=$S/recipes/clean-os; P=~/EXPERIMENTS/reel-<name>
# 1. look + transcribe the RAW (all takes); pick the best COMPLETE take per line (watch for false starts: confirm with Gemini)
python3 $S/scripts/transcribe.py proxy.mp4 --out $P/build/words.whisper.json --lang ru --model turbo
python3 $S/scripts/face_track.py proxy.mp4 --out $P/build/face.json          # median eyes -> cut.json "eyes"
# 2. denoise (outdoor noise): DeepFilterNet3 capped at 20 dB (full strength = thin, watery voice)
.venv-df/bin/deepFilter audio/raw.wav --atten-lim 20 -o audio/df20      # venv setup: memory deepfilternet-denoise
# 3. write $P/cut.json (see assemble.py docstring), then:
python3 $R/assemble.py $P
python3 $S/scripts/transcribe.py $P/assets/voice.wav --out $P/build/words.cut.json --lang ru --model turbo
python3 $R/fetch_fonts.py $P
# 4. copy example/build_one_normal_day.py to $P/build.py and rewrite its PLAN parts for the new script
#    (shots, cards, UI scenes, figma(), persp/ring, script word, sfx). Everything is keyed to words via W("word", n).
cd $P && python3 build.py && npx hyperframes lint && npx hyperframes snapshot --at <every beat>
npx hyperframes render -o renders/<name>.mp4
```

## Checks that caught real problems

- Raw whisper merges a false start with its restart ("И даже то, что… И даже то, что сейчас…"): re-transcribe the cut voice.
- A "khm" before a word: find it with a voicing/pitch scan (a voiced hum with falling pitch), not by asking Gemini.
  Gemini's sub-second timestamps are unreliable.
- Speakers often bow their head or close their eyes right AFTER a take's last word. Check every take's tail in close-up frames
  (a head-pose scan from face landmarks does not see an eyes-down glance), end the take at the word, and when a phone scene
  covers the cut, end the scene's fade over the NEXT shot (scene out = next segment start + 0.2 s), not over the tail.
- Gemini's visual QA called the cut "clean" while the bow was visible; trust frames over its verdict. Its audio flags need
  checking too: a "breath" it reported was the щ inside "ощущалось" (voicing scan: unvoiced, high zero-crossing between vowels).
- Never use a bare `tl.to()` on something animated twice; use fromTo with explicit values (seek order changes the result).
- `.strike` on non-deleting boxes: render the element only when it's used (the lint rejects CSS transform + GSAP scale).
- Every `<video>` needs an id, including decorative blurred copies (otherwise it renders frozen).
- 4K HEVC select-by-time assembly takes ~4 min per framing; delete assets/{wide,tight}.mp4 to force a rebuild.
