# Hologram HUD as a system

This uses the same method as recipes/clean-os/SYSTEM.md section 5. The invariants and the house look make a reel
Hologram HUD; the slots follow the content; catalog.json records what each reel used, so the next reel does not repeat
it. Ported from Lemo-Opuscar styles/hologram-hud (MIT, LemoLab; CREDITS.txt) and proved on one talking-head reel. The
example column below is a reel about the phone as the first thing you touch every morning (the usage block in
hologramhud.py's docstring).

## Thesis
**The thing the speaker talks about is scanned into a glowing wireframe, and the HUD reads it like data: target boxes lock onto
its parts on the speaker's words, values roll in from garbage glyphs and turn amber the frame they are true, finished values dock
in a rail that stays. Between the scans the reel cuts to the speaker's face as shot, framed by the same interface.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no grade, no filter, nothing on the speaker's face. The face worlds carry only the edge
   chrome and the HUD subtitle on the chest. The HUD never draws a person.
2. **The subject is always a line wireframe made of light** on a round projector pad on a near-black stage, built in
   code for the spoken noun. It is never a rendered object, a stock picture or a screenshot. At most one real printed object may
   keep its own colour on the wireframe's face (the single-colour exception).
3. **Three depth layers on every HUD frame:** the dot grid behind (slow parallax), the object with its pad, and the HUD
   in front (corner brackets, rulers that parallax faster, subject // mode, a live status).
4. **One cold hue and one warm accent.** The hue carries lines, HUD and fills. The accent is spent only on a value at the
   frame it becomes true, a set toggle, or a marker label once it is set. White is heat: the scan front, hot pieces, the
   lock flash.
5. **Target lock = "look here now".** The box starts 1.9x and rotated 45 deg, snaps in 0.22 s on its word, flashes
   white for 3 frames, and tags the part. The camera follows the box (cubic in-out, starting before the next lock).
6. **Values are computed on screen.** Labels and values roll right to left from garbage glyphs of their own script.
   Every value is true: a state the speaker names (OFF / ON), a name (the book), a real count or progress (BASICS 3/4, the
   scan %). Never an invented number.
7. **Chip accumulation = reading time.** A finished value docks as a chip in the rail and stays in every later HUD
   scene, so the reel's list builds up on screen.
8. **No cuts inside a HUD scene.** The object grows under the scan plane, erases top-down, explodes along its assembly
   axis, or the turntable whips. Cuts happen only between the speaker's face and a HUD scene, on word onsets, and every HUD scene
   opens with the 3-frame power-on. There is one 3-frame glitch per reel, on the biggest change.
9. **Text never sits on the wireframe bare:** every block has its dark plate (cards, chips, markers, tags, subtitles).
   Every word is at least 48 px and stays inside the safe area (status at y 196, the subtitle plate bottom at y 1690,
   100 px clear on the right).
10. **Sound marks data, not words:** the voice plus library UI sounds where a scene opens, a lock lands, a value turns
    true, a chip docks or a notification pings. No music bed or score, and nothing on face worlds.

## House look (fixed: house.json)
`house.json` holds what stays the same from reel to reel:
- the palette (hue 188 cyan, accent 38 amber, the stage, plates);
- the type: Exo 2 for every word (Light values, SemiBold labels, Medium subtitles at 70 px, cap height 48 px), JetBrains Mono for subject, status
  and indexes. These are the Latin + Cyrillic substitutes for Rajdhani and Share Tech Mono;
- the layout (status band, rail, card zone, subtitle plate, chrome);
- the motion numbers and the sound roles.
The engine (engine/holohud.js) holds the renderers: stage, pad, wireframe with fog and glow, scan plane, target box,
leader, spec card, toggle chip, marker, beam, subtitle, glitch, power-on. The builder `hologramhud.py` reads the hue,
accent and fps from house.json. The objects, the lock order, the camera route and the opening and ending devices are NEW
every reel (catalog.json).

## Slots and their generators (components are new every reel; catalog.json lists what was used)

| slot | its job | generator: the question that fills it | example (the morning phone reel) |
|---|---|---|---|
| S1 frame 0 | the speaker's face with the first line | which plate, and is the first line short enough for two subtitle lines? | tight plate, «Your phone is the first thing ...» |
| S2 opening scan | name the subject of the reel as scanned data | what object is the reel about, what are its parts, and how does it arrive: scan-in, a part first (the rest scans out of it), plan view? | the phone scans in, orbit craning down, PHONE rolls in |
| S3 source | show where the advice comes from | does the speaker name a source (a book, a study, a person)? scan it in and lock it, with the name rolling in; keep its real cover only if the speaker shows or names it | the book, its real cover, AUTHOR / BOOK TITLE |
| S4 teardown | the one action, on the object's own part | which part of the object does the action touch, how does it come apart (explode axis), what state does it end in? | notifications pulled out of the screen, OFF, markers ALARM / MAIL / NEWS, each cooled dark |
| S5 list | a list the speaker says (2-5 items) | what object stands for each item (a line icon the viewer would recognise), and how do they come on: a turntable whip, a top-down knolling, a loupe? | four icons on a turntable pad, a lock and a toggle each: SLEEP / MOVE / PEOPLE / CHALLENGE |
| S6 ending | the payoff as a state change | which object leaves and which arrives: power-down, scan-erase, one value at eye level, the solid hologram once? | the phone locked, glitched, scan-erased; the basics ignite solid with the beam, FREE TIME / YOURS |
| S7 rail | the reel's takeaway list | which values dock, in which order, on or off? | ALERTS off, then four on |

## Planning procedure
1. Write the script word for word from build/words.cut.json (edit seconds). In build/plan.txt mark which lines stay on
   the speaker's face (personal lines, the turn) and which lines name a thing (an object, a source, a list, a state). The speaker's face
   should be on screen 35-45 % of the reel, in 2-3 s worlds.
2. For each HUD line: the object and its parts, what locks on which word, which value rolls (true only), what docks.
   Build any new model in engine/holohud.js (rr / piece / cylX / place). Every piece must touch its neighbour, and the
   part that carries the value gets a hot piece that slides along its own axis.
3. Write $P/tools/build.py from the usage block in hologramhud.py's docstring. Keep the subtitles the speaker's exact words, one
   chunk per spoken line, at most two lines at 70 px (cap height 48 px) (split longer lines on a pause). Fix only misheard names.
4. Run it, `hf.sh lint $P` (0 errors), then snapshot every beat (build/beats.json keys) and look at frame 0, every lock,
   every roll and the ending at 1080x1920. Check that no text leaves the safe area and that the object is at least 1/3
   of the frame height at its key moment.
5. `finals.py preview $P --out $P/finals --style "Hologram HUD" --code <code> --title "..."` through the render lock,
   then WAIT for the user's OK before `finals.py render`.

## Prerequisites
- The approved cut, one or more plates of the same timeline, assets/voice.wav, build/words.cut.json.
- Lines that name things. A reel of pure opinion with no objects gives this style nothing to scan; use another style.
- No matte, B-roll or stock is needed. Pictures are drawn wireframes; one real printed object at most.

## Sound
- The source scores the whole film (synth arpeggios, a drop at ignition) and synthesises its foley. The house rule is no beds,
  so the score is dropped. The foley roles are mapped to library sounds: tech-digital-whoosh / whoosh-2 into a HUD scene
  (3 frames before the cut), paper-flip when a printed object scans in, click-1 / pop-3 on a lock, tech-ui-confirm when
  a value turns amber, pop-2 on a chip dock, tech-notification-2 on a notification marker, glitch-hit + whoosh-reverse
  on the glitch and scan-erase, deep-boom at the solid ignition.
- Proof reel: 26 SFX in 32 s, all inside HUD scenes (about 13 per 10 s of HUD time), none on the speaker's face worlds.
- Missing from the library: a soft synth "lock" thump + two-tone beep, a frame-rate roll tick, a projector hum. The
  stand-ins are click-1 / pop-3, tick-1 and silence.

## Not yet built (catalog.json ideas_not_built_yet)
- The loupe (frame in frame), real motion blur in whips, the orbit around a part's own axis (piece.axis spin was dropped
  in the port), the plan-view opening, the knolling ending, the upgrade beat (old value dim, new value amber), a loop
  screen, modelFromPath for a logo the user gives.

## Rejected (do not copy)
- The source's 18-22 px micro telemetry (coordinates, zoom, HOLO.0252): under the 48 px floor. Ticks and rulers carry
  the texture instead.
- Its music-first sound (score, drop, ducking): the no-bed rule.
- Its end card and LemoLab sign-off, the e-bike and the drone, Rajdhani and Share Tech Mono (no Cyrillic).
- Any HUD element over the speaker's face, any filter on the speaker's plate, fictional product or channel names, invented specs.

## Changelog
- v0.3.0: ported from Lemo-Opuscar styles/hologram-hud (MIT). Engine adapted to 1080x1920 and Cyrillic. Builder
  hologramhud.py (class Hud); proved on one talking-head reel; no worked example ships yet.
