# "Two directions" — explainer reel plan (9:16, ~60 s)

Format: animated explainer, no camera footage. Wise-elder voiceover, motion-graphics
illustration built in HyperFrames (SVG + GSAP), word-timed captions, cinematic score.

## Script

The draft repeats its last line five times (a paste glitch) and runs ~200 words (~90 s at an elder's pace).
Proposed tight version, ~115 words, ~60 s. Your wording kept wherever possible:

> Did you know a tree grows in two directions at the same time?
> Down... and up.
> And what's interesting: the roots mirror the crown.
> A tree is both gravitropic and phototropic.
> The roots grow away from the light, and toward gravity.
> Before a tree can ever rise, the seed has to go down first.
> Into darkness. Resistance. Pressure. Dirt.
> The roots literally fight their way deeper.
> But once it breaks through the surface... there's less resistance.
> And that is one of the most beautiful pictures of how life works.
> The work you do in the dark, when nobody sees you, when life feels heavy,
> is what grows the success people admire later, in the light.
> Everybody wants the fruit.
> Very few are willing to go through the lonely seasons that create it.

Fact check:
- Roots are positively gravitropic and negatively phototropic; shoots are the opposite. The radicle (first root) emerges before the shoot. Correct.
- "Root system mirrors the fruit system": botany has no "fruit system". The accurate version is that roots often spread about as wide as the canopy (the drip line) or wider, so it's "the roots mirror the crown", and it's a loose mirror, not an exact one.
- "Less resistance" above ground: true as a metaphor (air vs. soil); fine as stated.

## Look

The vertical frame is the idea: a horizon line across the middle of the 1080x1920 frame.
Above: warm light (cream sky, gold sun). Below: dark soil (near-black brown, grain, pebbles).
The tree is drawn live as SVG strokes: branches grow up, roots grow down, both on the same beat.

- Palette: soil #1B1410 / #2A1F18, root gold #C9A15B, sky cream #F4EAD8, sun #F2B544, leaf green #6E8B3D, fruit red #C0392B
- Type: Playfair Display italic for the elder's key lines (serif = wisdom), Montserrat for labels
- Texture: paper grain + soft vignette, so it feels hand-made, not corporate

## Beats (timing set to the real voiceover once generated)

| # | ~time | voice | picture |
|---|---|---|---|
| 1 | 0–4 s | Did you know a tree grows in two directions at the same time? | Black frame, a single seed on the horizon line. It splits: a stem draws UP, a root draws DOWN, simultaneously. Title "↑ ↓" |
| 2 | 4–9 s | Down... and up. / the roots mirror the crown | The full tree grows both ways. A dotted mirror line; the root system folds up over the crown to show the matching shape |
| 3 | 9–17 s | gravitropic and phototropic / away from light, toward gravity | Two labelled arrows: ☀ phototropic ↑ (light) and ⬇ gravitropic (gravity). The words land as kinetic type |
| 4 | 17–27 s | the seed has to go down first. Into darkness. Resistance. Pressure. Dirt. | The camera sinks underground. The root tip pushes through soil; "RESISTANCE", "PRESSURE", "DIRT" slam in as heavy words that crack; rocks shift; the sound turns low |
| 5 | 27–33 s | But once it breaks through the surface... less resistance | The camera rises; the sprout breaks the surface in a burst of light; growth speeds up; the colours warm |
| 6 | 33–47 s | the work you do in the dark... admired in the light | Split frame: underground roots labelled "5 am", "no one watching", "heavy days"; above ground fruit labelled "success", "recognition", "results" |
| 7 | 47–53 s | Everybody wants the fruit. | Hands reach for the fruit (silhouettes); zoom onto one red fruit |
| 8 | 53–60 s | Very few... lonely seasons that create it. | Seasons cycle fast (snow, bare branches, rain, bloom) while the roots keep growing. The last line lands in serif. Hold 2 s |

## Sound

- Voice: ElevenLabs, a wise elder narrator (see the options), slow, with pauses written into the script
- Music: cinematic piano/drone bed (library: `silent-descent` or `vastness`), ducked under the voice, swelling at the breakthrough (beat 5)
- SFX (Mixkit, licensed): soil crunch/creak on the root push, a deep boom under "Resistance. Pressure. Dirt.", a riser into the breakthrough, soft wind on the seasons

## Build

1. Lock script and voice, then generate the voiceover (ElevenLabs), ~4 takes to pick from
2. Word timestamps (whisper) → scene timing
3. HyperFrames composition: SVG tree (branches/roots as stroke-draw paths), camera moves, kinetic serif type, captions
4. Snapshot every beat → review → render 1080x1920 → loudness/true-peak QA
5. Deliver MP4 + editable project in ~/EXPERIMENTS/reel-tree-roots/
