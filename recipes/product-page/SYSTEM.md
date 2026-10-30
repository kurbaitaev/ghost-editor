# Product page as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it Product page, the slots
follow the content, catalog.json records what each reel used so the next one does not repeat it. The reference is a
tool demo by @adrien.ninet, measured frame by frame (the logic, every frame, and a replica of its first 9 s); the
founding reel applied it to a talking head about a book's advice on phone habits (approved 2026-10-24). Fold in what
the user loves later: edit house.json and this file.

## Thesis
**Show the named thing, do not tell it: every "what / how" line becomes a white product page (the real picture, the
rebuilt UI state, a hairline drawing of the noun) that a virtual camera moves through on the speaker's words, while the
speaker's face, as shot, carries only the lines said to the viewer.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no grade, no filter on the face; every insert is conformed to the plate; B-roll
   obeys the people rules (`people-rules.json`) and shows its line (references/broll.md section 0).
2. **The page carries the thing.** A line that names a thing or a step is shown on a white page, never only told on
   the face: the real picture of the named thing (a cover, a product, an app), the rebuilt UI state the line describes,
   or a hairline drawing of the noun the speaker says. The thing's own colour, sampled as it sits on screen, is the one accent.
3. **The face for the lines said to the viewer.** The claim, the reason, the encouragement are the face: full frame
   as shot, or a cut-out (BiRefNet matte, pixels untouched) over a rounded footage card when a page shares the screen
   (the hook, a split). The face is on screen at least 45 % of the reel (the reference's 24 % is too little for a
   talking head).
4. **Two caption voices, chosen by the layer.** Over the footage: big two-tier white captions on the chest (heavy sans
   + the payoff word in italic serif). Over a page, a split or UI: the one spoken word in the grey pill. On a page the
   title is black type on white. Never two caption systems at once; the pill is off while a title is up and while the
   words are on screen as UI text.
5. **Cut on the sentence, move inside the page.** A hard cut on the first word of a sentence, and a new sentence takes
   a new layer (page, split, UI page, face). Every other move is a virtual camera inside the page: the measured push
   on arrival, a zoom-out that makes room for the title, a push to the detail on the word that names it, an
   accelerating zoom into the cut. The face only gets a slow linear push.
6. **The demo acts the line.** Every UI action and every change in a drawing lands on the word that names it, within
   2 frames: a press on its verb, a toggle on its app's name, a bead hop on each word, a tile shrinking on the payoff.
7. **A list becomes a stack of drawings.** A spoken list is one drawing per noun, each arriving on its word, ending in a
   zoom-out and a two-tier title; the end gathers the reel's own drawings and changes one of them on the payoff word.
8. **Sound only where something enters.** A ducked plucky bed that drops out under the hook payoff and returns with the
   first setup page; SFX only on entrances and UI actions; none on pill swaps, caption words, bare cuts or the payoff
   title.
9. **Plain claims, flat ending.** On-screen text never claims what the speaker did not say (plain-fact labels only: a
   title, an author, an app's name); no em dashes; captions at least 48 px and 3:1 against what is behind them; no
   comment-keyword call to action and no outro card: the reel ends on the payoff title.

## House look (fixed: one house look per style)
`house.json` in this folder: palette (white #FDFDFD pages, ink #0F0E0E, the grey pill, line-art greys
#9A9A9A / #B2B2B2 / #C8C8C8 with one black active part, the hook and split gradients, soft shadows on objects only),
type (Inter Tight 800 + Playfair Display Italic 600 for titles and captions, Inter Tight 700 66 px in the pill, Inter
for rebuilt UI; Playfair stands in for the reference's Instrument Serif, which has no Cyrillic), layout and geometry
(the hook card inset 1290 r 66, the split card inset 1390 r 60 at x0.87, the pill slot y 1098-1194, captions from
y 1150), the insert frames (card, badge, tile), the motion system (measured push, zoom-for-title, push-to-detail,
expo.out entrances, the whip, live loops, UI actions on their words), the sound and the budgets (face >= 45 %, a page
<= 6 s, <= 3 inserts a minute). `productpage.py` reads palette, sizes, geometry and budgets from it. The components that
fill the slots are NEW every reel (`scripts/components.py plan --style product-page`). A new house element only enters
when the user asks for it, and then it replaces the old one in house.json.

## Slots and their generators (the components are new every reel; catalog.json lists what was used)

| slot | its job | generator: the question that fills it from a new script | the founding reel used |
|---|---|---|---|
| S1 hook device | frame 0 names the thing and the claim, with the face | what is the named thing as an object (a file card with its real picture as the badge, an app icon, a product shot), and which 2-3 tiers say line 1, payoff word in the serif? | a dark file card (the book's title, a chevron and its author) with the real cover as its badge, a 3-tier headline, the matted head over the card |
| S2 subject page | the subject of line 2 as a picture | which noun is the subject, drawn in hairline with one live black part, and which words make the title? | an exploded phone with a hopping tile, the measured push, a two-tier title naming the subject |
| S3 the real thing | show the named thing itself | is there a real picture of it (cover, product, screenshot) and which detail does the speaker name, for the push-to-detail? | the cover rises from below, push to its title on the word naming it, accelerate into the cut |
| S4 the step | the action the speaker asks for | what does the speaker tell the viewer to do, and which UI state shows it (an alert, a prompt, a button)? in a split when the face should stay | split: a bell icon drops on the verb, an iOS permission alert, its deny button pressed on its word, the bell slashed |
| S5 the specifics | the named items act | which items does the speaker list, as rows / cards that change on their names? | iOS Settings, three named apps' toggles go off on their words |
| S6 face beats | the lines to the viewer, and the pivot | which lines are said to the viewer, which word of each is the serif payoff, which line is the three-voice pivot, where does a reframe cut keep it alive? | three face beats, a reframe cut to the tight plate, a three-voice pivot line |
| S7 list stack | a spoken list as drawings | which nouns, one drawing each, and which transition joins them (a whip, a rise from below, a push through)? | bed, whip, sneaker, mugs + teapot; a two-tier title |
| S8 effort split | a concrete metaphor beside the face | which line is about effort or progress, and which object moves on its words? | a staircase in the split panel, the bead hops a step a word and falters on the last |
| T transitions | join two pages without a flashy cut | which page-to-page move carries the content (the hook wash, a whip, a reframe cut, a pull-back)? | hook wash + card exit, whip between drawings, reframe cut on the face |
| S9 outro | the payoff as a picture, then a flat end | how do the reel's own drawings show the payoff (something shrinks, fills, lights up) on the payoff word, and which title tiers close it? | gallery of the drawings, the 2x2 phone tile shrinks to one cell on the payoff verb, veil, a two-tier title |

## Planning procedure
1. `python3 $S/scripts/taste.py prompt --style product-page` and `python3 $S/scripts/components.py plan --style
   product-page`: the user's rules for the style, what the last 7 reels used (avoid) and what is free.
2. `$P/build/plan.txt`: the script word for word (fix names on screen, never in the voice); for each line its slot and
   layer (page / split / UI page / face), the words it lands on, which word gets the serif, where the scene cuts sit (on
   the cuts of the plate), the pill windows; frame 0 must read on its own; the sound plan; the accent.
3. Fill each slot from its generator with a component the last reels did not use; register each new one first:
   `components.py add --style product-page --id <id> --kind <kind> --slot S<n> --sig '<regex>' --desc ...`.
   New drawings are drawn with the kit in productpage.py (Art, iso, box, line, cyl), new UI with HTML builders like
   ios_alert / ios_list; give each a stable id or marker so its sig finds it.
4. Prerequisites in $P (below), then write the generator from the usage block in productpage.py's docstring (the public
   edition has no worked example for this recipe yet) and build it (`~/.venvs/media/bin/python reel.py --project $P`):
   the guards and budgets must pass. `bash $S/scripts/hf.sh lint $P` (0 errors), `python3 $S/recipes/seoul-list/snap.py
   beats $P`, `components.py check --style product-page --project $P`; look at every beat (the face clean, the pill
   clear of the head, titles inside x 110-970, nothing in the IG bands).
5. `python3 $S/scripts/finals.py preview $P --out $P/finals --style "Product page" --code <code> --title "..."` and WAIT
   for the user's OK before `finals.py render`.
6. After the user's yes: `components.py record --style product-page --project $P --reel <code>`. If the user loved it,
   ask what to keep and fold it into house.json and this file.

## Prerequisites (what the style needs; never fill a gap with stock)
- The approved cut: the plate(s) as shot (a wide plate; a tight plate if a reframe cut is planned), the voice, the words
  in edit seconds, `face_track.py` on every plate (build/face.json, build/face_<plate>.json).
- A BiRefNet matte of the plate over the hook and every split window: `scripts/matte.py <plate> -o
  assets/<plate>_matte.webm --ranges 0-<hook end + 0.4>,<split windows>` (the founding reel: 275 frames, ~7 min on an
  Apple M4, 24 GB).
- The real picture of the named thing (cover, product, app icon, screenshot) through `insert_prep.py --ref <plate>
  --line ...` and shown on a `broll_vision.py picks` sheet; the badge copy at 2x for the hook.
- For a software tool: clean high-res screen recordings of the tool, cursor visible, no browser chrome (the reference's
  pages were real recordings). Phone settings and system alerts can be rebuilt in HTML (ios_alert, ios_list). No stock
  video on the pages; drawings are drawn per reel in SVG, no downloads.
- build/metrics.json (advance widths) is written on the first build by fontwidths.py (needs ~/.venvs/ghost-captions).

## Sound rules (measured: reference 3.6 SFX per 10 s, the founding reel 4.3)
- The bed: plucky minimal tech (library "infinity"), ~22 dB under the voice, ducked 8 dB, with a drop-out under the hook
  payoff (`music["drops"]`) that returns with the first setup page.
- Sounds sit on graphic entrances and UI actions within 2 frames: pop-1 on the hook card at frame 0, a soft whoosh
  leading the hook wash, a trimmed swell on a push-to-detail or a page entrance, click-1 on a press, tick-1 per toggle
  or icon change, a quiet hit 2 reference frames after the cut into a face beat, the whip whoosh landing with the
  incoming drawing (not at the midpoint), a soft whoosh-2 on a panel slide, pop-3 on a tile change.
- Never on pill swaps, caption words, bare cuts or the payoff title. Missing from the library (worked around so far):
  a soft wide air swell, a slider drag, hover ticks, a UI toggle click.

## Not yet built (catalog.json ideas_not_built_yet)
- Real screen-recording pages: zoom-to-field into a light app window, caret-follow typing with a slash-command chip,
  pull-back to a window card then dive, a cursor-following camera, the demo retimed so each action lands on its verb.
- A dark-mode flip on the word (one-frame palette invert), a chat reply streaming with an option highlighted, the
  4-frame blank beat, the pivot line on the speaker's own desk B-roll while the bed is out.
- A feathered left-to-right reveal and gradient fill on the payoff word; the end-tail riser; the reference's
  illustration tool as a per-reel illustration generator (licence check first).

## Rejected (do not copy)
- The comment-keyword CTA, twice in the reference (early at 27 % and at the end, keyword in an accent box): only with
  a real offer; the ending stays flat.
- The reference's face share (24 %): a talking head needs at least 45 %.
- Instrument Serif and the reference's SF-like pill face: not on disk and no Cyrillic; Playfair Display and Inter
  Tight stand in (one house for Russian and English).
- The reference's brand look as a default: Claude's orange is that reel's accent; each reel samples its own thing's
  colour.
- Per-pill whooshes and the "0.2 s zoom-blur between scenes" Gemini reported: measured false (hard cuts, silent pills).
- Stock B-roll of strangers or stock video on pages; any picture the people rules (people-rules.json) exclude.

## Changelog
- 2026-10-24: founded from a reference reel by @adrien.ninet and the founding reel built from it.
- 2026-10-24: the system written from the frame-by-frame study, the replica and the founding reel: thesis, nine
  invariants replacing the scaffold's two placeholder invariants, slots S1-S9 + T, prerequisites, sound rules,
  rejected list. house.about, house.layout, house.type, house.palette, house.insert_frame, house.sound and
  house.vary_per_reel filled with measured values; new keys geometry, motion, budgets. Builder productpage.py (+
  fontwidths.py) generalised from the founding reel's generator. catalog.json: the 27 components of the founding reel
  with sigs, 14 ideas not built yet.
- 2026-10-30: public edition: the founding reel's worked example is not shipped (it holds a private script).
