# Clean OS: talking head edited like an Apple ad that lives inside your phone

Call it with: **"edit this in Clean OS"** (or "Clean OS style").

**Read SYSTEM.md first.** This README is the first reel's grammar; SYSTEM.md is the logic (invariants, slots, generators)
and catalog.json records every element used. A new reel fills each slot with something NEW; copying a previous reel's
scenes is the known failure (it reads as the same edit).

The look was reverse-engineered from @yashmotions' Apple-style clean talking-head edit.

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
   Photos "Memories" card. Enter 0.26 s rise + tech-digital-whoosh; exit 0.18 s fade. iOS blue #0A84FF, black #111.
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
S=~/.claude/skills/ghost-editor; R=$S/recipes/clean-os; P=~/reels/<name>
# 1. look + transcribe the RAW (all takes); pick the best COMPLETE take per line (watch for false starts: confirm with Gemini)
python3 $S/scripts/transcribe.py proxy.mp4 --out $P/build/words.whisper.json --lang <code> --model turbo
python3 $S/scripts/face_track.py proxy.mp4 --out $P/build/face.json          # median eyes -> cut.json "eyes"
# 2. denoise (outdoor noise): DeepFilterNet3 capped at 20 dB (full strength = thin, watery voice)
.venv-df/bin/deepFilter audio/raw.wav --atten-lim 20 -o audio/df20      # venv: the first run of scripts/denoise.sh creates $S/.venv-df
# 3. write $P/cut.json (see assemble.py docstring), then:
python3 $R/assemble.py $P
#    many takes of a script: plan the cut first (references/take-selection.md, "The raw cut, step by step"):
#    python3 $S/scripts/plan_cut.py $P && python3 $R/assemble.py $P --plan $P/build/plan.json --alt
#    The plates are never graded (the speaker's face as shot); the old default grade is gone.
python3 $S/scripts/transcribe.py $P/assets/voice.wav --out $P/build/words.cut.json --lang <code> --model turbo
python3 $R/fetch_fonts.py $P
# 4. write $P/reel.py on the builder (SYSTEM.md section 4): python3 $R/cleanos.py --api lists every call; the project
#    from an approved cut: python3 $R/cleanos.py --new $P --from <cut dir>. Everything is keyed to words: R.t("word").
#    (example/build_one_thing.py is a hand-written build of an English example: read it for ideas, never copy it.)
#    A Markup pen word needs its font: python3 $R/fetch_fonts.py $P "Marck Script".
cd $P && python3 reel.py && $S/scripts/hf.sh lint && python3 $S/recipes/seoul-list/snap.py beats $P   # look at build/snaps/overview.jpg
python3 $S/scripts/finals.py preview $P --out $P/finals --style "Clean OS" --code <C> --title "<title>"   # WAIT for the user's OK
```

## Checks that caught real problems

- Hiding every flagged frame hides the speaker: in one audit, a reel that covered 31 off-lens windows kept the speaker on
  screen 33 % of the reel. Small glances stay (plan_cut.py / cover_windows.py now say keep or cover per window). Inserts
  are graded onto the plate with insert_prep.py and kept to <= 3 per minute. Scenes open from an icon below the chin,
  never over the speaker's mouth. Run `broll_qa.py --project $P` on every render (references/broll.md).

- Raw whisper merges a false start with its restart ("And even the… And even the thing that now…"): re-transcribe the cut voice.
- A "khm" before a word: find it with a voicing/pitch scan (a voiced hum with falling pitch), not by asking Gemini.
  Gemini's sub-second timestamps are unreliable.
- Speakers often bow their head or close their eyes right AFTER a take's last word. Check every take's tail in close-up frames
  (a head-pose scan from face landmarks does not see an eyes-down glance), end the take at the word, and when a phone scene
  covers the cut, end the scene's fade over the NEXT shot (scene out = next segment start + 0.2 s), not over the tail.
- Gemini's visual QA called the cut "clean" while the bow was visible; trust frames over its verdict. Its audio flags need
  checking too: a "breath" it reported was an unvoiced fricative inside a word (voicing scan: unvoiced, high zero-crossing
  between vowels).
- Never use a bare `tl.to()` on something animated twice; use fromTo with explicit values (seek order changes the result).
- `.strike` on non-deleting boxes: render the element only when it's used (the lint rejects CSS transform + GSAP scale).
- Every `<video>` needs an id, including decorative blurred copies (otherwise it renders frozen).
- 4K HEVC select-by-time assembly takes ~4 min per framing; delete assets/{wide,tight}.mp4 to force a rebuild.
- Lip sync: assemble.py snaps every segment edge to the 30 fps grid and cuts the picture and the voice at the same snapped
  times, then checks frames == round(voice seconds x 30). Before that fix, a 23-piece cut rounded each piece of the picture
  to whole frames while the voice was cut at exact times: the picture ran 2 frames long and the voice ended 43-54 ms early.
  An older cut: `python3 $S/scripts/qa.py $P <any render> --av-only` flags it; `python3 $S/tests/test_assemble_sync.py`
  is the regression test.

## Worked example

`example/build_one_thing.py` with `example/script.txt` and `example/cut.json`: an English monologue, "one thing at a time"
(9 lines, about 32 s), built in the current house look (house.json), not the first reel's: Inter cards resolving from blur
on the chest, the red Figma box twice rejecting ("more time", "not forever") and once focusing, QuickType suggestions
tapped up into the card on two choice words, the Markup pen writing "feeling" in Marck Script, a green accent. Its
components: four OS moments (a home screen whose badges count up on 32 / 11 / 3, the app switcher flicking every card away
but one, a chest window with a timer wheel rolling to 25 and a notifications toggle switching off, a checklist with one
item done and ten started), the scenes growing out of the Dynamic Island and shrinking back, an "attention" battery
beside the head draining across its sentence; a small sound on every entrance and the `vastness` bed. A new reel keeps the
house and replaces those components. It is for reading (a new reel is written on the builder, not copied from
it) and for a test run: the recording is yours to supply. Put your file in
cut.json `source`, re-time `segments` from your own transcript, run assemble.py, transcribe `assets/voice.wav` with
`--lang en`, then fix any word key the build stops on (whisper writes "10" for "ten": keys accept `"ten|10"`). A dry run
(a test-pattern 4K source with a synthetic voice and a false start, cut by assemble.py, words from whisper on the cut voice)
builds and lints with 0 errors and 0 warnings; it has not been rendered with real footage.
