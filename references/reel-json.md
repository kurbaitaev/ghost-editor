# reel.json: the whole edit in one file

`build.mjs` turns this into `index.html` (HyperFrames). Every time is an
ORIGINAL-recording second, as printed by `transcribe.py`, except `"end"`
(the last frame) and `"outro+N"` (N seconds into the frozen outro). A time
that falls in cut material fails the build with the beat's name. `"hold:1+0.7"` is 0.7 s into the
hold after take 1. Any on-screen text with Cyrillic switches the card font from Geist to Inter.

```jsonc
{
  "title": "why nobody cares about your launch",
  "source": "assets/talk.mp4",          // prep.sh output (voice at -16 LUFS)
  "words": "build/words.whisper.json",  // transcribe.py output
  "fps": 30,
  "outro": 3,                           // seconds of frozen last frame under the end card
  "takes": [                            // edit order; a = first word - 0.10..0.15, b = last word + 0.20..0.30
    { "a": 6.58, "b": 10.40, "note": "hook, 2nd take" },
    { "a": 10.76, "b": 14.42, "hold": 0.8 }   // hold: frozen last frame, no voice, AFTER the take: air for a meme on a
  ],                                          // tightly cut recording. Address it as "hold:<take index>+<seconds>"
  "zoom": {
    "origin": "50% 29%",                // the face; move it if the face sits elsewhere
    "snaps": [[10.76, 1.1], [16.30, 1.0]],   // instant reframes: every cut + most sentence starts, 1.0/1.1, 1.12 on a punchline
    "pushes": [{ "at": 19.8, "z": 1.1, "up": 0.4, "until": 22.4, "down": 0.2 }],  // slow push-ins, 4-6 per reel, no overlaps; until "end" holds through the outro
    "snapSfx": false                    // true = quiet whoosh on every snap; default off (dry cuts read more premium)
  },
  "captions": {
    "style": "house",                   // house: Arial bold 56, white, black outline, lower third. "pill": Geist 66 on a dark pill.
                                        // "none": the recording already has burned-in captions (never stack two caption layers)
    "group": 3,                         // words per caption (also breaks on , . ? ! and on pauses > 0.6 s)
    "highlight": null,                  // e.g. "#FFD166" to colour the spoken word; null = scale-pop only
    "size": 56,
    "fixes": { "Jithub": "GitHub" }     // whisper word -> correct word, case-insensitive
  },
  "layout": { "cardY": 990, "capBottom": 450,     // card band top, caption bottom margin (IG UI covers the bottom 450)
              "slotY": 240,                        // reaction slot top (emoji / logo / meme next to the head)
              "compact": false },                  // smaller cards for a narrow band, e.g. under burned-in captions
  "mix": { "roleDb": { "ui": -14, "whoosh": -12, "impact": -8, "meme": -3 } },  // SFX peak vs voice p95 peak, dB
  "beats": [ /* see below */ ],
  "sfx": [{ "at": 24.4, "id": "record-scratch", "db": 0, "lead": 0 }]   // extra hand-placed sounds
}
```

## Beats

All beats take `at`, `to` (optional; default 2.5 s, meme 1.8 s) and `sfx`
(optional): omit for the default, a kit id or list of ids to override,
`"none"` for silence. Card beats live in the band under the chin; `emoji`,
`logo` and `meme` share the reaction slot next to the head (one at a time,
the build warns on a double booking).

| type | fields | default sound | use when the speaker says |
|---|---|---|---|
| `big` | `text`, `sub`, `count` (count up a number) | whoosh-cine + impact (text slam) | a number, a duration, a claim they would put on a website |
| `chips` | `items: [{text \| icon \| src, label, bg, fg, invert, at}]` | pop per chip (round-robin) | a list of names or numbers, one chip per spoken word |
| `strike` | `text`, `strikeAt` | whoosh | "not X", a myth, a claim they dismiss |
| `quote` | `header`, `lines: [{text, at, big}]` | impact on the `big` line | what someone told them |
| `list` | `lines: [{text, at}]`, `stamp`, `stampAt`, `stampSfx` | pop per line, impact + buzzer on the stamp | a list they then dismiss |
| `emoji` | `emoji`, `x`, `y` | pop | a feeling (push in on the speaker at the same time) |
| `logo` | `icon` (simple-icons slug) or `src`, `bg`, `invert` | pop | a product or company that should land alone |
| `meme` | `id` (library), `audio` (false = mute the clip's own sound), `in` (start later in the clip), `w`, `x`, `y`, `tilt`, `db` | clip: its own audio; image: its `sfx` or vine-boom | a punchline, a reaction, a wait. ON or just after the punchline word, never before |
| `endcard` | `title`, `line`, `url` (usually `at: "outro+0"`) | whoosh | the close |

`icon` slugs come from simpleicons.org (fetched at build time, CC0).

## Style, platform, look (top level)

- `style`: a preset from `styles/` (see `references/styles.md`); reel.json overrides it.
- `platform`: `instagram` (default), `tiktok`, `shorts` or `all`. It sets the safe area captions and cards stay inside.
- `sfxProfile`: `restrained` (structural hits only), `standard`, `rich` (adds a whoosh to every snap).
- `look`: `{grade: "<css filter>", grain: 0.07, vignette: 0.45}`, the film look over the speaker plate.
- `matte: true`: cut the speaker out once (`hyperframes remove-background`, cached as `assets/talk-matte.webm`, ~4 fps) for `behind` beats.
- `captions.phrases: {"a call for reach": "Coffer Reach"}` fixes multi-word whisper errors.
- `captions.upper: true`: uppercase captions. `captions.keywordStyle: "serif"`: highlight words become a glowing serif italic (cinematic).
- `face`: the path to the face track, default `build/face.json` (run `scripts/face_track.py`). Without it, captions sit at a fixed height and the build warns.

New beat:

| type | fields | default sound | use for |
|---|---|---|---|
| `behind` | `text`, `at`, `to`, `size` (auto-fits the width), `y` (auto: head height), `color` | impact | the 2-4 biggest words, BEHIND the speaker (needs `matte`) |

## Motion layer (scripts/lib/motion.mjs)

Top-level fields:

- `brand`: `{accent, accentDark, ink, capSize, font}`. A 60/30/10 kit: one accent, a darker accent for text on light scenes, ink for dark text. `font: "Montserrat"` is bundled with Latin and Cyrillic.
- `zoom.base`: a constant punch-in on the speaker, for example `1.8` with `origin` at the face. `pushes[].sfx` puts a whoosh on a push-in.
- `captions.style: "editorial"`:
  - Lowercase lines of `group` words.
  - The spoken word resolves out of blur in bold white. The previous line relaxes to a light weight.
  - A block is two lines, or a tag pill plus two lines.
  - `tags: ["for Gen Z", "Gen Z"]` renders those phrases as tilted accent pills. List longer phrases first.
  - `highlight: ["fundamental"]` wipes an accent box behind the word.
  - `y` is the top of the block (default 1150).
- `music`: `{id | src, db: -20, fadeIn, fadeOut, start}`. The bed is set `db` below the -16 LUFS voice, from the track's own measured loudness. The library is `library/music/manifest.json`.

`scene` beats are full-screen graphic scenes over the continuing voice. Captions hide during a scene unless `captions: true`.

- **Transitions:** `in` is `blur` (default), `expand`, `wipe`, `glitch` or `cut`. A style can set `scenes.default_in`. `out` is `blur` (default) or `cut`. A scene that ends where an expand or wipe scene starts stays underneath for 0.45 s.
- **Sound:** default sounds are listed per kind below; expand and wipe also get a whoosh.

| kind | fields | what it looks like |
|---|---|---|
| `card` | `bg`, `y`, `lines:[{text, at, size, color}]`, `pill:{text, at, size, gap}`, `cursor:{clickAt, dx, dy}` | Centred text plus a tilted accent pill; a cursor flies in and clicks it (ring, press). Sounds: pop, then click |
| `stats` | `bg:"accent"`, `badges:[{value, sub, at, label:"follow **bold part**", labelAt}]`, `centerY`, `gap` | Glass ring badges land big (whoosh). On `labelAt` they shrink into a row with the label typed beside them, and earlier rows re-centre |
| `fly3d` | `bg`, `items:[{text, sub, at, x, y, z, size}]`, `cam:{from, to}`, `focus`, `ease` | Words in 3D space; a camera dolly moves through them, and blur and grey level follow the distance to focus. Seek-safe painter. Sounds: riser, whoosh per word |
| `image` | `src`, `zoom:[1, 1.1]`, `grade`, `captions: true` | A full-bleed still with a slow push. AI B-roll comes from `scripts/broll_gen.py` |
| `ui` | `title`, `label`, `prompt:{text, at, cps}`, `lines:[{text, at}]`, `y` | Dark app/terminal window: the prompt types in (typing sound), result lines tick in with checks. Product launches |
| `device` | `src` (an image) or `lines:[{text, at, me}]`, `label`, `y` | A phone frame rises and floats; an image or a mini chat whose bubbles pop in |
| `kinetic` | `text` (`*keyword*`, `_filler_`), `bg`, `size`, `zoom`, `pullback`, `pip`, `pipX`, `pipY` | Full-screen word-by-word type aligned to the spoken words; a camera glides from word to word, then pulls back. `pip: true` shrinks the speaker into a round window |
| `sentence` | `bg`, `lines:["...", "..."]`, `hero:{text, at, size, color}`, `sub:{text, at, cross, crossAt}` | Words ink in as they are spoken (matched to the transcript), then shrink up while a big accent hero lands (impact). The `cross` word gets a drawn X |

Helpers:

- `scripts/autocut.py talk.mp4 --noise -30` prints `takes` for a single clean take. It cuts pauses from the audio, because whisper's word times hide them.
- Scene times may sit up to 1.2 s inside a removed pause; they snap to the next kept moment.
- Each whisper word belongs to the one take it overlaps most, so boundary words are never duplicated.

## What the build enforces (warnings, printed after the SFX table)

- the same meme sound twice in one reel
- meme sounds < 8 s apart; > 3.5 meme sounds per minute
- > 14 whoosh/impact/meme hits per minute (a layered whoosh+impact counts once)
- a meme sound landing on speech (put it in a pause: extend the take's `b` to keep the air, or place it on the end of the punchline word)
- the reaction slot double-booked
- an em dash in on-screen text
