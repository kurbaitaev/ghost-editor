# Whiteboard as a system

Same method as recipes/clean-os/SYSTEM.md section 5: invariants and the house look make it the Whiteboard, slots follow
the content, catalog.json records what each reel drew.

## Thesis
**The thought is drawn while it is said.** The speaker stays on screen, as shot; a marker board above turns each sentence
into one simple drawing, stroke by stroke, with the marker visibly doing it.

## Invariants
1. The speaker's footage as shot: no grade, no filter on the face. Frame 1 is the face full screen with the hook words in
   a pill; the board drops over the top half on the first words and the whole face sits under the seam.
2. Every mark draws on (rough seeded strokes, stroke-dashoffset), never pops; a visible marker follows each stroke and
   each handwritten word and lifts off the board between ideas; Caveat handwriting; 2-4 marker colours on white.
3. One page per thought; an eraser wipe between pages; nothing under the seam captions (y > 900 fails the build).
4. Seam captions: white pills, the spoken word swept in yellow. One text layer: the board writes key words, the pill
   carries the sentence.
5. The board goes full screen only to hide a look-away, <= 2.5 s. No B-roll. A quiet bed; scribbles are texture.

## House look (fixed)
`house.json` in this folder. The house is the layout, the type, the marker colours, the captions and the speaker's face
as shot. The DRAWINGS are new every reel, so reels don't look alike: `scripts/components.py plan --style whiteboard`
lists what the last reels drew (avoid) and what is free; every `draw()` names its shape (`data-shape` in index.html, the
catalog sig); basic vocabulary (stick figures, arrows, ticks, crosses, underlines) may stay.

## Slots (content: what the story needs)
- **Pages**: one per thought (5-8 in 30-45 s); where a page starts and is erased.
- **The metaphor of each page**: the object a person would sketch to explain that sentence (a chain for a relationship, a
  key for advice, a steering wheel for control, a mountain for a scary task); not in the last 7 reels.
- **The words the board writes**: the key noun or the claim, in the speaker's words, on its spoken word.
- **The hook page and the outro page**: the first idea after the drop; a callback or a resolution at the end.
- **The bed**: quiet, rotate.

## Generator
For each sentence: what would you draw on a whiteboard in 2 seconds to explain this line to a friend? One object, its
label, maybe one arrow or tick. Draw it on the words that name it; write the label as it is said.

## Planning procedure
1. `components.py plan --style whiteboard`: what the last reels drew (avoid) and what is free (`ideas_not_built_yet` too).
2. Pages from the transcript, each keyed to words (`B.t("word")`); new drawings get a helper in board.py when they are
   reusable, and a catalog entry (`components.py add --style whiteboard --kind prop --sig 'data-shape="<name>"'`).
3. Build, `components.py check --style whiteboard --project $P` (the build prints it), preview; after the user's yes
   `components.py record --style whiteboard --project $P --reel <id>`.
