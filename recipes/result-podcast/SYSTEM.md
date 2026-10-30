# RESULT as a system

Same method as recipes/clean-os/SYSTEM.md section 5: invariants and the house look make it RESULT, slots follow the content, catalog.json
records what each reel used.

## Thesis
**The story told across a table of real, tactile objects.** Warm film, paper, handwriting: the idea becomes an object you
could hold (a note, a ticket, a receipt, a clipping), the voice keeps going over it.

## Invariants
1. The speaker's footage as shot: no warm grade or sepia on the face unless the user asks for it (`look.asked`).
   Grain + per-frame-seeded dust canvas, vignette. The warmth lives in the paper, kraft and polaroid surfaces.
2. Captions: one or two words, Inter Tight; two-tier emphasis (small line + one big bold word); key words in Caveat.
3. Film-burn light leaks at section turns (screen-blended radial gradients sweeping in).
4. Artifacts sit on a surface (navy card, kraft paper, cork, wood) and move like paper: slide in with rotation, settle,
   get stamped/written on. Handwriting is drawn in with a clip-path wipe; marker circles with stroke-dashoffset.
5. At most three punch-ins per reel; no zoom on every cut.

## House look (fixed)
One house look per style, small variation per reel: `house.json` in this folder holds it, and the build reads it instead
of inventing a new look each reel. The house look is only the type, the captions, the accents, the insert framing
and the speaker's face as shot. The COMPONENTS that fill the slots are NEW every reel, so reels don't look alike:
phone-UI scenes, paper props, polaroid / card / collage treatments, transitions, hook devices and outro
devices. `scripts/components.py plan --style result-podcast` lists what the last 7 reels used (avoid) and what is free;
`broll_qa.py --style result-podcast` warns on a repeat (check `components`). Grade: none on the speaker's face: the plate
keeps its as-shot colour and every insert is conformed to it
(`insert_prep.py --ref <plate>`); the house look is the type, graphics and devices above. B-roll obeys the people rules
(`people-rules.json`) and shows its line (references/broll.md section 0). A new look element (a new transition, a new
device) only enters the house when the user asks for it, and then it replaces the old one in house.json.
House: the speaker's face as shot (a warm film look, `look.film`, only when the user asks for it), the two-tier
Inter Tight captions with Caveat key words, navy and kraft surfaces, polaroids and paper as the insert frame, grain and
dust. Not house (new every reel, see catalog.json): the paper props and artifacts, the polaroid / collage
treatments, the transitions (the film-burn leaks were the first set), the hook and the outro devices.

## Face RESULT (the talking-head mode; faceresult.py)
- The speaker's face stays on screen (>= 65 %); props sit beside, above or below it in zones measured from face.json,
  never on it (the build checks every prop, caption and punch-in against the face core); full-screen cards <= 2.5 s.
- Captions: the two-tier caption on the navy card (small line 62 px, big word 132 px, Caveat key word 150 px).
- No film-burn leak over the face (an orange sweep across the face is a colour change): transitions are components.
- The plate is held for the tail (0.45 s) and keyframed every second; nothing ever filters it.

## Slots (content: what the story needs)
- **Artifacts** (one per story beat, from the story's world; NEW every reel: not in the last 7 RESULT reels, see
  `components.py plan --style result-podcast`): polaroid, paper stack, notebook to-do,
  sticky notes on cork, boarding pass + stamp, thermal receipt, envelopes + postmarks, newspaper clipping, tear-off calendar,
  business card, ticket stub, map, Post-it on a laptop, index cards, cassette label, receipt from a shop, etc.
- **Surface palette**: the house pair navy + kraft (cork / wood / linen only when the story is set there).
- **Comic props** (only for funny beats): REC frame, declined call, cursor dialog, chat bubble, emoji sticker.
- **Music**: a warm bed (lo-fi, piano); rotate.

## Generator
For each sentence: what object would a person in that story physically hold at that moment? Make the spoken claim
appear on that object as it is said (written, printed, stamped, circled). Prefer objects from the speaker's own world.

## Planning procedure
1. `components.py plan --style result-podcast`: what the last 7 reels used (avoid) and what is free.
2. Per sentence: the object from the story's world (Generator above); pick props, polaroid / collage treatments,
   transitions, the hook and the outro device that the last 7 reels did not use; register new ones with
   `components.py add` (with a sig).
3. Build, `components.py check --style result-podcast --project $P` (broll_qa.py warns too), render; after the user's yes
   `components.py record --style result-podcast --project $P --reel <id>`.
