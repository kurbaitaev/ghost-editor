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

1. Copy the closest preset in `styles/` to `styles/<new-name>.json`.
2. Set `_about` (one line: the look and when to use it), `brand` (accent, accentDark, ink, fonts), `captions` (style, `upper`, `keywordStyle`), `sfxProfile`, `music` (an id or `auto` plus a mood tag in `library/music/manifest.json` `styles`), `look` and `scenes` defaults. Take all of these from the study or the reel.json that worked.
3. Add a row to the table above, and save the reel.json that defined it as `examples/gallery/<new-name>.reel.json`.
4. Render one existing example in the new style to confirm it reads as its own look.

## Caption and overlay safety (all styles)

`scripts/face_track.py` must run before the build. The placer then:
- puts every caption block **below the chin** near the ideal reading height, else **above the head**, else shrinks it (down to 70%) to fit above the head, and only as a last resort puts it **as low as the platform allows** on a dark backing (never over the eyes or the mouth)
- keeps blocks in the same zone while it fits (no top/bottom jumping)
- keeps inside the platform's safe area (`"platform": "instagram" | "tiktok" | "shorts" | "all"`) and clear of the right-hand button column
- places cards (`big`, `chips`, `strike`, `quote`, `list`) beside the face too; a `big` with no room is promoted to a full-screen scene
- puts emoji/logo/meme on the side of the head with room, or skips them
- steps captions around cards on screen at the same time

`build/caption_layout.json` records every block's zone. `qa.py` prints the counts and fails on anything outside the safe area.
