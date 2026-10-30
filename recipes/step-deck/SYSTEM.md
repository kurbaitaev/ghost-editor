# Step Deck as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it Step Deck, the slots
follow the content, catalog.json records what each reel used so the next one does not repeat it. Filled from a
reference reel by @ant.lon (a 55 s "hook stacking" tutorial, torn down frame by frame: elements E1-E29, transitions
X1-X9) and from a founding talking-head reel built and approved in this style. Fold in what the user loves later by
editing this file and house.json.

## Thesis
**A tips reel as a numbered deck: every spoken word lands on screen on its onset, sized by how much it matters and set
behind the speaker's head, the reel changes world every 1-2 s between the face and flat full-screen cards, and each
step opens on a card whose giant italic numeral shrinks into place, so the viewer always knows where they are in the
list.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no grade, no filter on the face; every insert is conformed to the plate; B-roll
   obeys the people rules and shows its line (references/broll.md section 0).
2. **Every spoken word lands on its onset.** A word appears on the frame it is spoken, as a new caption state, as a
   phrase growing in place (the first words already sit where the finished phrase is centred) or as a sub-line under
   it; states swap hard. Only the first word of a face world fades in (6 frames, 30 px rise), and a stressed word may
   flicker on (E8). Nearly every frame carries text (the reference: 97 %).
3. **Size is importance.** Every word gets a tier from what it carries: tiny for connectives, mid, big for the content
   word, the serif italic voice for the payoff or abstract word of a clause (about 1 in 6, never two in a row). A line
   shrinks to fit 930 px, but no caption word goes under 56 px (the rule: at least 48 px).
4. **On the face the words sit behind the head.** The caption layer lies between the plate and its matte, its baseline
   on the crown of the head plus the tier offset, so the head covers the lower part of the words. On cards the words
   ARE the graphic, centred.
5. **A new world every 1-2 s.** The face (35-45 % of the reel) alternates with full-screen cards and pictures; every
   look-away is under a card. Hard cuts land on word onsets; the motion lives in the elements (push-backs, the
   shrinking numeral, element whips, blur ramps before a cut), never in a frame effect on the face; one punch-in per
   reel at most.
6. **Every step opens on its own card.** The word that names a step cuts to a full-screen step card: the colour field
   rotates navy, off-white, electric blue; the giant italic numeral enters big and blurred and shrinks into place
   while a 10-frame glow steps down hard; the speaker's words land on top. Questions and turns get a navy word card,
   statements a white word page.
7. **The hook is a stack.** The first three lines (the challenge, the pain, the outcome or promise) each get their own
   world, loud then quiet then the face again; frame 0 is the face with the first word big behind the head.
8. **Pictures are the nouns of the speaker's lines, made for the line.** Objects as B&W paper prints, ideas as line
   drawings on the white page (each part pops in on its word, the thing being said stays sharp, the rest goes soft),
   one metaphor clip framed in a paper panel before it goes full screen. No people except one person doing the line's
   action.
9. **One small palette, one gradient word.** Navy, off-white, cream, electric blue; red only on the hook montage words;
   at most one gradient word in the whole reel, the payoff, behind the head.
10. **Sound marks worlds, not words.** A steady bed about 9 dB under the voice from frame 0 to the end; a sound only
    where a world changes or something enters (3.5-4.5 per 10 s): whooshes lead the cut by 3-10 frames, risers end on
    it, hits land on it; nothing on caption swaps; the payoff is quiet.
11. **A flat ending.** The payoff lands on the face and the reel ends on the last word: no comment-keyword call to
    action, no pen outro, no end card.

## House look (fixed: house.json)
`house.json` in this folder holds what stays reel to reel: the palette (navy #0B1829, white page #F1F1F1, cream
#EAE4C0, paper #FAFAFA, ink #0F1827, warm #FAE9D4 on navy, red #D30B20, electric blue #2534E9, the three step looks
and the 8-stop gradient), the type (Inter Tight 600 captions in tiers, Inter Tight 700 for the red montage words,
Playfair Display Italic for the serif voice and the numerals, Playfair Display caps squeezed x0.88 for titles and
labels, Montserrat 800 for the gradient word; the Cyrillic substitutions for Instrument Serif and Plus Jakarta Sans),
the tiers and offsets, the layout (captions on the crown of the head; cards centred on y 960), the insert frames
(paper print, paper panel on navy, full screen with tinted captions, line drawings, the cream icon card), the motion
(30 fps, the curves and stepped keys measured in the study), the sound and the budgets. The builder `stepdeck.py`
reads its palette, type and keys from house.json. The components that fill the slots are NEW every reel
(`scripts/components.py plan --style step-deck`). A new house element only enters when the user asks for it, and
then it replaces the old one in house.json.

## Slots and their generators (the components are new every reel; catalog.json lists what was used)

| slot | its job | generator: the question that fills it from a new script | the founding reel used |
|---|---|---|---|
| S1 hook stack | three worlds for the first three lines: challenge, pain, outcome | which three opening lines are the challenge, the pain and the outcome, and which world does each get: the face with the first word behind the head (always first), a loud picture world of the line's objects, a quiet card (tiny words around one icon), a title over the face? | face push-back on the opening question; a B&W print flicker + red words (laptop, letters, headset, calendar, clock, desk) for the end-of-workday line; a cream disk with a moon that empties on the pain word |
| S2 word cards | carry the lines between face worlds | which line is a question, a doubt or a turn (navy card, phrase append), which a statement (white page), and which one word in it flickers? | navy cards for the doubt and the turn lines; white pages for the statements (one exit to white) |
| S3 promise card | the reel's promise, once, before the steps | what is the promise line, and how does it land: caps title block, a blue title bar over the face, a quote box? | a caps title with RGB split |
| S4 metaphor insert | the one concrete picture of the idea | what image carries the whole idea (a person doing it, an object), and how is it framed: a paper panel on navy with a label, then full screen with captions tinted to its light? | a craftsman at work (one stock clip): panel + a serif label, then full screen with tinted captions |
| S5 step cards | one card per step the speaker names | how many steps are named (2-5), and which word is each label? the look follows the rotation | Step 1 navy, Step 2 off-white, Step 3 blue, each with its label line |
| S6 step pictures | show each step in a different mode | for each step: a line drawing of the noun with rack focus, a callback to an earlier picture, a counter for a number, or the face with big captions? never the same mode twice in a reel | five unfinished tables -> a jump onto one, its leg draws on the line's last words; the tables return with a blue box under the noun; a counter 1 -> 10 on the number |
| S7 transitions | the joins between chapters (one or two of each at most) | which chapter changes get a move: exit to white (X3), fade-up from dark (X7), blur-out before a step (X1), push-out / push-in whip (X4), the one punch-in (X8)? | X3 into the metaphor clip, X7 on the panel, X1 into Step 2, X4 from Step 3 to the face, X8 on the clause the speaker leans on |
| S8 ending | the payoff, held, flat | which word is the payoff, and how does it land on the face: the one gradient word behind the head, a serif word alone, the hook's picture back? | the payoff word as the one gradient word (Montserrat 800) behind the head, flicker-on + rise |

## Planning procedure
1. `python3 $S/scripts/taste.py prompt --style step-deck` and `python3 $S/scripts/components.py plan --style
   step-deck`: the user's rules for the style, what the last 7 reels used (avoid) and what is free.
2. The script word for word (build/words.cut.json, edit seconds). Write build/plan.txt: every line -> its world -> its
   slot -> the word it lands on -> the tier tokens. Mark the three hook lines, the promise, the step labels and the
   payoff; leave the connecting lines to the face and the word cards.
3. Fill each slot from its generator with a component the last reels did not use; register each new one first:
   `components.py add --style step-deck --id <id> --kind <kind> --slot S<n> --sig '<regex>' --desc ...`.
4. Pictures: B&W object stills (`broll_gen.py`, no people) and at most one clip (`broll_fetch.py`, 1080p or better, or
   the speaker's own footage); each through `insert_prep.py --ref <plate> --line "<words under it>"`, then
   `broll_vision.py picks $P` (build/broll-picks.jpg); prints with `make_prints()`.
5. Write $P/tools/build.py from the usage block in stepdeck.py's docstring, the worlds from plan.txt, run it with a
   python that has the media tools (e.g. `~/.venvs/media/bin/python`); `hf.sh lint $P` (0 errors); read
   build/coverage.txt (face %, no look-away showing); snapshot every beat onto one sheet and look at frame 0 and the
   busiest moment at 1080x1920; `components.py check --style step-deck --project $P`.
6. `finals.py preview $P --out $P/finals --style "Step Deck" --code <code> --title "..."` and WAIT for the user's OK
   before `finals.py render`.
7. After the user's yes: `components.py record --style step-deck --project $P --reel <code>`.

## Prerequisites
- An approved cut: a talking head with a list in it (2-5 steps or tips are named); the plates as shot (wide + tight
  framings are best, one works), assets/voice.wav, build/words.cut.json in edit seconds, build/cover_windows.json.
- A matte per plate (`scripts/matte.py`, BiRefNet: assets/<plate>-matte.webm with alpha): the captions behind the head
  need it; the crown of the head per face world is measured from it (build/crowns.json). A mic in front of the chest
  helps the depth but is not needed.
- Pictures are made per line (generated object stills, line drawings); the style must never depend on stock of
  people. One metaphor clip at most, 1080p or better, checked against the people rules. No screen recordings needed.
- Fonts, SFX and the bed come from the skill (templates/fonts, library/sfx, library/music); the builder copies them.

## Sound
- Measured in the reference: 24 SFX in 55 s (3.6 per 10 s on world changes), a steady 88.6 BPM boom-bap bed 6-9 dB
  under the voice, the loudest events (a riser into a chapter, a sub boom on the biggest reveals) about level with the
  voice, everything else under it. The founding reel: 27 SFX in 63 s (4.3 per 10 s), the library bed lo-fi-02 at 0.18.
- A sound only where a world changes or something enters: a whoosh into a card or back to the face (3-10 frames
  before the cut), whoosh-cine into a picture world, a back-timed riser ending on a step card with a cine hit on the
  cut, a boom on frame 0 and on the biggest reveal, pops and clicks 1-4 frames after a diagram item or a counter.
- Never on caption swaps or cuts inside a run, never a meme sound, never the voice lifted or ducked; the payoff gets
  one quiet whoosh at most.
- When the founding reel was built the library lacked a reverse whoosh, a short gap riser and paper / print flips
  (stand-ins: riser-1 trimmed, cinematic-rumble-riser trimmed); the CC0 pack now has whoosh-reverse, riser-short,
  paper-flip and paper-riffle. Still missing: a real boom-bap bed. List any stand-in in the report.

## Not yet built (catalog.json ideas_not_built_yet)
- A tight hook stack inside 5-6 s (the founding reel's ran 0-12 s: its approved lines sat at 0 / 5.6 / 10.2 s).
- The reference's other devices: the title bar with a centre-out blue box over the face (E10), the recap row of live
  mini cards of the reel's own hook (E19), the 3D flip deck of the speaker's assets (E28), the name mind map (E12), the
  stats card with live counters (E15), the quote box (E25), the hook diagram with connector lines and a depth-of-field
  camera (E24 full), the B-roll keyword colour ramp (E9), the motion-blur caption slide-in, glow and tracked captions
  (E26, E27).
- Grain and a soft vignette on the pages; cuts snapped to the bed's beat; a diegetic prop action when the speaker
  records; a tagger that picks the tiers.

## Rejected (do not copy)
- The comment-keyword call to action ("Comment PRESET"): a flat ending unless there is a real offer.
- The reference's B&W aside on the talking head (E11) and its teal-green A-roll grade: the face stays as shot; black
  and white is for pictures only.
- Filler words at 2-3 % of the frame height (about 40 px): under the 48 px floor; the tiny tier is 64-68 px.
- The montage at frame 0 (the reference opens on its eye montage): the face goes on frame 0, so the montage is the
  second hook.
- Speeding the take up to the reference's 244 words a minute: not without the user's OK (pauses and flow are theirs).
- The reference's content (eye macros, the creator's name map, the creator's asset screenshots): pictures show the
  speaker's own nouns.
- Instrument Serif and Plus Jakarta Sans (no Cyrillic); SVG `filter:url(#id)` (HyperFrames 0.8.159 renders every
  other clip black; the RGB split is three channel copies); an AI model's ~57 "swooshes" (the bed's clap, not SFX).
- Never: em dashes on screen, words the speaker did not say, the pen outro, anything the people rules exclude in any
  picture.

## Changelog
- Founded from a reference reel by @ant.lon and a founding talking-head reel.
- Recipe filled from the every-frame spec, the replica and the approved founding reel: the thesis, invariants 2-11,
  the slots and generators, prerequisites, sound, not yet built and rejected sections written; house.layout,
  house.type, house.palette, house.insert_frame, house.sound and house.vary_per_reel filled with the measured values
  (new keys: world, layout_px, steps, motion, budgets); builder stepdeck.py (class Deck) generalised from the founding
  reel's one-off generator; catalog.json records the founding reel's 24 components.
