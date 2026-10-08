# Vector explainer: a narrated story drawn live in one continuous world

Call it with: **"make an animated explainer"**, **"like the tree video"**, **"faceless explainer with a wise voice"**.

First made for "Two Directions" (a tree grows down and up; life lesson), Sep 2026: ~/EXPERIMENTS/reel-tree-roots.

**When to use:** a script or idea with no footage, especially a metaphor or a concept that can be *drawn*:
a process, a contrast (above/below, before/after), a growth story. Parables, life lessons, science explainers.

## The grammar

1. **One world, one camera.** Not a sequence of slides: a single tall SVG world (e.g. sky over soil, a horizon at mid-frame) and a
   camera (`#cam`: translate + scale, origin 0 0) that moves over it. `cam(x, y, s)` centres world point (x, y) at scale s.
   Dives, rises and zooms carry the story (underground for "into darkness", up into a light burst for "breaks through").
2. **The subject draws itself.** Procedural SVG (seeded random, so it's repeatable): paths with `pathLength=1`, stroke-dashoffset 1→0,
   ordered by depth so growth spreads outward. Leaves grow with `attr: {r}` (not scale transforms; the renderer drops those on SVG).
3. **Every beat keyed to a WORD** of the voiceover: `W("word", n)` returns that word's time from voice/words.json. A new voice take = one rebuild.
4. **Headlines:** Playfair Display on soft cream panels (dark panels over dark ground), 84 px, key word in the italic. 5–7 per minute.
   One heavy moment in Montserrat 900 (e.g. "RESISTANCE / PRESSURE / DIRT") with screen shake and booms.
5. **Captions:** editorial reveal: each word rises out of a blur (22 px → 0, 0.3 s) exactly when spoken; Geist 600 lowercase, key words
   in Playfair italic gold; no box, a dark glow; bottom edge at y 1490 (above the Reels UI). Hidden while a headline says the same words.
6. **Labels on the drawing** (roots: "the work in the dark"; fruit: "success") pop with `back.out(2)` on their words.
7. **A closing montage moment** (seasons cycling: snow, blossom, fruit, falling leaves) on the last line, then a held final line.
8. **Look:** paper grain overlay (6–7 %), soft vignette, a warm grade layer after the turning point. Palette: soil #1B1410/#2A1F18,
   root gold #C9A15B, sky cream #F4EAD8, sun #F2B544, leaf greens, fruit #C0392B.
9. **Sound:** ElevenLabs voice (a wise elder: Spuds Oxley `NOpBlnGInO9m6vDvFkFC`), piano bed (silent-descent) at 0.2 that swells
   at the turning point and the end, cinematic SFX on structural moments only (whooshes on camera moves, booms on heavy words,
   rumble riser into the breakthrough, cine hit on it). Final −15 LUFS, TP ≤ −1.

## Pipeline

```bash
S=~/.claude/skills/ghost-editor; P=~/EXPERIMENTS/<name>
# 1. tighten the script (~115 words ≈ 60 s at an elder's pace); fact-check it; write "..." where the voice should breathe
# 2. voiceover with word timings (2 takes, pick by ear)
python3 $S/scripts/tts_elevenlabs.py $P/voice/script.txt --voice NOpBlnGInO9m6vDvFkFC --out $P/voice --takes 2
cp $P/voice/take1.words.json $P/voice/words.json
ffmpeg -i $P/voice/take1.mp3 -af loudnorm=I=-16:TP=-1.5 -c:a aac $P/assets/voice.m4a
# 3. fonts (Playfair, Montserrat, Geist from $S/templates/fonts), SFX + music bed from $S/library into $P/assets
# 4. copy example/build_two_directions.py to $P/build.py; redraw the world for the new metaphor; re-key every beat to words
cd $P && python3 build.py && npx hyperframes lint && npx hyperframes snapshot --at <every beat>
npx hyperframes render -o renders/<name>.mp4
```

## Checks that caught real problems

- A bare `tl.to()` on something tweened twice locks a stale start value depending on the renderer's seek order (leaves stayed
  hidden until late). Use `fromTo` with explicit values everywhere (`ft` / `tw` helpers in the example).
- SVG `transformOrigin` on circles is unreliable in the renderer: animate `attr: {r}` instead.
- A baseline `tl.set(..., 0)` added later in the list overrides an earlier one (orange "autumn" leaves showed from frame 0):
  register the selector in `based` when you set its baseline by hand.
- Hero text over a dense canopy needs a panel; captions need no box over the dark soil.
- The ElevenLabs MCP connector's grant budget can run out; the direct API key (skill .env) keeps working.
