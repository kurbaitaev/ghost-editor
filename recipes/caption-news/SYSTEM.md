# Caption News as a system

Same method as recipes/step-deck/SYSTEM.md: the invariants and the house look make it Caption News, the slots follow the
content, catalog.json records what each reel used so the next one does not repeat it. Ported from the
MIT-licensed lemo-opuscar style "Caption News" (styles/caption-news, demo film "The Bee Ledger", 16:9, 59.5 s; credits in
CREDITS.txt) and adapted to a vertical talking head. The example column below is a reel about a cluttered desk (the
usage block in captionnews.py's docstring).

## Thesis
**A talking head that reads with the sound off: the speaker's face as shot is the ground, the speaker's words are the lead actor, slammed
onto the lower band a chunk at a time with one keyword on a honey block; whenever the speaker names a source, a list or a
quantity, the reel cuts to the evidence (the document highlighted, a lit grid, a ruled list on the ledger sheet) and
back to the speaker's face.**

## Invariants (never change: this is the style)
1. **The speaker's face as shot** (the house rule): no grade, filter, tint or gradient on the speaker's plates; no caption,
   chip or page above the chin. The original grades every shot and lays a bottom gradient under the captions; here each
   caption line carries its own ink slab instead (it reads on any clothing).
2. **Sound-off first.** Every beat is understood from the picture and the captions alone. Every spoken word is on
   screen, in order (build() checks it); cards carry the words they show (`said`).
3. **The caption is the shot.** One caption at a time in the lower band (x 64, max 916 px wide, bottom at y 1680):
   2-3 chunks per caption, stacked on lines, each slamming in (scale 1.3 -> 1 in 0.13 s, back 1.6) on the onset of its
   first word; at most ONE keyword per caption on a honey block that wipes left to right in 0.12 s, the word turning
   ink. Inter Tight 900, 84 px (verdict 100-105 px), never under 60 px.
4. **A hook on frame 4.** The first caption lands at 0.13 s, its chunks 0.07-0.13 s apart, its keyword in a giant honey
   block: the only caption allowed to run ahead of the voice.
5. **A title sting becomes the bug.** Early on, a honey ruled page (rules drawn staggered, red double margin) wipes over
   the bottom band while the speaker's face stays live above; the title slams word by word, a chip follows; the page wipes off
   left and the title lives on as the bug top left (honey block + dark chip, 48 px caps) to the end.
6. **Evidence on screen.** A source the speaker names gets a document beat: the source itself on a dark desk, tilted, pushed in
   (never past 1:1), highlighter rectangles swept over the words as the speaker says them, the key words re-set in a honey block
   beside it, and a source tag (SOURCE + the label) under the bug. A number appears only with its source on the same
   shot; no number is ever invented.
7. **Short cutaways on the ledger.** Lists and quantities leave the speaker's face for 2-4 s on the ledger sheet (#151512, ruled
   every 54 px, red double margin), which slides in from the right in 0.18 s with honey streaks and pushes 1.0 -> 1.03.
   The speaker's face stays 60-75 % of the reel.
8. **Colour has meaning.** Honey = the point (keyword, bug, lit panel, active row); red = the bad thing (notification
   dots, losses); ivory = everything else; grey = labels and unlit items.
9. **Sound only where something enters.** Voice + SFX, never a bed: a hit on frame 4, a pop under each keyword wipe,
   paper and whooshes into pages and cards, a marker under each highlighter sweep, pops as panels light, clicks as rows
   land, one soft boom under the verdict.

## House look (fixed: house.json)
Palette (ink, ivory, honey, loss red, greys, ledger, desk, slab), type (Inter Tight 900 for everything, 600 for source
labels; Latin + Cyrillic, the stand-in for Noto Sans SC), the lower-band caption card, the bug and source tag (48 px), the sting
band (y >= 1140), the document desk, the grid and list geometry, the motion constants (slam, wipe, card-in, grid rise,
list rows, highlighter), the sound kit. `captionnews.py` reads all of it from house.json.

## Slots and their generators (the components are new every reel; catalog.json lists what was used)

| slot | its job | generator: the question that fills it from a new script | example (the desk reel) |
|---|---|---|---|
| S1 hook | frame-4 hook | which first line is the hook, and which word in it gets the giant block? | «Your desk is stealing your {focus}.» stacked, block 1.6x |
| S2 title + bug | name the story once, then sign every frame | which line names the subject (3-4 words), what is the chip (a true framing: where the advice is from, a date), and how does the bug split (honey / dark)? | YOUR / DESK / AND FOCUS, chip ONE SIMPLE RULE, bug DESK / AND FOCUS |
| S3 evidence | the source the speaker names | what is the document (cover, page, screenshot of the real thing), which words get highlighted on which spoken word, what is re-set in the block? | the page of the guide the speaker names; its title highlighted; block CLEAR DESK; tag SOURCE + the guide's name |
| S4 list card | a list the speaker names | how many items, and which card: lit grid (things, each with a drawn icon), ruled list (actions), split (two sides)? | lit grid: Mail / Chat / Feeds with drawn icons + red dots; ruled list: Sleep / Move / Call a friend |
| S5 quantity card | a number the speaker says | is there a true, sourced number? then a chart on the ledger (line, bars, proportion by darkness) with its source tag; if not, no chart | none (the reel has no numbers) |
| S6 keywords | one per caption | which word in each caption carries the meaning? never a filler word, never two in one caption | focus, won't, ... (one per caption) |
| S7 ending | the verdict | which last line is the verdict, and how does it land: bigger captions on the speaker's face, the hook's block back, the last card's point as the caption? | verdict on the speaker's face (wide) at 100-105 px, its last words in the block, a soft boom |

## Planning procedure
1. The speaker's words word for word (build/words.cut.json, edit seconds). Write the plan as a docstring at the top of
   build.py: every line -> the speaker's face or a card -> its chunks (2-3, each on a word onset) -> its keyword.
2. Mark the hook, the title line, every source the speaker names, every list, every number. Numbers: verify each from a primary
   source before it goes on screen; no source, no number.
3. Choose plates (the speaker's own tight / wide switches on caption changes) so the speaker's face stays 60-75 %.
4. Write $P/tools/build.py from the usage block in captionnews.py's docstring, run it; build/coverage.txt must say "every
   spoken word on screen in order".
5. `hf.sh lint $P` (0 errors); snapshot every beat (the keyword wipes, each card mid-way and complete, the sting) and
   look at frame 0 and the busiest frame at full size: nothing above the speaker's chin, nothing outside the safe area.
6. `finals.py preview ... --style "Caption News"` and WAIT for the user's OK.

## Prerequisites
- A talking head with something to show: a named source (book, study, article), a list, or a number. A reel with none
  of these is only captions: still the style, but thin.
- The source itself in a usable size (cover >= 600 px wide, or a real page). Never a fake document.

## Sound
- Measured in the port's proof reel: 32 SFX in 32 s, almost all short pops under keyword wipes and card actions (pop-3 at 0.22).
- Kit (house.json sound.kit): impact-2 hook, pop-3 keyword, whoosh-cine card in, paper-flip sting / document,
  whoosh-reverse sting out, marker-scribble highlighter, click-1 source tag / list row, pop-1 grid light, deep-boom
  verdict. The original's score (120 BPM, brass on numbers, silences before the turn) is not ported: no music.

## Not yet built
- Charts on the ledger (line drawing segment by segment, bars with the point first, proportion by darkness): need a
  reel with true, sourced numbers. Rolling counters with fixed-width digits (num()).
- Split screen (two counters racing), the map with a mask transition into a photo, the freeze frame (not on the speaker's face).
- Real silences before the turn and the verdict (would need a re-cut with the user's OK).
- A second-language line under the caption (the original's bilingual card): only at >= 48 px.

## Rejected (do not copy)
- The grade, the warm soft-light layer, the bottom gradient on footage, grain: the speaker's face as shot.
- The 120 BPM score, the half-beat cut grid: no music; cuts land on the word onsets.
- Captions spaced 0.12 s apart at the caption start (the original): on the speaker's face no word shows before it is said,
  except the frame-4 hook.
- The 17-33 px bug, credits and second-language line: under the 48 px floor; chrome is 48 px.
- The fictional channel name, the demo's footage, report and map: not copied (CREDITS.txt).
- Punch-in and freeze frame on the subject: never on the speaker's face.

## Changelog
- v0.3.0: ported from lemo-opuscar styles/caption-news (MIT, (c) 2026 LemoLab); builder captionnews.py (class News),
  house.json, catalog.json. Proved on one talking-head reel; no worked example ships yet.
