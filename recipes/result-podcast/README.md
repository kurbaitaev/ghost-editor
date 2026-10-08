# RESULT: a warm podcast-style edit with paper, film and handwriting

Call it with: **"edit this in RESULT style"**, **"like the millennials reel"**, **"loompixual style"**.

First made for «Почему миллениалы ностальгируют» (Oct 2026): ~/EXPERIMENTS/reel-c008. The look comes from @loompixual's
"RESULT" edit (IG DZr7QYDTwQG). Libraries and licences behind it: STYLE-LIBRARIES.md in this folder.

**When to use:** storytelling or nostalgic talking heads, podcast-style monologues, lists of memories or examples where a photo per
idea helps. Warmer and more tactile than Clean OS.

## The grammar

1. **Captions:** one or two words at a time, centred, Inter Tight. Two-tier emphasis: a small line, then one big bold word.
   Key words in Caveat handwriting.
2. **Cards:** navy text cards with film dust; polaroid photo cards; a paper stack whose pictures swap stop-motion; framed B-roll.
3. **Texture:** dust and grain drawn on a canvas seeded per frame (deterministic in render); film-burn light leaks at section turns.
4. **Props for the funny beats:** comic emoji stickers, a REC frame, an incoming-call card with a finger tapping "decline",
   a cursor clicking a dialog, a chat-bubble card.
5. **Cuts:** hide jump cuts with a 0.2 s picture morph-dissolve between lines while the audio hard-cuts. No zoom on every cut:
   at most three comic punch-ins per reel (per-cut zooms were rejected as annoying).

## Pipeline

```bash
S=~/.claude/skills/ghost-editor; P=~/EXPERIMENTS/<name>
# 1. attempt log: Gemini 2.5 Pro over the WHOLE raw take (every attempt, restart and filler, verbatim)
# 2. takes: best take per line, cut only pauses > 0.7 s inside a line, start each line at the voice onset (RMS > -30 dB, no breaths)
cp $S/recipes/result-podcast/example/{takes.py,build.py,gen_broll.sh} $P/ && cd $P && python3 takes.py      # -> build/takes.json
# 3. render a rough cut, transcribe it (build/rough.words.json), audit it verbatim with Gemini 2.5 Pro; fix and re-audit until clean
# 4. B-roll stills / photos for the polaroids and stack (gen_broll.sh), then adapt build.py's beats to the new script
python3 build.py && npx hyperframes lint && npx hyperframes snapshot --at <every beat>
npx hyperframes render -o renders/<name>.mp4
```

## Checks that caught real problems

- Whisper merges restarts ("Миллениалы веч- миллениалы") into a clean sentence and can even invent the script word that was never
  said ("контентом"). The take picker left 6 restarts in until two Gemini 2.5 Pro audits found them all.
- Hide each caption with an explicit `fromTo` placed AFTER its fade-in; a bare `set` inside the fade gets overridden and the caption
  stays on screen.
- Seed the per-frame dust/grain canvas by frame number, never by wall-clock time, or renders won't match previews.
