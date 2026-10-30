# Clean OS as a system (not a template)

The README describes what the first Clean OS reel looked like. This file is the logic behind it. The default is
**one fixed house look per style, small variation per reel** (`house.json`, the "House look" section):
every reel looks like Clean OS, and only the content follows the script. Pasting the last reel's scenes where the script
doesn't call for them is still wrong (it reads as "the same edit"); reusing the house's type, transitions, device,
palette and grade is the point.

## 1. The thesis (why the style works)

**The viewer's phone is the stage.** Every abstract idea in the monologue is translated into a *state change on a device
the viewer already owns*. Two worlds alternate:

| world | carries | look |
|---|---|---|
| the footage | the person, warmth, doubt, honesty | the recording's own mood (dusk stays dusk), wide/tight from one 4K camera |
| the OS | the idea made concrete, the "aha" | white system surfaces or frosted glass over blurred footage, system colours, Inter |

The cut between the two worlds is the rhythm. The *state change landing on the spoken word* is the payoff. Everything
else is decoration.

## 2. Invariants (never change: this is the brand)

1. **Type:** Inter (Latin + Cyrillic), lowercase, tight tracking (−0.03…−0.06 em); italic is the only emphasis. Word cards
   of 1–3 words resolve from blur on the chest (y≈1250).
2. **Two worlds** as above; OS time is 20–35 % of the runtime; bare cuts between takes stay hard.
3. **Literalism:** an OS moment shows exactly what is said, as a real OS primitive, and its state change lands on the
   key word (± 0.05 s). Décor text inside a UI (sender names, file names) may add colour, never a new claim.
4. **Two shot sizes** from one 4K camera; a soft whoosh only on tight → wide when the cut is visible.
5. **Sound:** one small, native-sounding UI sound per graphic entrance; nothing on bare cuts; a quiet ambient bed
   (≈ −12 dB under the voice); UI sounds ≈ −14 dB, clicks no louder than −14 dB vs the voice p95 peak.
6. **The designer's hand:** at least one meta moment where the edit shows its own tool (a selection, a cursor, a pen).
7. **Footage hygiene:** no REAL look-away on screen, and no pause inside a sentence. Run `scripts/facescan.py`
   (MediaPipe head angles + gaze/blink blendshapes, every frame, IMAGE mode) and `scripts/plan_cut.py` (drops every pause
   > 0.24 s, lists every off-lens window in edit time with a verdict). **Small glances stay on screen**: a blink, a glance
   or a nod up to 0.5 s with the head within 12 deg reads as a person talking (in one audit, 29 of 31 flagged windows were
   0.03-0.4 s blips; hiding all 31 put the speaker on screen 33 % of the reel). Only a real look-away (eyes off or closed
   > 0.5 s, head > 12 deg) is covered, cheapest first: trim it (a split edit at a line end), a tight-crop punch, hold the
   scene already on screen, a framed insert, full-screen stock last (references/broll.md 1). There is no assert-covered
   check any more. plan_cut never removes a gap inside a word (an unvoiced 'st' inside a word reads as silence)
   and keeps a breath at sentence joins; stray words go in cut.json "drop". Head angles alone miss eye turns: gaze is the
   main offender (in one reel, 74 of 123 bad frames); confirm flags in IMAGE mode and in 30 fps strips.

## House look (fixed)
One house look per style, small variation per reel: `house.json` in this folder holds it, and the build reads it instead
of inventing a new look each reel. The house look is only the type, the captions, the accents, the insert framing
and the speaker's face as shot. The COMPONENTS that fill the slots are NEW every reel, so reels don't look alike:
phone-UI scenes, paper props, polaroid / card / collage treatments, transitions, hook devices and outro
devices. `scripts/components.py plan --style clean-os` lists what the last 7 reels used (avoid) and what is free;
`broll_qa.py --style clean-os` warns on a repeat (check `components`). Grade: none on the speaker's face: the plate keeps
its as-shot colour and every insert is conformed to it
(`insert_prep.py --ref <plate>`); the house look is the type, graphics and devices above. B-roll obeys the people rules
(`people-rules.json`) and shows its line (references/broll.md section 0). A new look element (a new transition, a new
device) only enters the house when the user asks for it, and then it replaces the old one in house.json.
House: Inter lowercase cards (base blur-resolve, QuickType on choice words); the red Figma selection box is the
emphasis device; the Markup pen writes the signature word; the accent is one of orange #FF9F0A / blue #0A84FF / green
#30D158 by topic; inserts sit in a PiP window, a Photos card or the viewfinder (stock video never full screen; stock
images welcome in a card). The speaker's face as shot. Not house (new every reel, recorded in catalog.json): the scene
transition pair and the OS scenes.

## 3. Slots (content: what the script needs; the components are new every reel) and their generators

Each slot has a generator: a procedure that produces a new element from the script, not a list to pick from.
The catalog (`catalog.json`) records every element ever made and the reels that used it.

### S1. OS scenes: the metaphor generator
For each sentence that carries an image or a turn:
1. **Nucleus:** the one noun/verb the viewer should *see* ("emails", "switch", "finished").
2. **Where does it live on a phone?** Map the nucleus to a primitive family:

| family | primitives (grow this list every reel) |
|---|---|
| time | clock, timer, stopwatch, alarm, calendar day, date picker, Screen Time report |
| communication | mail inbox, message thread, call banner, voicemail, read receipt, typing dots |
| attention | notification stack, badge counts, Focus/DND, app switcher, Dynamic Island, Control Center |
| progress | progress/download bar, checklist, Activity rings, battery, storage bar, install |
| memory | Photos memory, album, camera viewfinder, notes, files/drafts, recents |
| decision | picker wheel, toggle, two-button alert, segmented control, action sheet |
| self | search, dictation/Siri, Health, Settings, profile |
| failure | error alert, low battery, stalled loading, "no results", sync failed, unsaved draft |

3. **Choose the primitive whose state change IS the sentence's turn.** "nothing finished" = a pile of drafts that never
   reached "saved"; "focus on one" = four cards flicked away, one stays. If the change can't land on a word, pick another.
4. **New every reel:** pick a primitive whose state change IS the line and that the last 7 Clean OS reels did not use
   (`components.py plan`; never used is best, `ideas_not_built_yet` in catalog.json is a start). Register it first:
   `components.py add --style clean-os --id ... --kind scene --slot S1 --sig '<a class or id it emits>' --desc ...`.
5. **Arc:** order the scenes as a mini story: pressure (inbox, badges) → doubt (search, dictation) → turn (a choice)
   → resolution (completion). A reel should end on its resolution primitive or on the face.

### S2. Scene transition family (one per reel, in + out)
Derive from an OS **gesture**, so the transition itself says "phone": app opens from its icon, swipe up to home, sheet
slides up, notification drops, Dynamic Island expands, app-switcher card flick, Control Center pull-down, unlock.
One pair per reel, NOT used in the last 7 reels (`components.py plan`). Everything else stays a
hard cut.
**Never over the face:** an app-open starts from an icon BELOW the chin (the face track gives the chin), opens fast
(power2.in, <= 0.25 s) and shows its content from its first frame. Opening every scene from an icon on the chin with a
slow power3.inOut puts an empty white or frosted box on the speaker's mouth for a few frames each time (one read as a
censored face; broll_qa.py found three more in the same reel).

### S3. Emphasis device (the designer's hand)
A tool that *selects* or *edits* the spoken words on the footage, with two modes: **focus** (select only) and
**reject** (select, then delete or strike). Families: design tool (Figma box), OS text selection (handles + callout
menu), markup highlighter, Find-in-page highlight, spell-check underline with suggestion, track changes, Keynote build.
House device: the red Figma selection box (focus / reject), used 3–5 times.

### S4. Data moment
One numeric device placed beside the head on the footage, tied to the sentence about state or energy: ring %, battery,
Screen Time bars, Activity rings, storage bar, timer, step counter. Count it down or up across the sentence.

### S5. Signature word
One hand-made word per reel, on the emotional noun. House tool: the Markup pen with the nib and toolbar (Marck Script).

### S6. Accent colour
One colour per reel from the house palette, by topic: orange #FF9F0A (craft, warmth), blue #0A84FF (digital),
green #30D158 (health, done). It colours the scenes' active state, never the word cards.

### S7. Card variant
House variant: the QuickType suggestion tapped up into the card, 2–3 times on the choice words; all other cards stay
the base blur-resolve.

### S8. Story layer (immersion): what makes it more than illustrated captions
1. **Acts.** Map the script to 3–4 acts (the trap → the turn → the method → the resolution). Each act has a world:
   a grade (cool vs warm), a B-roll family and a music state.
2. **The turn is an event.** On the sentence that changes the frame of the story, cut the music into its build, hit
   an impact (a foley sound from the story's world, e.g. a wood hit), switch the grade, open the new world on B-roll.
3. **B-roll tells a parallel story,** not decoration: the viewer should be able to follow the arc with the sound off.
   - **One character:** the parallel story is ONE person, so take clips from one stock creator's series and check the
     frames. One reel's "carpenter" was three different men in five seconds.
   - **Sources:** the speaker's own footage first, then AI stills in one frame language, then stock that matches the
     reel's light and place.
   - **Grade:** every insert goes through `insert_prep.py --ref <plate>` (grade, SDR, fps). CSS filters are not a grade.
   - **Budget:** at most 3 inserts per minute and <= 25 % full-screen B-roll. The rest are framed on the phone stage (a
     PiP window, a Photos card, a viewfinder) so the speaker's face stays on screen. Full screen is for the turn.
   - **Not for covers:** B-roll is NOT a cover tool here. Real look-aways are rare; small glances stay.
   - 4K only (Pexels vertical/landscape ≥ 2160 short side; Mixkit only where 2160p is offered).
4. **Recurring motif + callback:** an image from act 1 returns in act 4 in the cold grade ("the whole day was busy"), and
   the reel ends on the resolution image (e.g. the finished table) holding ~1.4 s after the last word.
5. **Music arc:** pick a track with a measurable build (2 s RMS curve), play its quiet part under act 1 and jump into
   the build at the turn. **Foley** from the story's world under the warm act (saw, sanding, workshop room tone).
6. **Pace:** no pause inside sentences, 0.1–0.2 s between them; median shot 1.5–2.5 s; captions continuous (1–3 words).
7. **Frame 1 is the speaker.** Never open on B-roll or type: the first frame is the face (it is the cover and the
   promise). If the opening frames are slightly dirty, keep them and record the exception (ACCEPT in the build).
8. **Cover with what is already there first.** A real look-away at a sentence start right after a scene: hold the scene
   until the eyes are back (auto-extend), before adding a new cutaway. Small glances need nothing. Don't drop random
   people B-roll into the method act.
9. **Layering:** one text element at a time. Captions are blocked word by word under selections, scenes and type;
   selections end before the next scene or type; full-screen type sits above captions and selections.

## 4. The planning procedure (do this before writing reel.py)

A reel is `$P/reel.py` on the builder: `cleanos.py` (the house, captions, scenes / chest / top / figma / pen / hero, the
budgets that fail the build) and `kit.py` (counters, toggles, rows, bars, rings, taps, typing, stacks, alerts). Read
`python3 cleanos.py --api`, not the source and not old generators; `cleanos.py --new $P --from <cut>` makes the project.
reel.py holds only this reel's word-keyed calls and its NEW components' markup (aim <= 150 lines). A part that two reels
needed goes into kit.py (a part is not a component: the catalog tracks the scene it sits in).

1. Script table: sentence → nucleus → family → primitive → state change → landing word.
2. `components.py plan --style clean-os`; fill S1, S2 and S4 with components the last 7 reels did not use (register
   new ones with `components.py add`, with a sig); S3, S5, S6, S7 come from house.json.
3. Head-pose scan; `plan_cut.py` / `cover_windows.py` label each off-lens window keep or cover; plan a fix only for
   the cover ones (trim, punch, hold the scene, framed insert).
4. Budget: OS time 20–35 %; one scene every 6–12 s; never two scenes back to back without ≥ 1.5 s of face between; the
   speaker's face on screen >= 65 % of the reel; full-screen scenes median <= 2.5 s, each with a state change every
   1-1.5 s; `broll_qa.py` checks all of it on the render; the builder fails the build on the face / scene / gap budgets.
5. Before the render `components.py check --style clean-os --project $P` (broll_qa.py warns too); after the user's yes
   `components.py record --style clean-os --project $P --reel <id>` and one line in a changelog at the end of this
   file: what was new, what worked.

## 5. How to break down ANY new reference style (the same method)

1. Verbatim script, then a second-by-second element log (reference_study.py).
2. Group the elements by **job** (carry the person, make the idea concrete, emphasise, measure, sign, transition).
3. For each job, write the **rule** that produced the element ("a state change on a phone that lands on the word"),
   not the element ("a search bar").
4. Split rules into invariants (what makes it this style) and slots (what can vary), then write a generator per slot
   and seed a catalog with the reference's elements.
5. Test the system: plan a second reel for a different script and check it reads as the same style with no element
   copied. If it can only be made by copying, the rules are too specific.
