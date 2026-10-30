# Halftone Dossier as a system

Same method as recipes/clean-os/SYSTEM.md section 5: the invariants and the house look make it Halftone Dossier, the
slots follow the content, catalog.json records what each reel used so the next one does not repeat it. Ported from
LemoLab's MIT-licensed style "Halftone Dossier" (github.com/lemomo-ai/lemo-opuscar, styles/halftone-dossier: STYLE.md is
the spec, DEMO.md and demo/index.html the engine; CREDITS.txt) and proved on one talking-head reel. The example column
below is a case file on the 2 a.m. scroll (the usage block in dossier.py's docstring).

## Thesis
**The reel is a case file on its subject: every idea is one printed exhibit on cream paper (halftone dots in flat inks,
a heavy misregistered headline, a drawn prop or a pinned picture, a stamp for a verdict), read out between shots of the
speaker's face as shot, while a case-number HUD and a navy caption bar carry the file through both.**

## Invariants (never change: this is the style)
1. The speaker's footage as shot: no paper, dots, grain, tint or effect on the speaker's plate; no graphic on the speaker's face. On the speaker's face worlds
   only the HUD (top corners), the caption bar (under the speaker's chin), headlines BEHIND the speaker's head (between the plate and its
   matte) and one stamp below the speaker's face (over clothing or hands, no shake).
2. **The whole page is paper.** Every page has the paper multiply layer (mottling, warm noise, vignette, fold) and grain
   specks re-seeded every 2 frames; dark ("night") pages are printed too.
3. **Tone is dots, never gradients.** 1-3 halftone layers per page in different inks and screen angles (step 20-26 px),
   density fields radial / edge / linear; the second layer overprints (multiply). Numerals can be halftone-filled.
4. **One dark ink (navy) carries every outline, body text and the caption bar;** pink is the misregistration shadow,
   yellow the highlight (keywords, numerals), red only for stamps and alarms. At most five inks plus paper.
5. **Cards are the subtitles.** Each page has one black-serif headline (a spoken word or a short file label) that pops in
   glyph by glyph with squash, and the caption bar carries every spoken word (chunks <= 25 characters, keywords yellow).
6. **Bureaucratic apparatus frames the subject:** case number + chapter chip + REC/date on every frame but the hook;
   exhibits are numbered, profiled, labelled, pinned.
7. **Verdicts are physical.** A stamp slams (2.6x -> 1x in 0.09 s, bounce) with a page shake and an impact on the same
   frame; 2-3 stamps per 30 s, the last one closes the file.
8. **Everything enters with overshoot** (rise from below, scale from 0); nothing fades in. Drawn props boil (three
   jittered copies at 10 fps); text, dots, HUD and captions never boil.
9. **Joins are dot wipes or hard cuts,** never dissolves. A wipe's dots only ever cross a page: page-to-page cuts get
   the full wipe, cuts that touch the speaker's face only the page half (grow over the outgoing page / shrink off the incoming).
10. **Sound is foley of the print, no music:** stamps = impacts, flash = shutter, pages = paper flips / short whooshes,
    landings = pops; a little silence before the big stamp.

## House look (fixed: house.json)
Palette (the source's ink set: paper #F4ECDD, navy #1D2340, blue #2E55D6, pink #FF5A87, yellow #FFC628, red #E8384F,
cream #FFF4E2, night #18203F/#2A3568, orange inside numerals), type (Playfair Display 900 headlines with a pink
+0.055 em shadow; Unbounded 900 numerals; JetBrains Mono 800 for case numbers, ticks and typed labels; Inter 900 for the
caption bar, stamps, plates; all >= 48 px, Cyrillic), the caption bar (navy pill, pink 10/10 shadow, cream 54 px, yellow
keywords, centred on x 510, y 1560-1690), the HUD (navy chips at y 130 / 214, REC dot + date at the right), paper +
grain, halftone, stamp, wipe and motion numbers. `dossier.py` reads palette and fonts from house.json. A new house
element only enters when the user asks for it.

## Slots and their generators (components are new every reel; catalog.json lists what was used)

| slot | its job | generator: the question that fills it from a new script | example (the 2 a.m. scroll reel) |
|---|---|---|---|
| S1 hook | frame 0: name the file | which single word of the first line is the subject or the charge, and how does it sit: behind the speaker's head (matte), as a file label chip, as the first stamp? | «SCROLLING» behind the speaker's head, fully set on frame 0, no HUD |
| S2 the suspect | introduce the subject | what is "on file" (a phone, an app, a habit, a myth), and how is it profiled: a mugshot with height chart and plate, a passport card, a wanted poster? | the phone as a kawaii suspect with glossy eyes, height chart, plate PHONE / CASE NO. 001, flash + squint on its word |
| S3 exhibits | the evidence the speaker names | which real thing does the speaker name (a book, a study, a product) and which drawn things carry the other nouns; pinned print, typed label, giant halftone numeral? | a sleep guide's cover as a taped print + typed label (author / title), numeral 01 |
| S4 the advice page | the action the speaker asks for | what does the speaker tell the viewer to do, and what drawn scene shows it happening (a night page for "turn off")? | night page «LIGHTS OUT»: the phone + three banners on the speaker's words, stamp OFF. |
| S5 the list | a list the speaker says | how many items, which icon per item, and how are they filed: an evidence board with pins and a string, index cards, a ledger? | evidence board 01-03 (moon, dumbbell, heart) + red string |
| S6 mid verdict | a turn or reassurance | which line is a verdict, which stamp word says it naturally in the reel's language, which drawn subject carries it? | the mountain with a flag, stamp YOU CAN on its word |
| S7 payoff page | the outcome | what changes at the end, and how is it shown with dots (density = emotion: bloom for relief, edge-crowding for pressure)? | day cells under a phone that shrinks away, yellow dot bloom |
| S8 closing | close the file | how does the file close: a stamp below the speaker's face, a folder into a drawer, a redacted last line? | stamp CASE CLOSED below the speaker's face on the last line |
| S9 joins | transitions | which cuts get a full wipe, a half wipe (face side), a hard cut on a hit; which ink per wipe? | 9 half / full wipes in navy, yellow, blue, pink; one hard cut 26.84 |

## Planning procedure
1. Read the script word for word (build/words.cut.json). Name the subject of the file and its charge; mark the nouns
   the speaker names (exhibits), the action, the list, the turn and the payoff.
2. Plan the worlds: the speaker's face about 40-55 % of the reel, pages 1.5-4.8 s, a cut on a word onset; give each page one
   exhibit and one headline (a spoken word or a short natural file label in the reel's language); place 2-3 stamps.
3. Check the matte covers every behind() range (the alt matte only exists for parts of the cut).
4. Write $P/tools/build.py from the usage block in dossier.py's docstring; captions(): chunk starts so every
   word is covered and no chunk passes 25 characters; fixes={} only for a misheard name.
5. Build, `hf.sh lint` (0 errors), snapshot every beat and look: no text under 48 px or outside the safe area (120 top,
   220 bottom, 100 right), nothing on the speaker's face, stamps readable, headline glyphs not cut by the matte on frame 0.
6. `finals.py preview` and WAIT for the user's OK.

## Prerequisites
- The approved cut, a plate as shot and its matte for any behind() headline, assets/voice.wav, build/words.cut.json.
- Pictures only for real things the speaker names (the speaker's own or the product's own image); drawn props for everything else. No
  stock of people is needed.

## Sound
- Proof reel: 27 SFX in 32 s (8.4 per 10 s): paper-flip / paper-riffle on pages, whoosh-cine into page-side wipes, shutter-1
  on the flash, reaction-boing for the suspect rising, wood-hit + tick-1 for the pinned print and label,
  tech-notification-2 + pop-1 for banners, pop-3 for board cards, marker-scribble for the string, impact-1 / impact-2
  for stamps, cartoon-zip + reaction-ding-ding for the payoff. No bed (the house rule).
- Missing in the library (stand-ins used): a real rubber-stamp thud (impact-2), a typewriter key (tick-1).

## Not yet built (catalog.json ideas_not_built_yet)
- Redaction bars that lift one by one; the file folder into a drawer ending; a snap zoom into dots; the pinned-board
  pan; interjections in a hand face (no Cyrillic hand face checked yet); halftone stills of real photos (a halftone
  conversion from a picture's luminance, for objects only).

## Rejected (do not copy)
- The source's demo film, cat mascot, story, Chinese strings, end card, LemoLab sign-off, score and fonts without
  Cyrillic (Noto Serif SC / Noto Sans SC / Bagel Fat One / ZCOOL KuaiLe).
- SVG filters (#boil, #stampInk): HyperFrames 0.8.159 blacks out other clips; boil = jittered copies, stamp ink = PNG mask.
- Any paper, dot, grain or wipe over the speaker's face; a music bed; numbers the speaker did not say (the source's "99+" style badges).

## Changelog
- v0.3.0: ported from lemo-opuscar styles/halftone-dossier (MIT, LemoLab; commit f171360) and proved on one talking-head
  reel. Builder dossier.py (class Dossier); no worked example ships yet.
