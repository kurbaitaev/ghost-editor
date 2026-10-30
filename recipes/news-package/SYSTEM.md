# News Package as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it News Package, the slots
follow the content, catalog.json records what each reel used so the next one does not repeat it. Ported from the
MIT-licensed lemo-opuscar style "Broadcast News Package" (https://github.com/lemomo-ai/lemo-opuscar,
styles/news-package/STYLE.md + demo/main.js; CREDITS.txt) and proven on a 32 s talking-head reel. The source is a 16:9
four-story bulletin with no anchor and no footage; here the speaker is the anchor of a one-story segment and the package
frames their talking head. The user's notes on a preview go in with `taste.py`.

## Thesis
**The speaker's talking head as the anchor of a one-story news segment: one package system (plate, bug, strap, tab,
rundown, band wipe, stamp) used the same way every time, so the viewer reads the system before the words; the face
carries the voice with the headline on a strap on the speaker's chest, and each point they make cuts to a full-frame
package card that states one fact, in the bulletin's order: sting, rundown, the points, the rundown ticked off.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no grade, filter, tint or effect on the face plates, and nothing drawn over the face;
   the only "camera" is switching between the speaker's own framings on their jump cuts. The strap sits on the chest
   (below the chin), the bug on the ceiling above the head.
2. **The sting becomes the bug.** The brand plate slams in, its letters drop, the wordmark opens from the centre, a
   glint, then the same plate flies to the top right and stays there as the bug until the end. Opening and programme
   are one object. The channel word is neutral (ON AIR, in the reel's language), never a real or fictional channel name.
3. **The strap holds the headline.** From the first face shot to the recap one lower-third strap is on screen: the
   lemon tab names the category (numbered for a point: "01 · NOTIFICATIONS"), the paper body carries a short headline
   of the speaker's line and an olive sub-line. On the face it flips (new words up from below, old up and out, 0.32 s;
   the tab flashes white on a new category); on a cut or under a wipe the new picture brings its own strap words. It
   never wraps, never goes under 48 px, never leaves mid-segment.
4. **The rundown opens and closes.** After the sting and the opening line, the rundown lists the reel's points
   (numbered rows flipping in, each with a mono timecode of when it airs); at the end the same object returns as the
   recap (RECAP) and each row is ticked on the speaker's last words.
5. **One fact per card.** A full-frame card on the ink studio background states one thing: the document the speaker
   names, the switch, the list, the line that breaks, the proportion. Every card is built from the same parts:
   accent-edged ink cards (6 px lemon top), mono eyebrows, push-up titles, one stamp at most per point.
6. **Three transitions only.** The lemon band wipe between parts (sting, rundown, each point, recap); a hard cut with a
   low impact inside a point (card to the face and back); nothing else (no dissolves, flips of the frame, zooms on the
   face). The incoming picture's entry animation already runs under the band.
7. **A package action every 0.5-1 s inside a card**, landing on the speaker's words (a row flips, a tile flips, a box
   ticks, a line step, a stamp), and the order inside a point: what (title) -> how big (board / line / bar) -> what it
   hits (rows / cells) -> the verdict (stamp / readout).
8. **Facts first.** Nothing on screen beyond what the speaker says and the source they name; the source line sits under
   the strap while a point rests on it. A graphic with no data behind it is a schematic: it carries the SCHEMATIC
   corner tag and no numbers.
9. **Sound marks package actions, never music.** The voice + short SFX only: a hit on the sting, a whoosh on every band
   wipe, a low impact on hard cuts, pops as rows land, ticks on flaps and line steps, a stamp thump, the heaviest hit
   (after a held beat) on the threshold crossing, clicks on ticks.
10. **A clean panel.** No word-by-word captions and no crawl: the strap carries the headline, the cards carry the
    facts. Every on-screen word >= 48 px inside the safe area (y 120-1700, x <= 980).

## House look (fixed: house.json)
`house.json` holds what stays reel to reel: the palette (ink #121417, ink2 #1B1E23, ink3 #22262C, lemon #F2CF1D with
#F8DE4A / #D8B30C, gold #D4B064, paper #F4F1E8, olive #6E5A1E, reserved breaking orange #FE6B3D), the type (Fira Sans 800
for headlines in place of Noto Sans SC 900; Fira Sans Extra Condensed 800 / 600 / 600 italic in place of Barlow
Condensed, which has no Cyrillic; IBM Plex Mono 500 for eyebrows, sources, tags and timecodes), the package parts (plate,
bug, strap, tab, rundown, band wipe, stamp, corner tag, studio background), the layout in 1080x1920 (bug centre
(825, 185), strap tab y 1322 / body 1390-1560, source line baseline 1630, card content y 260-1290), the motion (30 fps,
the sting timings, flips, push-ups, flaps, the threshold shake) and the sound roles. The builder `newspackage.py` reads
them. The graphics that fill the slots are NEW every reel.

## Slots and their generators (the components are new every reel; catalog.json lists what was used)

The last column is an illustration for an English reel about coffee ("how much caffeine is too much"), not a build.

| slot | its job | generator: the question that fills it from a new script | e.g. a coffee reel |
|---|---|---|---|
| S1 sting | open the segment, become the bug | what is the wordmark line (the reel's subject in 2-3 words) and the mono dateline under it? | ON AIR plate, "YOU AND COFFEE", "ONE SEGMENT · ONE STORY" |
| S2 rundown | list the points, then tick them off | which 3-5 points does the speaker make, in their order, as 1-3 word row titles, and on which last words do the ticks land? | 03 POINTS: The limit / What is in a cup / The afternoon cup; ticks on the closing line |
| S3 strap words | carry the speaker's line as a headline | for each face window: the category tab, a headline of the line in <= ~24 characters (the speaker's words, shortened, never a new claim), the sub-line, the source line if the point rests on one; where does it flip? | TODAY, THE LIMIT, 01 · YOUR CUP ... flips on the turn words |
| S4 source document | show the source the speaker names | do they name a real book, paper, post or page? its own picture as the document flying out, the title pushed up, one stamp with the gist | the page of the health agency the speaker cites, stamp ONE NUMBER |
| S5 point graphics | one fact per point | for each point: a state change (split-flap board), a list they name (check rows / cells), a set of equal things (accent cards + bracket), a rise or a limit (threshold line, schematic), a share of something (one-scale proportion bar), a quote (quote card), places (map)? never the same graphic twice in a reel | flap ON -> OFF for the late cup; a threshold line that crosses a dashed LIMIT; a proportion bar of the day |
| S6 face windows | the speaker's face as the anchor | which lines do they say to the viewer (the turn, the reassurance, the question)? those stay on the face with a strap flip; 35-45 % of the reel | the opening question, the turn, the closing line |
| S7 transitions | join the parts | where are the part changes (band wipe) and the cuts inside a point (hard cut + low impact)? | a band wipe per part, hard cuts inside a point |
| S8 ending | close the segment | the rundown ticked off (default), the last stamp holding, or a teaser card (ask the user) | the recap ticked, ends on the full list |

## Planning procedure
1. `python3 $S/scripts/components.py plan --style news-package` (what the last reels used) and the user's rules
   (`taste.py prompt --style news-package` once registered).
2. The script word for word (build/words.cut.json). Write build/plan.txt: every line -> face or card -> its slot ->
   the word it lands on. Mark the points for the rundown, the source the speaker names, the lines that stay on the face.
3. Fill each slot from its generator with a graphic the last reels did not use; check every label reads as plain calm
   language in the reel's language and claims nothing the speaker did not say; schematic graphics get SCHEMATIC and no
   numbers.
4. Write $P/tools/build.py (the public edition has no worked example yet: follow newspackage.py's docstring and this
   file), run it with `~/.venvs/media/bin/python` (it refuses words under 48 px and missing glyphs); `hf.sh lint $P`
   (0 errors); read build/coverage.txt (face share); snapshot every beat and look at frame 0, every card fully built,
   every strap flip and every wipe mid-band.
5. `finals.py preview ... --style "News Package"` and WAIT for the user's OK before `finals.py render`.
6. After the user's yes: `components.py record --style news-package --project $P --reel <code>`.

## Prerequisites
- The cut as shot (one framing is enough; two or three let the hard cuts change size on the jump cuts), voice.wav,
  words.cut.json in edit seconds. No matte.
- A script with 3-5 points (a list, steps, reasons). A single-point reel can still use the system (one lead package,
  a rundown of its parts), but the rundown is the style's spine.
- Pictures only of a real thing the speaker names; no stock people, no generated plates (the source's illustrative
  plates are not part of this port).

## Sound
- The proof reel: 43 SFX in 32 s (13.5 per 10 s), every one on a package action, all well under the voice:
  cinematic-cine-hit on the slam, whoosh-1/2/3 on wipes, impact-2 on hard cuts, pop-1/3 on rows and cards, tick-1 on
  flaps and line steps, impact-1 on the stamp, cinematic-deep-boom on the threshold crossing, click-1 on ticks and the
  bracket, cc0-paper-flip on the document, cc0-whoosh-reverse when a bar shrinks, ding-1 on the last tick.
- Denser than the house calibration (0.4-0.9 per 10 s) because the source's foley follows every package action; if
  the user finds it busy, drop the row pops and line ticks first.
- Never a music bed, a theme or a musical stinger; never a sound marked "licensed": false (the builder refuses it).

## Not yet built (catalog.json ideas_not_built_yet)
- The quote card, the explainer map long take with documents flying from a city, the profile strap, a teaser or end
  card, a cold open on the biggest graphic before the sting.

## Rejected (do not copy)
- The source's 16:9 layout and its bilingual Chinese / English lines: one language, the reel's.
- The LEMO plate, AI NEWS wordmark, LemoLab end card and credit card (the source says a user's film carries none).
- Burned-in subtitles and a crawl (the source's clean panel); a word-by-word caption track would break the package.
- AI-generated illustrative plates and their duotone grade: no pictures that stand in for the speaker's points; the
  face is never graded.
- The orchestral news theme, timpani, glockenspiel and the held drone: music (no bed).
- Barlow Condensed and Noto Sans SC (no Cyrillic in Barlow; replaced), mono text under 48 px (the source's 13-22 px).
- Numbers the script does not give: the threshold and proportion graphics are schematics.

## Changelog
- Ported from lemo-opuscar styles/news-package (MIT, Copyright (c) 2026 LemoLab): thesis, invariants 1-10, house.json
  (palette, type with Cyrillic substitutes, 1080x1920 layout, motion, sound roles), newspackage.py (class Bulletin:
  sting -> bug, strap with flips, rundown + recap, band wipe, stamp, corner tag, document, split-flap board, check rows,
  accent cards + bracket, threshold line, proportion bar + cells), catalog.json; proof preview on a 32 s reel.
- Public edition: IBM Plex Mono is served from its unmodified TTF (Reserved Font Name), house labels in English.
