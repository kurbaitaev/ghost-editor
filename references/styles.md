# Styles

A style is a preset in `styles/<name>.json`: brand (fonts, accent), caption
style, sound density, music mood, film look and scene defaults. A reel names
one with `"style": "<name>"`, and anything in reel.json overrides the preset.
The preset sets the LOOK. The beats (what happens when) are still planned per
recording, using the grammar below. Every style was rendered from the same
recording (`examples/gallery/`) to check that they read as different.

| style | looks like | best for | beats that fit | sound | music |
|---|---|---|---|---|---|
| `clean` | bold mixed-case captions, active word in the accent, snap zooms, no scenes | business talking heads, advice, Hormozi-restrained | snaps at sentence starts, 1-2 pushes, at most 1-2 `big` cards | restrained | none (add one on the platform) |
| `editorial` | lowercase blur-in captions, light previous line, tilted pill tags, highlight wipes, full-screen scenes over the voice | data, insight, "new research shows" | `card` with cursor, `stats`, `fly3d`, `image`, `sentence` covering 30-50% of the runtime | standard | tense minimal electronic |
| `meme` | outline captions, emoji/memes beside the head, chips and big cards | entertainment, hot takes, reactions | `emoji`, `meme` (own library), `big`, `chips`, `strike`; reaction sounds on punchlines | rich | quirky |
| `cinematic` | film grade, grain, vignette, B&W B-roll stills, keywords in a glowing serif italic, dark sentence scenes | stories, founder journeys, emotional turns | `image` B-roll (AI stills via `broll_gen.py`), dark `sentence` heroes, 1 push per section | restrained (boom, riser) | ambient cinematic |
| `launch` | dark UI windows with typed prompts, phone frames with chats, glitch transitions, violet accent | product and AI launches, feature demos | `ui` (the pain or the prompt), `device` (the product answering), `sentence` hero for the name, cursor CTA card | standard | upbeat electronic |
| `kinetic` | full-screen word-by-word type on a solid colour, a camera gliding between words, speaker in a round picture-in-picture | hooks, quotes, manifestos, lists | `kinetic` scenes (`*keyword*`, `_filler_`), `pip: true`, 1-2 per reel | standard | percussive |
| `pop` | giant display words BEHIND the speaker (person cut-out), uppercase captions with hot colour boxes | personal brand, lifestyle, bold claims | `behind` beats on the 2-4 biggest words, colour-block CTA | standard | upbeat pop |

## Picking a style

- The speaker's energy decides more than the topic. A calm explainer in `pop` feels wrong; a hype launch in `clean` feels flat.
- Ask for a reference edit when the user has one: `reference_study.py` and the closest style, then override.
- Don't mix two styles' signature moves in one reel (e.g. `kinetic` scenes inside `cinematic`). Keep the recognisable beats consistent.

## Keeping every reel fresh (same style, not the same reel)

- Rotate the accent and the music bed between reels (`brand.accent`, `music.id`); keep fonts and caption style (the brand).
- Change the scene order and kinds: a `stats` reel, then a `fly3d` reel.
- One new move per reel (a new scene kind, a transition), everything else proven.

## Saving a new style (from a reference study or a reel the user loved)

A recipe ships with a SYSTEM.md (thesis, invariants, slots with generators, planning procedure) and a catalog.json, like
`recipes/clean-os/`. The element list alone produces copies.

`python3 $S/scripts/save_style.py <project> <new-name> --best-for "..." [--about "one line"] [--music-auto] [--verify-on <another project>]`
does it: it copies the reel's own preset, fills brand, caption look, sfxProfile, music, look and scene defaults from what
rendered (never the per-recording fixes, tags or highlight words), writes `styles/<new-name>.json`, adds the row to the table
above, saves `examples/gallery/<new-name>.reel.json`, and checks the round trip (example + new preset build the identical
composition). `--verify-on` builds another project in the new style and snapshots it next to its own look: confirm it reads
as its own look before calling the style done. It refuses a reel without a render or with a failed render report, and the
seven built-in names.

By hand (from a reference study): copy the closest preset, set `_about`, `brand`, `captions`, `sfxProfile`, `music` (an id or
`auto` plus a mood tag in `library/music/manifest.json` `styles`), `look` and `scenes`, add the table row and the example,
and render one existing example in the new style.

## Caption and overlay safety (all styles)

`scripts/face_track.py` must run before the build. The placer then:
- puts every caption block **below the chin** near the ideal reading height, else **above the head**, else shrinks it (down to 70%) to fit above the head, and only as a last resort puts it **as low as the platform allows** on a dark backing (never over the eyes or the mouth)
- keeps blocks in the same zone while it fits (no top/bottom jumping)
- keeps inside the platform's safe area (`"platform": "instagram" | "tiktok" | "shorts" | "all"`) and clear of the right-hand button column
- places cards (`big`, `chips`, `strike`, `quote`, `list`) beside the face too; a `big` with no room is promoted to a full-screen scene
- puts emoji/logo/meme on the side of the head with room, or skips them
- steps captions around cards on screen at the same time

`build/caption_layout.json` records every block's zone. `qa.py` prints the counts and fails on anything outside the safe area.

## Recipes (beyond the presets)

| recipe | looks like | best for | where |
|---|---|---|---|
| **Clean OS** | Apple-clean lowercase Inter word cards resolving from blur, wide/tight cuts from one 4K camera, white iOS-style scenes (date picker, lock screen, search, Photos), a red Figma selection box with a cursor, perspective text + draining ring, Great Vibes script word | reflective or explanatory monologues where each line names something you could see on a phone | `recipes/clean-os/README.md` |
| **Vector explainer** | no footage: one SVG world a camera travels through, a subject drawing itself (stroke-draw), Playfair headlines on panels, word-reveal captions, ElevenLabs narrator, piano bed | parables, life lessons, concepts you can draw | `recipes/explainer-vector/README.md` (example: "Two Directions") |
| **RESULT** | one or two Inter Tight words with a small line + big word emphasis, Caveat handwriting, navy dust cards, polaroids, stop-motion paper stack, film-burn leaks, comic props (REC frame, incoming call, cursor dialog), dissolves between lines | storytelling, nostalgia, podcast-style monologues | `recipes/result-podcast/README.md` |
| **POV montage** | first-person clips cut to a story: speed-ups, flash-forward hook, freeze-frame + zoom + record scratch + meme, editorial motion layer with a footage-matched accent | trips, vlogs, a day in the life from glasses or a GoPro | `recipes/pov-montage/README.md` (example: SF Lime ride) |
| **Face RESULT** | RESULT over a talking head: the speaker's face as shot, paper props / polaroids / quote cards in zones beside, above or below the face (never on it), big two-tier captions on a navy card, film grain + dust only | the RESULT look when the speaker talks to camera | `recipes/result-podcast/README.md` ("Face RESULT") |
| **Whiteboard** | a split screen: a white marker board on top draws each thought live with a visible marker, Caveat handwriting, an eraser between pages; the speaker's face below as shot; white pill captions on the seam with the spoken word swept yellow | a talking head whose thoughts can be drawn as simple marker sketches | `recipes/whiteboard/SYSTEM.md` |
| **Kinetic doc** | B&W archive pictures as prints / windows / polaroids, every word popping on in one centred line with one big Oswald word, grey turn pages with a block cursor, one red accent (not the `kinetic` preset) | a black-and-white archive documentary in one grammar for a talking head, a voice-over over designed pictures, or B-roll only with a voice-over | `recipes/kinetic-doc/SYSTEM.md` |
| **Step Deck** | the speaker's face with every word on its onset behind their head, cut every 1-2 s against navy word cards, white word pages, B&W paper prints and line drawings; giant italic step numerals on navy / off-white / blue that shrink into place | a tips reel as a numbered deck over a talking head; from @ant.lon | `recipes/step-deck/SYSTEM.md` |
| **Product page** | white product pages (the real picture, rebuilt UI, hairline line art) moved by a virtual camera on the spoken words; the speaker's cut-out over a rounded footage card in the hook and splits; one spoken word in a grey pill; black two-tier titles (heavy sans + italic serif); white chest captions on face beats | a review or demo of a named tool, app or book; from @adrien.ninet | `recipes/product-page/SYSTEM.md` |
| **Tactile paper** | maroon paper and archive pages that unfurl and turn with a page fold on a stop-motion clock (8 fps), white arrows and a crimson marker, black pill captions; the paper turns away to reveal the speaker's face | a talk told on printed paper, with the speaker's face on the personal lines; from @chrismoran__ | `recipes/tactile-paper/SYSTEM.md` |
| **Caption News** | the speaker's face as shot under big captions slammed in 2-3 chunks on the word onsets, one keyword per caption on a yellow block, a title sting that becomes the channel bug, a document beat with highlighter sweeps and a source tag when a source is named | news-style takes that must read with the sound off; ported from lemo-opuscar (MIT) | `recipes/caption-news/SYSTEM.md` |
| **News Package** | the speaker as the anchor of a one-story TV segment: a sting that flies into the corner as the bug, a chest strap with a category tab, a rundown of the points ticked off at the end, full-frame package cards on ink (a document, a split-flap board, schematic cards) | one story with 3-5 points; ported from lemo-opuscar (MIT) | `recipes/news-package/SYSTEM.md` |
| **Telestrator** | the speaker's footage freezes on the key word and gets drawn on like a sports replay (rings, marker arrows, zones, one label card), around the face, never on it; yellow slanted wipes to dark tactics boards where an object is played, frozen and rewound | a line with an object the boards can play (a phone, an app, a list, a book); ported from lemo-opuscar (MIT) | `recipes/telestrator/SYSTEM.md` |
| **Halftone Dossier** | a retro print case file: cream paper, halftone dots in four flat inks, heavy misregistered headlines, stamps that slam, drawn exhibits that boil at 10 fps, the speaker's face as shot between the pages | a subject that can be "put on file": a habit, a product, a tool, a myth; ported from lemo-opuscar (MIT) | `recipes/halftone-dossier/SYSTEM.md` |
| **Swiss Grid** | International Typographic Style around the speaker's face: a 6-column grid, one typeface (Inter), one red, words set flush left on their onsets, giant numeral chapter cards, exact quiet motion | a talk in chapters, set like a poster; ported from lemo-opuscar (MIT) | `recipes/swiss-grid/SYSTEM.md` |
| **Data Story** | a chart draws itself on cream paper with a red-blue pencil when a line carries a quantity, handwritten notes, a figure caption with its source; the speaker's face as shot between the pages | lines that carry a quantity, with a primary source for every number (a chart with no verified number shows none); ported from lemo-opuscar (MIT) | `recipes/data-story/SYSTEM.md` |
| **Hologram HUD** | the thing the speaker talks about scanned into a glowing line wireframe, target boxes lock onto its parts, values roll in and dock as chips; cut against the face as shot, never over it | a talk about an object (a phone, a book, a list of habits) built as a wireframe model; ported from lemo-opuscar (MIT) | `recipes/hologram-hud/SYSTEM.md` |

