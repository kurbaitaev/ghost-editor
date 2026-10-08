# Style libraries for the "@loompixual RESULT" podcast-edit look

Researched 2026-10-07. Target look: centred lowercase one-word captions, a two-size stacked emphasis line
("and the rest / **WILL COME.**"), full-screen text cards on flat colour (yellow, navy, red-orange gradient)
with film dust, a polaroid/paper cut-out card, handwritten script words, hand-drawn arrows and scribbles,
rounded-corner framed B-roll on dark, archival inserts, an overall dark grain, and snap zooms.

How to read this: **ranked best-first per slot.** Licence is checked on GitHub (`gh api`) where possible.
"Unverified" means I could not find a licence file.

---

## 0. TL;DR stack (what to actually use)

| Slot | Use | Licence |
|---|---|---|
| Captions (word-at-a-time) | Hand-rolled GSAP timeline from word timestamps, using **GSAP SplitText** when you need per-char motion. Base it on HF `caption-editorial-emphasis` for the two-size stacked line | GSAP standard licence (free, commercial OK) |
| Handwritten words | HF `hw-title` / `hw-path-text` + a Google script font (Caveat / Mrs Saint Delafield) | HF registry + OFL |
| Arrows / scribbles / circles | HF `hw-arrow`, `hw-underline`, `marker-highlight`, `hw-boil`; fallback **rough-notation**, or **vivus**/GSAP DrawSVG on SVGs from the Excalidraw libraries | MIT |
| Film grain | HF `grain-overlay` (CSS), or a **mattdesl/glsl-film-grain** canvas, seeded per frame | MIT |
| Dust and scratches | **Procedural canvas layer** (seeded specks and vertical scratch lines, keyed to frame number). Use a real overlay MP4 only if you have one with a clear licence, blended with `screen` | your code, CC0 |
| Paper / polaroid card | HF `freeze-frame-dressing` (paper, tape, flash) + an ambientCG `Paper00x` texture + CSS polaroid frame | CC0 |
| Snap zooms | HF `yt-camera-move`, or plain GSAP `scale` tweens on the video wrapper (`hyperframes-keyframes` skill) | — |
| Fonts | Caption sans: **Inter Tight** (or Geist). Script: **Caveat** (casual), **Mrs Saint Delafield** (elegant "Always"). Editorial accent: **Instrument Serif** | SIL OFL |

---

## 1. HyperFrames registry hits (`npx hyperframes catalog --query … --json`)

Install with `npx hyperframes add <name>`. Previews are at `static.heygen.ai/hyperframes-oss/registry/...`.

**Captions / typography**
- `caption-editorial-emphasis` (component): a two-font system with strong size contrast on emphasis words. **This is the closest match to "and the rest / WILL COME."** Start here and restyle it to lowercase Inter Tight with a bold uppercase emphasis line.
- `caption-kinetic-slam` (component): one word full-screen with alternating entrance directions. It's useful for the full-screen colour-card words, but tone the slam down because the reference is calm.
- `caption-clip-wipe` (component): a left-to-right clip-path reveal per word. It's a subtle option for the centred single word.
- `blur-out-up`, `shared-axis-y`, `text-stagger`, `text-state-swap` (components): soft per-word enter and exit primitives in the reference's register.
- `kinetic-center-build`: words push in until the phrase locks centred. `kinetic-type-swap`: one slot rolls through alternatives.
- `mk-emphasis-type`: an oversized, low-contrast background word drifting behind the subject. Good for the navy card.
- Skip `caption-pill-karaoke`, `caption-highlight`, `caption-neon-*` and `caption-particle-burst`. They're TikTok-loud and the wrong vocabulary.

**Handwriting / scribbles (the `hw-*` family, all seek-safe)**
- `hw-arrow` (component): a wobbled draw-on arrow with straight, gentle and swoop poses, a stroke texture matrix (plain/soft/sharp/spray) and a travel-aligned head. **This is the primary arrow tool.**
- `hw-underline` (component): a squiggle underline, double-pass strikethrough and bracket marks.
- `marker-highlight` (component): one marker stroke (highlight, circle, underline or scribble) over an emphasised word on cue.
- `hw-title` (block): handwritten display text with a word-by-word highlight sweep and a seeded squiggle underline. Use it for "and trying to do" / "Always".
- `hw-path-text` (block): handwriting along an SVG path with a per-character reveal.
- `hw-boil` (component): line-boil jitter quantised to timeline time (seeded hash), which gives the hand-drawn "alive" feel deterministically. Wrap arrows in it.
- `hw-text-cloud`, `hw-box-label`, `hw-pipeline`: speech bubble, wobbly box and connector diagram (optional).

**Texture / overlays**
- `grain-overlay` (component): animated film grain with CSS keyframes. **Use it as the global top layer.**
- `organic-light-leak-overlay` (block): a finite CSS light leak for memory beats and transitions.
- `editorial-flash-overlay` (block): a warm camera-flash cut. It fits a polaroid entrance.
- `ridged-burn`, `light-leak`, `cinematic-zoom` (blocks): shader transitions. Use sparingly; film burn suits the archival inserts.
- There's **no dust/scratch block** in the registry. The query only returned grain and light-leak, so dust and scratches have to be built (see §3).

**Cards / paper**
- `freeze-frame-dressing` (block): timeline-driven paper, tape and flash dressing for a freeze-frame or a background-removed subject. **This is the closest to the polaroid/sticker card.** Combine it with `npx hyperframes remove-background` for cut-outs.
- `texture-mask-text` (component): 66 ambientCG luminance masks cut through letterforms. It can give paper-textured title words.
- `ink-bleed-reveal` (component): ink blooms through paper. It's an optional transition onto the yellow card.
- `yt-lcd-background` (block): a textured paper board with grain and a blur-focus title. It could be restyled into the flat-colour cards.
- No polaroid-specific block exists (`polaroid photo card` only returned social cards), so build one in CSS (§4).

**Camera / layout**
- `yt-camera-move` (component): zoom, slide and 3D tilt-pan helpers for any wrapper, with an edge-defocus pulse. Use it for snap zooms.
- `split-tilt-cards`, `comparison-split`: two-panel layouts if a split screen is ever needed. The reference doesn't use one.

---

## 2. Open-source libraries (outside the registry)

Ranked by fit with a deterministic, seekable GSAP timeline. Anything that runs its own `requestAnimationFrame` loop must be driven from the timeline (`progress`/`seek`) or it won't render deterministically.

1. **GSAP 3 + SplitText + DrawSVG (+ MorphSVG, ScrambleText)**: https://gsap.com/docs/v3/Plugins/SplitText/
   - Licence: GSAP Standard "No Charge" licence (Webflow, effective 2025-04-30). All former Club plugins are free for commercial use: https://gsap.com/community/standard-license/ . The one exclusion is building a competing visual animation builder, which doesn't apply here.
   - Integration: it's already the HyperFrames runtime. `import { SplitText } from "gsap/SplitText"`. Use SplitText for per-char/line reveals and DrawSVG to stroke-draw arrows and scribbles from any SVG path. Both are seek-safe on a paused timeline.
2. **rough-notation** (MIT, 9.7k★): https://github.com/rough-stuff/rough-notation
   - Hand-drawn underline, box, circle, highlight, strike-through and bracket around DOM text, built on rough.js.
   - Integration: its own `show()` animation is CSS/rAF based. For determinism, generate the annotation SVG (`animate:false`), then animate the paths with GSAP DrawSVG. Remotion has a wrapper (`@remotion/rough-notation`) as a reference implementation.
3. **rough.js** (MIT, 21k★): https://github.com/rough-stuff/rough
   - Sketchy lines, curves and ellipses as SVG. Pass `seed` so shapes are identical on every frame. That gives custom arrows and circles around a face.
4. **vivus** (MIT, 15k★, stale since 2022): https://github.com/maxwellito/vivus
   - SVG line-draw. Has a manual mode (`setFrameProgress`) you can drive from the timeline. GSAP DrawSVG makes it redundant, so keep it only as a fallback.
5. **Splitting.js** (MIT): https://github.com/shshaw/Splitting
   - Splits text into CSS-variable-indexed spans. It's a lighter alternative to SplitText if you want CSS-only staggers.
6. **anime.js v4** (MIT, 73k★, active): https://github.com/juliangarnier/anime
   - It's a HyperFrames-supported adapter (see the `hyperframes-animation` skill). It has text splitting and SVG draw helpers. Only worth it if a ported effect is already written in anime.
7. **mattdesl/glsl-film-grain** (MIT): https://github.com/mattdesl/glsl-film-grain
   - A natural-looking GLSL grain function. Drop it into a full-frame `<canvas>` WebGL pass, with the uniform `time = frameIndex` so it's deterministic. It looks better than CSS noise if `grain-overlay` reads too digital.
8. **Motion Canvas** (MIT): https://github.com/motion-canvas/motion-canvas and **Revideo** (MIT): https://github.com/redotvideo/revideo
   - Separate code-first video engines. They're **reference only** for kinetic-type patterns. Don't mix them into HF.
9. **Remotion `@remotion/captions`** (`createTikTokStyleCaptions`): https://www.remotion.dev/docs/captions/create-tiktok-style-captions
   - Licence: Remotion licence. It's free for individuals and companies of up to 3 people, otherwise a paid company licence: https://www.remotion.dev/docs/license
   - Integration: the useful idea is its **token-grouping logic**. `combineTokensWithinMilliseconds` set low gives word-by-word, set high gives multi-word pages. Port that ~30-line grouping into the HF caption builder rather than depending on Remotion.
   - Also a reference: `vshukla7/remotion-captions-themes` (MIT), themeable word-level caption themes: https://github.com/vshukla7/remotion-captions-themes

---

## 3. Film dust, scratches and grain overlays

**Recommendation: generate dust and scratches procedurally, and add grain via `grain-overlay` or the GLSL grain.**
It avoids any licence question, it's fully deterministic, and it's tunable per scene (heavy on colour cards, light on the face).
Sketch: a full-frame canvas; on each frame `f`, seed an RNG with `f`; draw 0–6 specks (1–4 px, sometimes a hair-like curve), plus a 1 px vertical scratch with ~8% probability, held 2–4 frames. Use `mix-blend-mode: screen` (white dust) on dark scenes and `multiply` (dark dust) on the yellow card. Add a gentle 1–2% luminance flicker.

If you'd rather have real scanned film:

| Source | What | Licence | Note |
|---|---|---|---|
| Pixabay video search "film dust", "old film" https://pixabay.com/videos/search/film%20dust/ | Various overlay clips | Pixabay Content License (free commercial use, no attribution; can't be redistributed as a stand-alone asset) | Pick ≥1080p, check each clip |
| Mixkit (see memory: 2160p = commercial free licence) https://mixkit.co/free-stock-video/ | Search "old film", "dust" | Mixkit Free licence | Same sourcing workflow as the B-roll |
| Kestfilms 16mm Film Matte (FREE) https://kestfilms.gumroad.com/l/freefilmmatte | 4K dust, 16mm grain, burn | **Not stated**, so ask or avoid | 2 GB |
| Snowman Digital old film grain https://snowmandigital.gumroad.com/l/NfyiE | Grain/dust | "CC licence", credit requested | Pay-what-you-want |
| Enchanted Media dust & scratches https://enchantedmediauk.gumroad.com/l/free-dust-and-scratches-overlay-video | 1080p loop | Not stated | HD only |
| Cinecom DUST 4K https://cinecom.gumroad.com/l/DustPack | 4K dust | Free tier **non-commercial** | Avoid |

I couldn't find any verified CC0 4K dust/scratch video pack. That's another reason to go procedural.
For integration, an overlay MP4 goes in as a muted `<video>` clip on the top track with `mix-blend-mode: screen` and `opacity: .35–.6`. Black-background overlays need `screen`; white-background ones need `multiply`.

---

## 4. Paper, polaroid and sticker cut-out cards

- **Paper textures (CC0):** ambientCG `Paper001`–`Paper006` and `Cardboard001`–`004` (I confirmed these exist via the ambientCG API): https://ambientcg.com/list?q=paper . Use the `_Color` 2K JPG as a `background-image` on the card. Poly Haven (CC0) is an alternative source: https://polyhaven.com/textures
- **Polaroid build (CSS, no library needed):** a white or off-white frame `padding: 28px 28px 110px`, paper texture at 25% `multiply`, a slight `rotate(-3deg)`, and a soft `drop-shadow`. Put the photo or B-roll inside. Animate it in with `back.out(1.4)` scale 0.85→1 plus a rotate settle, and an `editorial-flash-overlay` on impact.
- **Sticker / cut-out:** run `npx hyperframes remove-background` (or the `media-use` skill) for the subject, then a CSS outline sticker edge via `filter: drop-shadow(0 0 0 6px #fff)` stacked x4, or an SVG `feMorphology` dilate for a clean white border. Tape strips come from `freeze-frame-dressing`.
- **Rounded framed B-roll on dark:** plain CSS `border-radius: 28px; overflow:hidden` on a `#0d0d0f` field with a grain layer. Add a subtle 1.00→1.04 Ken Burns with GSAP.
- **Flat colour cards:** solid `#F2C230`-ish warm yellow, `#0E1A3A` navy, and a `linear-gradient(160deg,#E2401C,#F28A2E)` red-orange, plus the dust layer at high strength and a vignette. Text is Inter Tight with a single Instrument Serif or script accent word.

---

## 5. Fonts (all on Google Fonts; SIL OFL unless noted, so free to embed)

| Role | First pick | Alternates | Why |
|---|---|---|---|
| Single-word caption (small, clean, lowercase) | **Inter Tight** 500 https://fonts.google.com/specimen/Inter+Tight | Geist, Manrope, Instrument Sans | Neutral Helvetica-Now feel, tight tracking |
| Big stacked emphasis ("WILL COME.") | Inter Tight 800, uppercase, -2% tracking | Archivo Black, Anton (if it should be more condensed) | Size contrast with the caption |
| Casual handwriting ("and trying to do") | **Caveat** https://fonts.google.com/specimen/Caveat | Nothing You Could Do, Reenie Beanie, Homemade Apple (Apache-2.0) | Reads as a real pen |
| Elegant script ("Always") | **Mrs Saint Delafield** https://fonts.google.com/specimen/Mrs+Saint+Delafield | Allura, Pinyon Script, Corinthia | Thin flowing script as seen in the reference |
| Editorial serif accent | **Instrument Serif** (italic) https://fonts.google.com/specimen/Instrument+Serif | Fraunces, DM Serif Display | For a "Growth is so important" style card line |

Self-host the woff2 in `assets/fonts/` (HyperFrames renders offline/headless), and `await document.fonts.ready` before the first frame.
For the "being written" effect on script fonts, use `hw-path-text`, or a left-to-right clip-path/mask wipe per word (it's close enough at reel speed). True stroke-order writing needs a single-line SVG font, which isn't worth it here.

---

## 6. Hand-drawn arrow and doodle SVG packs

| Pack | Licence | Note |
|---|---|---|
| HF `hw-arrow` / `hw-underline` / `marker-highlight` | HyperFrames registry | **Use first.** Parametric, seek-safe, already boils |
| Excalidraw libraries https://libraries.excalidraw.com (repo MIT: https://github.com/excalidraw/excalidraw-libraries) | MIT repo; each library has an author, so check per lib | Export to SVG, then draw with DrawSVG. The sketchy style matches |
| rough.js (generate your own) | MIT | Seeded, unlimited, consistent |
| dddoodle by fffuel https://fffuel.co/dddoodle/ | **CC BY 4.0** (credit required) | 120+ arrows, circles, stars, lines, as an SVG zip |
| Handy Arrows https://github.com/Eronred/handy-arrows (389★) | **Unverified.** Directory sites say MIT, but the repo has **no LICENSE file** and the README doesn't state one | 180+ arrows. Ask the author or avoid for commercial use |
| Open Doodles https://opendoodles.com | CC0 (per site) | Characters rather than arrows. Optional |

---

## 7. Integration recipe for HyperFrames (one paused timeline)

Track order, bottom to top:
1. Speaker video in a wrapper. Snap zooms are 4–6 frame `power4.out` tweens of `scale` 1→1.12 on the wrapper, cut-synced (`yt-camera-move` or the `hyperframes-keyframes` skill).
2. Inserts: B-roll framed cards, archival clips, flat-colour cards, the polaroid card (each one a sub-composition).
3. Text: a single caption track (one centred word, Inter Tight ~56–64 px lowercase, at ~62% frame height; plain fade/blur-in, 80–120 ms per word), the emphasis-line component and the handwritten words.
4. Scribbles: `hw-arrow` / `hw-underline` timed to the spoken word. DrawSVG draw-on ≈ 250–400 ms, then `hw-boil` while held.
5. Texture: dust canvas (seeded by frame) plus `grain-overlay` across everything, a light vignette and a slight warm/low-saturation grade.

Determinism rules: every random value seeded by frame or time, no `Math.random()` at runtime, no free-running rAF, and fonts and textures local.
Captions come from word timestamps (`npx hyperframes transcribe` or the `media-use` engine), grouped with Remotion-style `combineTokensWithinMilliseconds` logic (~0 ms gives one word at a time, ~600 ms for the stacked two-line beats).

---

## 8. Vocabulary for the look (reference only)

I didn't find a canonical CapCut or Premiere template named for this style. Template sites are SEO-heavy and none matched film grain + script + polaroid podcast edits.
Search terms editors use for this aesthetic, useful for finding more references:
- "podcast edit", "aesthetic podcast edit", "documentary-style reel", "editorial edit"
- "scrapbook edit", "paper cut-out edit", "collage edit", "polaroid transition"
- "film grain + dust overlay", "vintage/16mm look", "archival b-roll edit"
- "handwritten text edit", "script font captions", "minimal captions / one word captions"
- "doodle arrows overlay", "hand-drawn elements pack", "scribble animation pack"
- In CapCut these pieces exist as built-ins ("Film" effects category: Dust, Old Film, Grain; text templates under "Handwriting"). Premiere/AE marketplaces sell them as "Hand-drawn elements", "Doodle pack", "Scrapbook/Paper toolkit" and "Film overlays".
- Adjacent creator styles: Ali Abdaal (handwritten captions, paper-tear transitions, Inter) and documentary-style podcast clippers. Hormozi-style (yellow Montserrat Black karaoke) is the **opposite** of this look, so avoid it.

## Sources
- GSAP licence: https://gsap.com/community/standard-license/ ; gsap-trial deprecation: https://cdn.jsdelivr.net/npm/gsap-trial@3.13.0/README.md
- Remotion captions: https://www.remotion.dev/docs/captions/create-tiktok-style-captions ; licence: https://www.remotion.dev/docs/license
- rough-notation: https://roughnotation.com ; Remotion wrapper: https://www.remotion.dev/docs/rough-notation/api
- Dust packs: listed in §3 ; CapCut overlay roundup: https://www.capcut.com/resource/best-free-film-dust-overlays
- Handy Arrows listing (claims MIT): https://uiuxshowcase.com/resources/handy-arrows/
- Ali Abdaal style notes: https://sendshort.ai/guides/ali-abdaal-style/
- GitHub licences verified via `gh api repos/<repo>` on 2026-10-07 (rough, rough-notation, vivus, Splitting, anime, motion-canvas, revideo, glsl-film-grain, excalidraw-libraries: MIT; remotion: custom).
