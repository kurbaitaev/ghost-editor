# Kinetic doc as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it Kinetic doc, the slots
follow the content, catalog.json records what each reel used so the next one does not repeat it. Founded 2026-10-15
from four reference reels (R1 @lightyear.residency, R2 @usvchq, R3 @_otsan, R4 @rit2raj_das), every number measured
frame by frame. Every choice below that is not measured from the references was a call made when the style was
founded (changelog), so the user's first notes on their own reels in this style outrank anything here: fold them into
house.json and this file.

## Thesis
**The narration made visible: every word lands on screen as it is spoken, in a black-and-white archive world with one
warm red accent, while each line shows one literal picture as a physical object (a print, a window, a polaroid) and
the payoff gets the slowest, cleanest stretch.** One grammar for three kinds of video: (A) the speaker talking to
camera, (B) a voice-over over designed pages and pictures, (C) B-roll only with a voice-over.

## Invariants (never change: this is the style)
1. **The speaker's footage as shot**: no grade, no filter, no grain, no dim on the speaker's face; B&W is the
   pictures' world, never the speaker's skin. A clip where the speaker appears stays in colour (`his_face=True`).
   B-roll obeys the people rules (`people-rules.json`) and shows its line (references/broll.md section 0).
2. **The words land on the voice.** Every caption word appears in ONE frame at its spoken start, at its final place in a
   line that was laid out before it appeared; nothing fades, scales, slides or bounces in (measured in all four
   references; Gemini claimed fades in all four, wrongly). The line clears with its phrase.
3. **One idea, one heavy word.** Each phrase is one centred line of small words with at most one big word (or two short
   ones) set under them in heavy condensed caps; emphasis is size, caps, a red box or a page of its own, never a per-word
   colour sweep. Quotes and coined terms speak in the serif italic.
4. **Turn lines get their own page.** The 1-3 word turns of the story ("but…", "and then…", "it never did")
   sit alone on a grey page, a black block the size of each word standing in its place 3 frames before it.
5. **Pictures are objects.** A picture arrives as a print on its own blurred copy, a window on black that steps up in
   three sizes, or a polaroid on the grey page; full bleed only for footage that fills 9:16 or the one hook burst. Every
   picture is black and white.
6. **Literal pictures.** A picture shows the noun of its line (a pressure gauge on "pressure", a sofa on "couch"); a
   metaphor only when the line is abstract (one lit window among dark ones on "lonely").
7. **Hard cuts, on phrase starts.** Scenes change on the first word of a phrase; no dissolves, no flash frames, no
   glitches; the reel ends on a hard cut, no fade.
8. **Something new every ~1.25 s outside the payoff** (the references: 48-105 visual events a minute): a long picture
   is kept alive with what lands on it (a label, a counter, a punch-in, a polaroid, the next big word), not with more
   cuts. `KineticDoc.pace()` reports the longest gaps.
9. **One world.** Black and white pictures, grey pages with a vignette, warm paper for quotes and the end, ONE warm red
   (#D63A2F) for the payoff word, the turn word on a page, a label box, a counter, a strike. Print texture and a falloff on pages and pictures
   only.
10. **The sound is the voice.** Voice wall to wall, a flat bed ~19 dB under it that never stops (no ducking), SFX only
    under picture events (a cut into a picture or page, a punch-in, a counter's values, a polaroid, a label box) and
    never under caption words; the payoff runs without SFX.
11. **The payoff is the slowest stretch.** Concrete anchor + tension in line 1, the turn on a page, the payoff held on
    the speaker's face (A) or one picture (B, C) with nothing else landing, a callback or bookend where the script
    allows, a hard end.

## House look (fixed: house.json; one house look per style)
`house.json` holds what stays reel to reel: the palette (ink #111111, white #F4F3EF, red #D63A2F, grey page #DDDDDD ->
#A1A1A1, warm paper #E6E1D6 -> #A9A49B), the type (captions Inter 500 62 px + Oswald 700 caps up to 168 px, Playfair
italic for the serif voice, JetBrains Mono for the typewriter, Oswald caps on red for labels, Playfair italic red for
numbers), the layout (A: the caption block in the chest band, B / C: at y 1240, pictures centred on y 700), the insert
frames (print / window / full / polaroids), the motion (hard cuts, slow pushes, 2-frame punch-ins), the sound and the
budgets. The builder is `kdoc.py` (KineticDoc on scripts/lib/facereel.py); its CSS reads the palette from house.json.
A new house element only enters when the user asks for it, and then it replaces the old one in house.json.

## Slots and their generators (the components are new every reel; catalog.json lists what was used)

| slot | its job | generator: the question that fills it from a new script | example |
|---|---|---|---|
| S1 hook device | frame 0 already moving into the hero (invariant 2 + M01) | what is the concrete anchor of line 1, and how do we arrive at it: the speaker's face pushing in (A), a print flying in (B), the user's own clip as a print (C), or the one burst when line 1-2 lists things? | A: face push + the big word; B: an object print + a 3-picture burst on a listed line; C: an own night clip as a print |
| S2 turn page | the turn line on its own page | which 1-3 words turn the story, and do they need the cursor page, the typewriter (a quote), the glow card (one hard word) or warm paper (a term)? | a coined term on warm paper in the serif; "but there is a downside" on the grey page |
| S3 pictures | one literal picture per carrying line | the noun of each carrying line: own footage first, then archive (public domain), then AI stills, never crowds | an archive portrait, object stills, own clips |
| S4 number device | make a number felt | is there a number, date or amount? counter with ticks, stat box + sub-line, a red box | a number counting up in red over a picture |
| S5 emphasis on the line | the stressed word gets a move | which word does the speaker lean on: a punch-in (A: on the face, B/C: on the picture), a red label, an erase, a swap gag, a strike? | a big word erased on "disappears", a switch flipped, an object struck through |
| S6 hidden cut | one cut hidden in motion | which object in the story can cross or open the frame (a door, a car, a page turning)? optional in A | none yet (free) |
| S7 ending | the payoff held, then a hard end | a callback to the hook picture, the payoff word in red, the stat box held, a CTA typed on paper? | the payoff word in red on the face; the hook picture returns; a door onto light |

## Planning procedure
1. `python3 $S/scripts/taste.py prompt --style kinetic-doc` and `python3 $S/scripts/components.py plan --style
   kinetic-doc`: the user's rules for the style, what the last 7 reels used (avoid) and what is free.
2. The script word for word; mark the carrying lines (they get a picture or a page), the turn line (a page), the payoff
   (held clean), the big word of each phrase (BIG), the payoff word (RED), quotes and terms (SERIF; `word#n` for one
   occurrence). Leave most lines to the captions alone.
3. Pick the format: A (a talking-head recording: budgets of facereel), B (voice only, designed pictures), C (voice only,
   footage). Fill each slot from its generator with a component the last reels did not use; register each new one first:
   `components.py add --style kinetic-doc --id <id> --kind <kind> --slot S<n> --sig '<regex>' --desc ...`.
4. Pictures: the user's own footage (`own_footage.py find`, then the sheet the user confirms), public-domain archive
   (Wikimedia Commons, Library of Congress; note the source), AI stills (`broll_gen.py`, the B&W archive prompt in
   example/b_voiceover.py); every one through `broll_vision.py check` (people rules) before the build; footage through
   `insert_prep.py --no-grade` (SDR, fps, size).
5. Write the generator from example/{a_talking_head,b_voiceover,c_broll}.py, build, `hf.sh lint`, `snap.py beats`,
   `components.py check --style kinetic-doc --project $P`; look at every beat (captions clear of the face, pictures
   B&W, nothing in the IG bands).
6. `finals.py preview <P> --style "Kinetic doc"` and WAIT for the user's OK before `finals.py render`.
7. After the user's yes: `components.py record --style kinetic-doc --project $P --reel <code>`. If the user loved it,
   ask what to keep and fold it into house.json and this file.

## Prerequisites
- A needs the approved raw cut (plate + voice + words) and `face_track.py` on the plate; look-aways in
  build/cover_windows.json are hidden under a page or a picture (<= 2.5 s each).
- B needs only the voice and its words; every picture is made or found per line (no stock video of people).
- C needs footage for most lines: the user's own first. Where there is none, a still (archive or AI) in a print, never
  a stock clip of strangers. Crowds and group photos are out (people check); the style must never depend on them.

## Not yet built (v2)
- The cut-out world: objects and the speaker (matte, never tinted) cut out and set on the grey page with a soft shadow (M17).
- Callouts pinned to moving objects in the footage (dot + ring + elbow leader, tracked; M14).
- Flat maps (a top view, a route, labels pinned to places, one eased move per listed item; M20); a 3D fly-in only if a
  script needs it.

## Rejected (do not copy)
- Dropped from the references when the style was founded: the whole script typed in two bands (M04), micro one-word
  subtitles (M06, too small), the one-hue violet world (M18), a grade arc between sections (M27, the world is one),
  flash frames and glitches (M29: stay clean), the 2.34:1 letterbox (M39), a mid-roll brand card (M40).
- From notes on other styles: the flat Vox explainer v0 ("very weak": flat icons, diagram boxes, cards on the
  speaker's chest, small sans labels), split screen, outlined text over busy pictures (unreadable).
- Never in a picture: crowds, group photos, classical nudes (the Creation of Adam appears in two references: out),
  and anything the user's people rules (`people-rules.json`) exclude.

## Changelog
- 2026-10-15: founded from four reference reels (@lightyear.residency, @usvchq, @_otsan, @rit2raj_das). Choices made at
  founding: world = B&W archive + one red accent; captions = one centred line, words popping on, two sizes; at most one
  montage burst, in the hook only; no flashes or glitches; flat maps only in v1; name "Kinetic doc". v1 builder kdoc.py
  with proofs in all three formats.
- 2026-10-15 (after the three proof builds): invariant 9 reworded: red also marks the turn word on a page (the proofs
  used it on the turn word of each page). Old text: "**One world.** Black and white pictures, grey pages with a
  vignette, warm paper for quotes and the end, ONE warm red (#D63A2F) for the payoff word, a label box, a counter, a
  strike. Print texture and a falloff on pages and pictures only." house.json palette.red_note reworded the same way.
- 2026-10-30: public edition: English worked examples for all three formats.
