# Swiss Grid as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it Swiss Grid, the slots
follow the content, catalog.json records what each reel used so the next one does not repeat it. Ported from LemoLab's
MIT-licensed Swiss Motion Graphics style (lemo-opuscar styles/swiss-motion: STYLE.md, DEMO.md, the demo code and the
film «Five Rules for a Poster», watched as reference only) and proved on a 32 s talking-head reel.

## Thesis
**A reel as a Swiss poster programme: the 9:16 frame is one modular page with one typeface and one signal colour; the
speaker's face, as shot, is one band of it, their words are set flush left on the grid as they say them, and between
face worlds the page grows into poster cards where the grid itself carries the idea (a chapter numeral, a programme of
modules, a grid that means something), with one exception, in the signal colour, that does not obey.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no grade, filter, crop or scale on the plates; the header and the page cover only
   what is above the head and below the chin (the page starts 40 px under the head box, checked per world from
   face_track). No graphic, word or grid line ever crosses the face.
2. **One grid.** 6 columns of 130 px, 24 px gutters, 72 px left margin, content to x 972, a 24 px baseline. Every word,
   rule, bar and module starts on a column; flush left, ragged right; big empty space is part of the layout.
3. **One typeface, one signal colour.** Inter only (several weights); page #EAE9E5, paper #FFF, ink #111, greys, and red
   #E30613 for ONE protagonist per reel (in the proof reel, a phone; in a coffee reel, the cup). Real pictures go
   greyscale. No gradients, shadows, glow, grain, blur.
4. **The speaker's words are part of the layout, on their onsets.** A grey lead-in (60 px Medium) and a Bold statement
   (104 px on the page, 112 px on cards, shrinking to fit but never under 48 px); each word rises out of its clip rect on
   its spoken onset in a sixteenth and leaves upward in an eighth. Their words exactly; only transcription fixes.
5. **Two curves only.** cubic-bezier(.7,0,.2,1) for every snap, linear for lines being drawn and for the exception.
   Durations are note values at 30 fps (sixteenth = 4 frames, eighth = 8), onsets on whole frames. Nothing bounces,
   nothing fades, nothing blurs.
6. **Entrances are wipes, deletions are knife cuts.** Paper appears by a wipe of its edge, lines grow along their
   length, numerals climb in 4 eased steps; a deleted thing is crossed by a 3 px line, then collapses to its midline.
   Ripples go nearest-first.
7. **Extreme scale contrast.** Chapter cards put a ~700 px numeral against 48 px notes; the caption row (a rule + 48 px
   notes) is the technical voice.
8. **The exception.** Only the signal-colour element may move linearly and unsnapped, pause mid-flight, or leave the
   grid; a readout can say so ("on grid" -> "off grid").
9. **Cards are short, the face carries the reel.** A card is at most 2.5 s; the face is on screen at least 65 % of the
   reel; the page wipes up into a card and the card rolls up into the header.
10. **Sound is print foley, no music.** The voice + SFX only: paper wipe, block snap, numeral thunk, knife snick, ruled
    line, slide; a sound only where something enters or is cut.
11. **A flat ending** on the last word: no call to action, no end card.

## House look (fixed: house.json)
`house.json` holds the frame grid (columns, margins, header 300 px, page gap 40 px, caption row y 1608 / 1668, the safe
area), the palette, the type (Inter weights and sizes, tracking -2.2 % at 90 px and up, line height 1.04, the numerals'
left bearings for optical flush left), the motion (the ease, note values, entrances, deletions, the exception), the
sound (print foley, no bed) and the budgets. `swissgrid.py` reads them. The components that fill the slots are NEW every
reel; catalog.json lists the components built so far.

## Slots and their generators (the components are new every reel)

The last column is an illustration for an English reel about coffee ("how much caffeine is too much"), not a build.

| slot | its job | generator: the question that fills it from a new script | e.g. a coffee reel |
|---|---|---|---|
| S0 programme | the reel's structure as numbered chapters | how many chapters does the script really have (a tip, steps, reasons), and which line opens each? the header counter counts them | one limit + two habits = 3 chapters, counter 00-03 / 03 |
| S1 the protagonist | introduce the one signal-colour thing | what is the one thing the reel is about, and what flat shape is it (slab, dot, module, line)? the speaker's words overprint it | the cup as a red slab under "your third coffee" |
| S2 the source | show what the speaker cites as an artifact on the grid | do they name a book, study, person or product? show the real thing greyscale on two columns with a museum label in their words | the health agency page they cite, with its title as the label |
| S3 the rule / deletion | make the instruction visible | is the instruction a removal (knife cut), an addition (bars snap in), an order (rows) or a limit (a module filled)? | the late cups as rows, knife-cut one by one |
| S4 the list | carry a list of items | modules drawn on a card, ruled rows on the page, bars of different lengths? numbers match the counter | ruled rows 02-03 for the two habits |
| S5 the tension | the line about risk, effort or doubt | which grid rule does that line break (a bleed off the page, an oversize module, a misaligned row), and how does it resolve? | a bar that slides past the page edge on "jittery", snapping back on the fix |
| S6 the reframe | change of framing between plates | does the cut to the other plate need the page to re-flow to the new chin line? | wide -> tight, the page top moves down one baseline step |
| S7 the grid means something | the peak: the grid becomes a quantity | what does the speaker measure (minutes, days, money, steps)? make columns x rows that quantity, true by definition or sourced (show the source) | 24 cells = the hours of a day; red fills the hours after the last cup |
| S8 ending | the payoff, flat | does the exception leave the frame, does the grid close, does one word stay flush left? | the red cup leaves the grid, "off grid", flat end on the last word |

## Planning procedure
1. The script word for word (build/words.cut.json). Find the plate cuts (`ffmpeg ... select='gt(scene,0.04)'`); cards
   or world changes go on them so jump cuts never show.
2. Write the world list as the docstring of your generator: every line -> face world or card (cards <= 2.5 s, face
   >= 65 %) -> its slot -> the word each element lands on. Pick the chapters (S0) and the one protagonist (S1).
3. Fill each slot from its generator with a component not in catalog.json for the last reels.
4. Write $P/tools/build.py (the public edition has no worked example yet: follow swissgrid.py's docstring), run it with
   ~/.venvs/media/bin/python; `hf.sh lint $P` (0 errors); snapshot every beat and LOOK at frame 0, every card and the
   busiest moment; read build/holds.txt.
5. `finals.py preview` and WAIT for the user's OK.

## Prerequisites
- The approved cut, plates as shot on one timeline, a face file per plate. A second framing (tight) is a bonus.
- No matte, no stock, no screen recordings: the style is drawn. A real picture only for a named thing.

## Sound
- The proof reel: 20 SFX in 32.3 s (6.2 per 10 s): pencil-write (the opening red line), paper-flip on each card wipe,
  wood-hit for the red slab and each numeral, click-1 for the book and each ruled row, shutter-1 for each knife cut,
  wood-plane for the bleed, tick-1 for the red fill, whoosh-1 (soft) for the exception leaving. No music.
- Missing in the library (stand-ins used): a letterpress clack (click-1), a guillotine snick (shutter-1), a ruling pen
  (pencil-write trimmed), a paper slap (paper-flip).

## Not yet built (catalog.json ideas_not_built_yet)
- Rotate 90 degrees and stop; pull out to a wall of artifacts; vertical scroll through a column; split frame into equal
  cells; words behind the speaker's head with a matte; a frame-accurate running counter in the caption row.

## Rejected (do not copy)
- The source's music grid (motorik score, music bed, drum drop at the break): no music bed.
- Archivo (no Cyrillic), Helvetica / Akzidenz files, the source's 19 px notes (the floor is 48 px).
- The source's story, poster, score.json, end card and LemoLab sign-off; any real institution or channel name.
- The source's subtitle hold (>= max(1.8 s, speech + 0.6 s)) as a hard rule: at a fast talking pace (~170 wpm) with
  worlds of 1.5-3.5 s it cannot hold for every line; build/holds.txt reports it instead.
- SVG filter:url() (HyperFrames 0.8.159 blacks out other clips); left/top tweens (snap to pixels; bars move by scaleX).

## Changelog
- Ported from lemo-opuscar styles/swiss-motion (MIT, LemoLab): builder swissgrid.py (class Grid) on facereel.py,
  house.json, catalog.json; proof preview on a 32 s reel.
- Public edition: the exception readout is in English ("on grid" / "off grid").
