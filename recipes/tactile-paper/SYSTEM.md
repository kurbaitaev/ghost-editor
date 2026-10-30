# Tactile paper as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it Tactile paper, the
slots follow the content, catalog.json records what each reel used so the next one does not repeat it. Replicated
frame by frame from a reel by @chrismoran__ (an After Effects CC Page Turn + Posterize Time tutorial on bringing paper
animations to life) and applied to a founding talking-head reel. The user's notes on the next reels outrank anything
here: fold them into this file and house.json.

## Thesis
**A talk told on printed paper that moves like stop-motion: every noun becomes a physical sheet that unfurls, curls
in or turns on its word, hand marks steer the eye, and the paper turns away like a page to reveal the speaker's face
on the personal lines.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no grade, no filter on the face; every insert is conformed to the plate; B-roll
   obeys the people rules and shows its line (references/broll.md section 0).
2. **Paper is physical.** Every sheet enters, leaves and changes by a page fold (unfurl from a corner, curl in from an
   edge, turn away), never by a fade or a flat slide; every sheet has paper texture and a contact shadow, and the camera
   on paper is never still (a slow push on every hold).
3. **A stop-motion clock.** Designed motion is stepped on twos (12 fps); the payoff on threes (8 fps). The plate, the
   caption swaps and the timing of a reveal stay on the 30 fps clock. Stepped = made by hand.
4. **The hook writes half the line, an object finishes it.** Frame 0 already moves (the object is unfurling), the
   title words rise whole on twos, and the next stressed word gets a zoom-blur push into the object (the scale jump
   hidden in the blur, title and arrow gone on that frame).
5. **Every noun on paper gets its own object on its word** (within ~0.1 s): a page, a print, a card, a map, a ticket.
   The object shows what the speaker says; a drawn metaphor only when the line is abstract (a crowd seen from above
   with one person alone for loneliness).
6. **The page under the page is the speaker.** A paper scene hands over to the face by turning away like a page (the
   whole frame), landing on the personal words; the face is the pattern break and carries the reel (45-60 % on
   screen), every paper scene <= 3.5 s, nothing drawn on the face (a sheet may sit below it).
7. **Hand marks only steer the eye.** A white brush arrow (black on the flat ground) = look here; a crimson underline
   under the printed words the speaker paraphrases; a crimson ellipse round the one thing they name. Marks are glued
   to their paper and leave with it (baked into a page that turns), they never float.
8. **Before / after inside the scene.** A slow turn shows the other side of the same idea (the reverse side, the
   blank new page), and the idea's one word rises letter by letter from behind the page (the caption that says the
   same word is hidden).
9. **The payoff is a bookend.** The hook object comes back on 8 fps with one new object that names the cost; the
   8 fps turn goes onto the face for the last line, and the reel ends flat on the face (no CTA, no pen outro).
10. **One house.** The maroon textured ground (or its flat twin), newsprint and archive paper, near-black grotesque
    titles, white arrows, one crimson marker, black condensed pill captions of 1-3 words with hard swaps; per line
    only the object changes.
11. **Only the speaker's words or plain fact on paper.** Handwriting is the speaker's own line; a printed source
    carries its real text (the paraphrased words underlined, the caption carries the meaning); labels are names and
    years; no em dashes.
12. **Sound only where something enters or a section changes.** A flat piano bed under the voice, whooshes pre-lapped
    to peak on a push or a section cut, foley on a mark or a label, one low boom under the big turn, a quiet payoff;
    nothing on caption words.

## House look (fixed: house.json)
`house.json` holds what stays reel to reel: the palette (maroon ground #522333 / #60293C / #240F16, flat #6A2947,
title #110E10, label and black arrow #141114, white arrow #FDFCFB, marker #990028 in multiply, pill
rgba(31,31,31,0.85) with #FCFCFD text, label box #363432), the type (Inter Tight 700 for titles 128 px, the rising word
190 px, labels 58 px and captions 62 px condensed 0.8; Playfair Display, JetBrains Mono and Caveat for printed props,
all with Cyrillic), the layout (paper full frame, page x 35-1048, close-up 1.12x -2 deg, a sheet below the face from
y 1215, captions at y 1400), the insert frames, the motion (unfurl, turns, push, holds), the texture, the sound and the
budgets. The builder is `tactile.py` (Tactile on scripts/lib/facereel.py) with the runtime `tactile.js` (the replica's
WebGL page fold, brush, marker, gobo and caption code + a data-driven scene loop); both read house.json. Props are
drawn per reel with `props.py`. A new house element only enters when the user asks for it, and then it replaces the
old one in house.json.

## Slots and their generators (the components are new every reel; catalog.json lists what was used)

| slot | its job | generator: the question that fills it from a new script | the founding reel used |
|---|---|---|---|
| S1 hook object | finish the half-written first line on frame 0 | what concrete thing does line 1 name (a city, a news page, a tweet, a receipt, an app screen as a printout)? Make it a sheet that unfurls on frame 0, title the first half of the line over it, and push (zoom blur) on the next stressed word | a drawn city map under the first half of the line, white arrow title -> map, push on the next stressed word |
| S2 turn onto the face | hand over from paper to the face on a personal line | where does the line turn to "you" / "I"? Turn the whole frame there, in a turn not used lately (fast on twos, on threes, from the left, folded in half, torn) | a fast turn on a personal line about the past; an 8 fps turn on the last line |
| S3 source page | put the source of a quote or a fact on paper | whom or what does the speaker cite (a book, a study, an article, a law)? Typeset its real text (props.essay_page), below the face or full frame, a plain-fact label (name, year) on the name | a 1903 essay by the quoted sociologist (Georg Simmel), unfurling below the face; a name + year label |
| S4 picture on the noun | make a noun concrete | which noun must be seen? A print or card curling in on it: the speaker's own photo first, then a still without people (insert_prep + broll_vision), then a drawn one | a B&W print of skyscrapers (a stock still, no people) on its noun |
| S5 marks | steer the eye | which printed words does the speaker paraphrase (underline), which one thing do they name (ellipse), where must the eye go (arrow)? | 2 underlines on the essay page, ellipses round the lone figure and the price, 2 white arrows, 1 black arrow |
| S6 before / after turn | show the other side of the idea | what is the other side (the reverse side, the empty page, the after)? The page turns slowly on that word and shows it under | on the turn word: the marked page turns onto a halftone crowd; the notebook turns onto a blank page |
| S7 the rising word | name the idea in one word | which single word names the line? It rises from behind the page (the caption with it is hidden) | the idea's one word over the notebook, black arrow to the page |
| S8 payoff bookend | close the loop | what from the hook comes back on 8 fps, and which one new object names the payoff (a ticket, a bill, a stamp, a receipt)? | the map on 8 fps + a train ticket, PRICE circled on its word |
| S9 ending | end flat on the face | which last line is said on the face? Hold the tail, no caption, no CTA | the last line, 0.45 s held |

## What the founding reel did (35.98 s)
- S1 0-3.43 paper: maroon ground, title rise + map unfurl + white arrow, zoom-blur push, gobo, fast whole-frame turn.
- S2 3.43-5.43 face: the essay page unfurls below the face, the name label pops on the author's name.
- S3 5.43-8.70 paper: the page close-up, two underlines on the paraphrased words, the city print curls in.
- S4 face. S5 9.73-12.83 paper: the slow turn on the turn word, the crowd from above, white arrow, ellipse on the lone figure.
- S6 face (personal lines). S7 18.33-21.33 paper: notebook, the one word rises, black arrow, turn to the blank page.
- S8 face. S9 28.93-31.83 paper: the map on 8 fps, the ticket, PRICE circled, the 8 fps turn. S10 face to the end.
- Face on screen 56.4 %, 5 paper scenes (longest 3.43 s), 1 stock still, 10 SFX (2.78 per 10 s).

## Planning procedure
1. `python3 $S/scripts/taste.py prompt --style tactile-paper` and `python3 $S/scripts/components.py plan --style
   tactile-paper`: the user's rules for the style, what the last 7 reels used (avoid) and what is free.
2. The script word for word; for each line, its slot or nothing. Mark the personal lines (the face), the carrying
   lines (paper, 3-5 scenes of <= 3.5 s), the cited source, the before / after word, the one rising word and the
   payoff. Leave most lines to the face and the captions.
3. Fill each slot from its generator with a component the last reels did not use; register each new one first:
   `components.py add --style tactile-paper --id <id> --kind <kind> --slot S<n> --sig '<regex>' --desc ...`
   (sig on its texture name, e.g. `"ticket": "assets/ticket\.png"`, or on its data, never on the runtime code).
4. Props: draw them in the generator with props.py (essay_page, notebook_page, ticket, photo_print, paper + apply_ink
   + halftone for your own drawings); stills through `insert_prep.py --line` and `broll_vision.py picks` first.
5. Write the generator from the usage block in tactile.py's docstring, run it with a python that has numpy + Pillow +
   OpenCV (e.g. ~/.venvs/media/bin/python), `hf.sh lint`, snapshot every beat (`snap.py beats $P` or
   `hf.sh snapshot --at ...`) onto one sheet, `components.py check --style tactile-paper --project $P`; check the
   face is clean, text legible, nothing cut off, captions clear of the cards.
6. `finals.py preview $P --style "Tactile paper" --code <CODE> --title "..."` and WAIT for the user's OK before
   `finals.py render`.
7. After the user's yes: `components.py record --style tactile-paper --project $P --reel <code>`.

## Prerequisites
- An approved raw cut: the plate as shot, the voice, the words in edit seconds and build/face.json
  (`facereel.py --new $P --from <cut dir>`). Nothing else is filmed: every picture is drawn or typeset per line.
- Real objects the speaker names (a news page, a tweet, a receipt, a document, their own photos) make the strongest
  props: ask for scans or screenshots before drawing a stand-in. Never fill a gap with stock photos of people.
- A tutorial reel (an AI tool, an app) needs the speaker's own screen recordings for the zoomed UI crops of the
  reference (not built yet); without them the style stays on paper.
- props.ground() needs OpenCV, the props numpy + Pillow. Drawing all of the founding reel's props took ~10 s of CPU
  (minutes of wall time on a busy machine: the crowd placement).

## Sound
The reference measured on HDemucs stems: 14 SFX in 43 s = 3.2 per 10 s, 5 of them loud (1.2 per 10 s), a pensive piano
bed ~17 dB under the voice, no drums. Whooshes and hits lead: onset 6-15 frames early, peak within -2..+4 frames of the
cut or landing; paper foley lands on the landing frame; clicks on the action frame; loud accents only at section
changes. The founding reel kept it: silent-descent at -18 dB with a -4 dB duck; whoosh-2 0.8 s before the push and
before each cut into a paper section; tick-1 on the label pop; marker-scribble on each underline and ellipse (<= 0.5 s,
foley 0.9 s apart); cinematic-deep-boom at -7 dB under the reverse-side turn; whoosh-cine at -8 dB on the payoff turn;
10 SFX = 2.78 per 10 s. Aim for 2.5-3.5 per 10 s. The founding reel had no paper foley, so its turns were unsounded;
library/sfx now has paper-flip and paper-riffle (the CC0 pack) for page turns. Never a UI sweep in place of paper.

## Not yet built (ideas_not_built_yet in catalog.json)
- Before / after in place: zoom out on twos + a hard-edge left-to-right wipe from the textured page to its flat twin
  (the reference's 'Flat' moment).
- A page turn as an object wipe between two paper scenes; the reverse turn from the left for a callback.
- The top-down desk collage (papers landing on their nouns with contact shadows); the crimson zig-zag scribble
  cross-out; the cut + blur breath on threes; an arrow that tracks a moving element.
- Zoomed screen-recording crops with a cursor-following camera (needs the speaker's own recordings).
- Paper slide / tap foley (library/sfx has none yet); the page fold's wedge-shaped flap and cast shadow (the replica's remaining misses).
- Merging Tactile paper with a paper collage style into one "Tactile collage" (not decided).

## Rejected (do not copy)
- From the reference: the face on 4 % of the runtime (a screen tutorial; a talking head carries these reels,
  45-60 %); captions at y 1500-1571 (inside the Instagram bottom UI) and 50 px (the floor is 48 px: 62 px condensed
  0.8 at y 1400); the open end cut mid-sentence on "And now..." (the default ending is flat); After Effects UI shots
  that are not the speaker's own recordings.
- Fonts: Instrument Serif (no Cyrillic); the reference's Helvetica Neue / Neue Haas Grotesk look is not on disk
  (Inter Tight 700 stands in; no font downloads).
- On paper or in a print: anything the B-roll people rules exclude (people-rules.json), nudity, photos of crowds or
  groups (the founding reel's crowd is drawn: dots from above, no faces).
- A UI sweep or swoosh standing in for a paper flip; a "comment X" CTA; the pen outro.
- An AI model's verbal account of the reference (a yellow caption highlight, 57 "swooshes", a white title): measured
  frames and stems only.

## Changelog
- Founded from a reference reel by @chrismoran__ and a founding talking-head reel.
- Recipe written from the study's findings, spec and replica and from the founding reel as approved: thesis,
  invariants 2-12, slots S1-S9 with generators, procedure, prerequisites, sound, not built, rejected. Builder
  tactile.py + tactile.js + props.py; the founding generator rebuilt its reel pixel for pixel (11 snapshot pairs,
  0 pixels differ) and redrew its props byte for byte. house.json filled with the measured values; catalog.json: the
  30 components the founding reel used and 12 ideas not built yet.
