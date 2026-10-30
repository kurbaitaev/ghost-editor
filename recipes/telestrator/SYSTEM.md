# Telestrator as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it Telestrator, the slots
follow the content, catalog.json records what each reel used so the next one does not repeat it. Ported from the MIT
style "Sports Telestrator" of lemo-opuscar (https://github.com/lemomo-ai/lemo-opuscar,
styles/telestrator/STYLE.md + DEMO.md + demo/index.html; its film "Freeze Frame" watched frame by frame from contact
sheets at 2 fps), adapted from 16:9 football footage to a 9:16 talking head, and proven on a 32 s reel.

## Thesis
**A TV analysis segment where the speaker's own footage is the match: it plays live, then freezes and gets drawn on - a
ring under the hand, marker arrows, a red zone for the space around the speaker, one label with the finding - always
around the face, never on it; between face shots the reel wipes to dark tactics boards where the object of the line (a
phone, a cup, a book, a list) is played, frozen, rewound and drawn on; a studio show's packaging is on every frame.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no grade, filter, punch, desaturation or vignette on the plate; a freeze is a still
   of the exact frame (accurate_rnd decode) with the speaker's own cutout of that frame on top. No ring, arrow, label,
   zone or caption ever enters the face box (measured per frozen frame; the builder raises FaceError).
2. **Watch it, then take it apart.** Every freeze follows play: the line plays live first, the freeze lands on the
   word that carries the finding. On a board the object plays first too (notifications stream in), then freezes.
3. **One freeze, one finding.** Each freeze says one thing: ring (who) -> line or zone (what) -> one label (the
   finding), 0.25-0.6 s apart; at most two groups of lines; a freeze over ~2 s gets a second action inside it.
4. **Three colour roles, never mixed.** Yellow = the speaker and what they say matters (rings, main marker lines);
   cyan = what works against them (notifications, the scary task); red = space (fill 0.36 + dashed edge); chalk =
   traced lines and neutral marks. A label's bar takes the colour of what it names.
5. **Drawn on the real picture.** Rings sit under the hand in perspective, zones and the spotlight sit BEHIND the
   speaker's cutout (they only touch the room), arrows run from the hand into the space beside the speaker; marker
   lines are drawn along their length with an arrowhead popping at the end; dashed = intended or future path, solid =
   what happened.
6. **Packaging on every frame from frame 0.** Corner bug (the show name + ● LIVE / ANALYSIS / REPLAY), source clock
   (▶ running, ❚❚ yellow on a freeze, ◀◀ counting back; true reel time and frame), matchup bar, subtitle bar with the
   speaker's words. Nothing under 48 px; nothing in the Instagram margins (120 top, 220 bottom, 100 right).
7. **Segments join with the yellow wipe only.** A slanted yellow band crosses in 0.34 s between the face and a board
   (and board to board); inside a segment hard cuts; no dissolves, no page turns.
8. **Numbers are counted, never invented.** The clock shows the reel's own time and frame; the matchup bar has no
   score; any number on a board must be true and sourced on screen.
9. **Sound is the show's foley, never music.** Shutter + low thump on a freeze, pop per ring, scribble per marker line,
   tick per label, whoosh per wipe, tape rewind, one stamp impact; the voice on top; no bed, no score, no stings.
10. **A flat ending.** The last freeze resolves, the speaker plays live to the last word; the matchup bar flips to
    their side on the payoff word. No CTA, no end card.

## House look (fixed: house.json)
`house.json` holds what stays reel to reel: the palette (yellow #FFD400, cyan #3FD8FF, red #FF3B30, chalk #F4F1E8,
board #0C1411, card rgba(8,12,14,.9)), the type (Inter Tight 900 labels, Oswald 600 / 700 oblique for spaced lines and
numerals, JetBrains Mono 500 clock, Inter Tight 600 subtitles: Cyrillic substitutes for the source's Noto Sans SC,
Barlow Condensed and IBM Plex Mono), the packaging (show name, modes, matchup names, clock rule), the layout in px
(clock, bug, subtitle bar, matchup bar, label sizes, split windows, safe area), the motion (freeze entry, draw order,
marker and ring specs, wipe, rewind, stamp), the sound and the budgets. The builder `telestrator.py` reads it. The
components that fill the slots are NEW every reel (`scripts/components.py plan --style telestrator`).

## Slots and their generators (the components are new every reel; catalog.json lists what was used)

The last column is an illustration for an English reel about coffee ("how much caffeine is too much"), not a build.

| slot | its job | generator: the question that fills it from a new script | e.g. a coffee reel |
|---|---|---|---|
| S1 opening | make frame 0 read as analysis | which opening: the stopwatch over live play with a ring already drawn, the first frame frozen and then played, a board with the object first? | stopwatch over live play + a ring under the hand holding the cup on frame 0 |
| S2 freezes on the footage | one finding per freeze, drawn in the space around the face | which words carry a finding, and what can be drawn there: a ghost object in the hand, an icon on the wall with a dashed future path, a zone in the room, a link between the hand and a label? | "third cup": a dashed second and third cup beside the hand, THE CUP / ALWAYS IN HAND |
| S3 the named source | show a book, study, person the speaker names | what do they name, and how is it read as a tactics board: rings on the page's own marks, a stamp on its verdict? (only a real asset; the name spelled right) | the health agency page with a ring on its daily limit line, stamp ONE NUMBER |
| S4 the object board | play, freeze, rewind the thing the line is about | which object is the "match" (a phone, a calendar, a feed, a desk, a mug), what streams in live, what freezes, what gets ringed and struck, what the rewind takes back? | a day's cups land on a timeline, freeze, the late ones ringed and struck, rewind to the morning cup |
| S5 the summary board | the list the speaker gives, as a board page | which list (2-4 items, their words), and which chalk icon or drawn mark per row? | WHAT TO DO: ONE CUP EARLY / WATER AFTER / NONE AFTER 2 PM with drawn icons |
| S6 the dual angle | the same moment from two plates | which line has a feeling worth seeing twice, and what is ringed in both windows? | "jittery": wide + tight, rings under the hand in both, JITTERY then CALM |
| S7 space | the room around the speaker as the thing that opens up | which word is about room, time or freedom, and where is the space drawn (always behind the cutout)? | "sleep": a red zone filling the room behind the speaker, ROOM / TO SLEEP |
| S8 ending | resolve the matchup | which word is the payoff, and which side does the matchup flip to? | the payoff word: CAFFEINE -> YOU |

## Planning procedure
1. `python3 $S/scripts/taste.py prompt --style telestrator` and `python3 $S/scripts/components.py plan --style
   telestrator`: the user's rules for the style, what the last reels used, what is free.
2. The script word for word (build/words.cut.json, edit seconds). Mark the words that carry a finding (2-4 freezes on
   the face), the object of the reel (one board where it plays and freezes), the source the speaker names, the list,
   and the payoff. Write the plan as the docstring of your generator.
3. Pick each freeze frame (on a word onset, n = round(t x 30)), look at it full-res with a 100 px grid, write down the
   face box and where the hand and the empty room are. Make the mattes for those frames only:
   `matte.py <plate> -o build/freeze/<plate>_fz-matte.webm --ranges t-0.05..t+0.1,... --pad 0.1` (mkdir build/freeze
   first). A split needs one per plate.
4. Write the generator (the public edition has no worked example yet: follow telestrator.py's docstring): the
   segments, labels (plain calm language in the reel's language, the speaker's words where possible), rings and
   sound; set house.json `packaging.matchup` to the reel's two sides; run it with `~/.venvs/media/bin/python`.
   FaceError / safe-area errors mean a drawing is in the wrong place: move it, never relax the box.
5. `hf.sh lint $P` (0 errors; the nested-section warnings are expected), snapshot every beat and look at frame 0, each
   freeze at full res, a wipe frame and the split. `components.py check --style telestrator --project $P`.
6. `finals.py preview $P --out $P/finals --style "Telestrator" --code <code> --title "..."` and WAIT for the user's OK.

## Prerequisites
- The approved cut as plates (wide + tight best, one works; a cut with its own framing switches is fine as the main
  plate), assets/voice.wav, build/words.cut.json. Mattes only for the frozen frames.
- At least one line with an object to play on a board (a phone, an app, a list, a book); the style does not need
  stock footage. A real picture only when the speaker names it (a cover), never stock people.
- Fonts and SFX from the skill (templates/fonts, library/sfx); the builder copies them.

## Sound
- The proof reel: 49 SFX in 32 s, all on entries (freezes, rings, lines, labels, wipes, the rewind, the stamp, three
  notification blips, the flip); none in plain live play. Library: shutter-1, impact-2 (low, as the freeze thump),
  impact-1 (stamp), pop-1 / pop-3, marker-scribble, tick-1, whoosh-1/2/3, reaction-tape-rewind, tech-notification-2,
  tech-ui-confirm. Levels in house.json.
- The source's score (drums stopping on each freeze, brass stabs) is NOT ported: voice + SFX only.

## Not yet built (catalog.json ideas_not_built_yet)
- A rewind or slow-motion pass on the speaker's own footage (needs a reversed / per-frame matte to keep bars off the
  face).
- A ring tracked through live play (keyframes) when the hand moves; the perspective flatten into a top-down board; a
  data card with counted numbers; the show sting at frame 0.

## Rejected (do not copy)
- The source's freeze punch (1.035 -> 1), 42 % desaturation, cool cast, heavier vignette and footage grade + grain:
  effects on the face plate.
- The music score and stings; the commentary transcript box (no second-language source here); Chinese + English
  double subtitles (the speaker's words only, in the reel's language).
- The source's show name 定格 FREEZE FRAME, its channel bug styling, broadcaster names and LemoLab credit card; its
  demo footage, photos and film (CC BY 4.0 / third party); handwriting fonts.
- Never: a drawing on the face, numbers the speaker did not say or that are not sourced, a pen outro.

## Changelog
- Ported from lemo-opuscar styles/telestrator (MIT, (c) 2026 LemoLab; CREDITS.txt): house.json, telestrator.py (class
  Show + Scene), catalog.json (11 house elements + 11 components); proof preview on a 32 s reel.
- Public edition: packaging and clock in English (BREAKDOWN, LIVE / ANALYSIS / REPLAY, "s · F" frame counter).
