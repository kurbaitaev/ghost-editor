# Data Story as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it Data Story, the slots
follow the content, catalog.json records what each reel used so the next one does not repeat it. Ported from
Lemo-Opuscar's "Data Storytelling" style (styles/dataviz: STYLE.md, DEMO.md, demo/engine.js; MIT, (c) 2026 LemoLab,
https://github.com/lemomo-ai/lemo-opuscar; CREDITS.txt) and proved on a 32 s talking-head reel. Fold in what the user
keeps after judging a preview with `taste.py`.

## Thesis
**When the speaker's line carries a quantity, the reel cuts to one cream paper sheet where a chart draws itself mark by
mark under a red-blue pencil, with the speaker's words and the facts handwritten as notes pinned to the marks; the
subtitle is the chart's figure caption; every number is real and sourced, and between the pages the face stays as
shot.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no grade, no filter, no graphic on the face. Over the face only the paper caption
   band at the bottom (under the chin) and pencil notes on paper slips above the head; the pencil enters from the upper
   right so it never crosses the face (DataStory.note guards every slip against the face core).
2. **The chart is the page.** Every mark on a page is a chart operation that lands on a spoken word: an axis grows, a
   bar lands, cells fill, a note is pinned, hatching is swept away. One idea per page; no dashboards, no slides.
3. **Every number is true and sourced.** A number appears only from a primary or official source, and the page or the
   kicker names the source and its year. A chart without a verified number says SCHEMATIC (in the reel's language) and
   shows no numbers. Scales start at zero; pale values stay pale; never stretch a ramp.
4. **The pencil is the performer.** Every drawn mark is drawn by the red-blue pencil: it lifts before a mark, travels in
   an arc, trembles while drawing, flips to its red end before a red mark and exits to the edge.
5. **Colour encodes one thing: the value** (a sequential ramp for counts, the RdBu ramp around a reference mean for
   diverging data). Blue lead for human notes, red lead for records and warnings; a change of lead marks a turn. A real
   object the speaker names (a book cover) is the one accent that bypasses the ramp.
6. **The subtitle is the figure caption.** On every frame the speaker speaks: a mono kicker (figure number, topic or
   source), a hairline rule, Playfair Display words appearing on their onsets, two lines max (auto-fit never under
   48 px).
7. **No fades to blank or dissolves.** Pages arrive by hard cut on a word onset with the paper already there; the
   motion lives in the chart (and one slow camera push per page, one push to the last mark at the end).
8. **Sound is graphite, paper and wood.** The voice and foley only where something enters (paper flip on a page, pencil
   on a note, wood hit on a bar, ticks on cells, a riffle on the sweep). No music bed.
9. **The end is a chart move**, not a call to action: one mark close, the empty cell, or the headline revised.

## House look (fixed: house.json)
`house.json` holds what stays reel to reel: the palette (paper #F6F3EC, dot grid #E4DDCF, ink #2B2723, soft ink
#6E665C, blue pencil #2F5D8A, red pencil #A8283A, the two ramps), the type (Caveat notes, Playfair Display headlines and
captions for the source's Newsreader, JetBrains Mono units and sources for IBM Plex Mono; nothing under 48 px), the
layout (caption kicker 1262 / rule 1282 / last baseline 1440, band 1196-1486 over the face; page title 330, chart
470-1180; notes at y 230-370 above the head), the pencil (scale 1.25; 0.62 rad on pages, -0.62 over the face), the
motion keys, the sound roles and the budgets (face >= 50 %, a page <= 3.4 s, <= 3 pictures a minute). The builder
`datastory.py` reads them; `engine.js` is the drawing. The charts, notes and the opening and ending moves are NEW every
reel (`scripts/components.py plan --style data-story`).

## Slots and their generators (the components are new every reel; catalog.json lists what was used)

The last column is an illustration for an English reel about caffeine, with the real numbers of the FDA Consumer Update
"Spilling the Beans: How Much Caffeine is Too Much?" (content current as of 2024-08-28; CREDITS.txt), not a build.

| slot | its job | generator: the question that fills it from a new script | e.g. a caffeine reel |
|---|---|---|---|
| S1 opening | set the measure before the case | which opening fits: the question first (an empty plot with only its unit and a handwritten question), one mark close, or the finished chart worked backwards? | the question first: "How much is too much?", an empty axis in mg, a red empty cell with "?" |
| S2 named thing | make the thing the speaker names concrete | do they name a book, an app, a study? show the real object pinned to the paper, annotated in pencil (name, ring on its key detail) | the agency page they cite, its title handwritten, a red ring on its daily figure |
| S3 data chart | the quantity the line carries | which true, sourced number sits under this line, and which chart does it ask for (bars for categories, dots for a series, a slope for before / after, a unit chart for parts of a whole)? land each mark on the word that names it | bars from zero on a 400 mg scale: green tea 37 mg, black tea 71 mg per 12 fl oz (FDA), kicker "FIG. 1 · FDA 2024" |
| S4 second chart | the turn of the reel | what does the turn measure (time, people, money), and which official numbers can carry it? | three 12 oz black teas (3 x 71 mg = 213 mg) as a filled share of one bar scaled to 400 mg a day for most adults (FDA) |
| S5 face notes | the key words over the face | which word of each face line carries it? write it (the speaker's words) on a slip above the head; blue for the human, red for the warning; underline, wave or strike | "too much?", "400 mg a day" in red |
| S6 ending | the verdict as a chart move | one mark close, the empty next cell, the headline revised, or a morph of an earlier chart? | the headline revised from the question to the answer, push in on the 400 mg mark |

## Planning procedure
1. `python3 $S/scripts/components.py plan --style data-story`: what the last reels used (avoid) and what is free.
2. The script word for word (build/words.cut.json). Write build/plan.txt: every line -> face or page -> the word each
   mark lands on. Mark the lines that carry a quantity: those are the pages (2-5 per 30 s; face stays >= 50 %).
3. For every number: find the primary or official source, read the number in it, write the source and its date into
   the plan and on the page. If it cannot be verified, the chart shows no number and says SCHEMATIC.
4. Write $P/tools/build.py (the public edition has no worked example yet: follow datastory.py's docstring) and run it
   with `~/.venvs/media/bin/python`; `hf.sh lint $P` (0 errors); snapshot every beat and look at frame 0, every page's
   busiest moment and the last frame at full size (edges: x 40-980, y 220-1490; nothing on the face).
5. `finals.py preview $P --out $P/finals --style "Data Story" --code <code> --title "..."` and WAIT for the user's OK
   before `finals.py render`.
6. After the user's yes: `components.py record --style data-story --project $P --reel <code>`.

## Prerequisites
- The approved cut: plates as shot (one is enough; two framings give the face worlds a reframe cut), voice.wav, words
  in edit seconds, face.json per plate. A line with a quantity in it, or the style has nothing to chart.
- Data from primary / official sources (papers, agencies). Never invent a statistic; never chart a number from a blog
  or an aggregator.
- No matte, music, stock footage or generated pictures needed.

## Sound
- Measured in the source: ambience, foley (taps, scratches, ruler hiss, ratchets, paper sweep), sonification and a
  modular bed, music ducked -11 dB. Here: the voice + foley only; the proof reel: 24 SFX in 32 s (paper-flip x5 on
  pages, pencil-write x11 on notes, wood-hit x4 on bars, tick-1 x3 on cells, paper-riffle on the sweep), foley 14 dB
  under the voice.

## Not yet built (catalog.json ideas_not_built_yet)
- Sonification (each mark a pitch): a music layer, dropped by the no-bed rule; a quiet single "plonk" per mark could be
  asked for.
- A time series with the tracking camera, the frame break and the scale switch; the encoding morph (bars -> waffle); the
  frozen-pane tick strip; words behind the speaker's head with a matte.

## Rejected (do not copy)
- The source's music bed, score and sonification (voice + SFX only).
- Newsreader and IBM Plex Mono (no Cyrillic / not in templates): Playfair Display and JetBrains Mono.
- Mono ticks at 17-20 px and a 42 px caption: under the 48 px floor.
- Graphics over the face, a pencil crossing the face, a fade to paper.
- The demo's story, data, film, voices and LemoLab end card.

## Changelog
- Ported from lemo-opuscar styles/dataviz (MIT, (c) 2026 LemoLab): engine.js adapted from demo/engine.js, builder
  datastory.py (class DataStory) on scripts/lib/facereel.py; proof preview on a 32 s reel.
- Public edition: the builder's docstring sketches an English reel with real, sourced FDA numbers (checked by a build
  of that sketch).
