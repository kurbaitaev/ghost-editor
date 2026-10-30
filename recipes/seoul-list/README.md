# Seoul list: a voice-over list over fast B-roll, two type families, phone-UI stickers, an iMessage outro

Call it with: **"Seoul list"**, **"like the Seoul reel"** (also "edit this in Seoul list").

From a 46 s list reel about life in Seoul (Sep 2025). The numbers below come from its breakdown (shot lengths, every
element checked on full-res frames).
**Status (Oct 2026):** the mechanics are proven by a smoke test (that reel's own voice, music removed, over unrelated
clips, compared with the reference block by block). The look still has to be proven on the next real video.
**Read SYSTEM.md before planning a reel**: what must stay, what must change.

**When to use:** a calm voice-over (not to camera) listing 5-8 observations about a place, a trip or a topic, ~100 words
in 45 s, over B-roll (the user's own when they hand it over). A selfie shot as the opener is fine. For talking heads use the main flow, Clean OS or RESULT.

**Footage ("Seoul list" names the format, not the footage source).** Full-screen B-roll is the
format, so any footage may fill the screen. In order:
1. Footage the user hands over for this reel: always used.
2. The user's own library through `own_footage.py` (face-checked: only the speaker appears; show the user the confirmation sheet before the render).
3. Sourced B-roll, stock or AI, full screen allowed here (the "stock only inside a frame" rule is for talking-head styles).
4. A line with no fitting footage can still become type: a word flash, a list, a collage page, a phone sticker.

The quality bar keeps the B-roll few and good-looking. It is checked by
`broll_qa.py <render> --project $P --profile broll-led --style seoul-list`:
- **People rules:** configurable B-roll people rules (`people-rules.json`; e.g. exclude women, or symbols; the default
  file has none, see `people-rules.example.json`). A shot that breaks a rule fails: pick an empty street, a detail or
  another shot. `broll_vision.py picks` before the render, `broll_qa.py` check `people` (skipped when no rules are set).
- **Each shot shows its line** (check `match`); a line with nothing that fits becomes type. Stock images on a collage
  page are fine.
- **One graded world:** every clip goes through `insert_prep.py --ref <ref>`: the speaker's face plate AS SHOT, or with
  no face of the speaker the main footage the user handed over. Never regrade the speaker's face to a house look, and the
  inserts agree. The spread across them must stay within L* sd 14 and b* sd 5
  (the reference: 11.8 / 2.5).
- **No posed stock models:** places, objects, the speaker's world. A stranger's face filling 8 % or more of the frame width fails.
- **Reference pace:** a median shot of 0.9-2.2 s (the reference: 1.30 s).
- **1080p or better.**
- Spoken lists of activities ("swimming, cycling, football") are typography, not one 0.5 s clip per noun.

In an audit of test reels, the lowest-scoring one (4.0) failed on mismatched stock, not on stock as such: 21 unrelated
posed models in three light worlds (white balance spread 7.7 b*).

## Anatomy (measured on the reference)

| block (`type`) | look | timing |
|---|---|---|
| B-roll montage (`shots`) | hard cuts, median 1.4 s (0.8-2.7), one long hold allowed, opener can be a selfie | cut on spoken words; 1 transition max: a zoom-blur whip into the outro (`tx`) |
| word beat (`word`) | ONE big word ~600-700 px wide (short words get bigger) + a subline (~54 px) tucked under its right end, or small words over its corners. *Playfair Display Italic* for mood/place words, *Inter Tight 800* (tight, CAPS for the contrast word) for facts. White, soft dark shadow, centred at 45-55 % | blur-in 0.22 s ON the spoken word (stagger ~0.1 s), fade out 0.12 s; a new word every 0.7-1 s |
| stacked list (`list`) | heavy words stacked (three verbs, one per line) | each on its word |
| white word flash (`flash`) | white frame, one black heavy connector word ("even", "cameras &"), small | 0.4-0.8 s, hard in/out |
| white collage page (`collage`) | (a) the current shot shrinks into a rounded card on white, a small black line above; the card dissolves as a red glitch serif word lands and the line drops under it; hand + 👀 stickers. (b) heavy black line above a photo card that flies in tilted and lands straight, italic serif word under it, a sticker at the edge | the hook, 1.5-3 s per page |
| triptych (`triptych`) | three shots as equal 640 px bands | under a list or a comment card |
| Instagram comment (`comment`) | white rounded card, round avatar, text typed word by word on the voice, emoji, a faint "Reply" label | the first-person aside, ~2 s, notification sound |
| macOS window (`window`) | dark frosted glass (a blurred copy of the shot), red/yellow/green dots, label or logo top right, a BiRefNet cut-out; the shot behind darkened | swaps item + label on each spoken item |
| blue highlight (`highlight`) | iMessage blue (#0B84FE) blocks behind white heavy words, left-aligned, stacked like a selection, optional emoji | each wipes in on its word |
| iMessage outro (`imessage`) | the last shot shrinks into a card on black and floats off in 3D (+ 0-4 tilted photo cards from the reel), a blue typing bubble (•••; blue in the reference, not grey), the blue bubble with the closing word, an emoji tapback on its corner | starts >= 1 s before the closing word; bubble ON the word |
| sound | measured on the downloaded reel: NO audible music bed (the mix in VO pauses is -54 dB) and only 3 non-voice hits (hook whoosh, photo-card fly-in, the outro send). Gemini's "~25 hits + lo-fi bed" is not supported | `sfx: "reference"` reproduces exactly that; a bed is optional |

The reference's cartoon glove hands are Disney/Mickey-style art: never copied. Stickers are Fluent emoji (MIT) from
library/emoji: `waving-hand`, `hand-splayed`, `point-right`, `eyes`, `running`, `yum`, `fire`, ... Brand logos are never
bundled: pass the user's own image as `logo`, or a text `label`.

## Pipeline (end to end)

```bash
S=~/.claude/skills/ghost-editor; R=$S/recipes/seoul-list; P=~/reels/<name>; HF="$S/scripts/hf.sh"   # the pinned HyperFrames (scripts/HF_VERSION)
mkdir -p $P/clips && cd $P
# 1. proxies: 1080x1920 30 fps H.264, no audio, refuses < 1080p; originals are never moved or modified
bash $R/proxy.sh <out-dir> <clips...>     # e.g. bash $R/proxy.sh clips ~/Downloads/my-trip/IMG_1.MOV ~/Downloads/my-trip/IMG_2.MOV
#    pick shots on 1 fps sheets: ffmpeg -i clips/X.mp4 -vf "fps=1,scale=180:320,tile=20x1" -frames:v 1 X.jpg
# 2. the voice-over (if it has music under it: voice_enhance.py IN clean.wav --mode enhance, audio-QA venv)
python3 $R/prep.py voice <your-read> assets/voice.wav [--keep 0-21.2,24.6-26.4 --gap 0.2]   # -16 LUFS, frame-snapped pieces
python3 $R/prep.py words assets/voice.wav build/words.json                                # whisper turbo + word times; read it
# 3. stills (LOOK at each; confirm the avatar is the speaker)
python3 $R/prep.py still  clip07 6.0  stills/photo-01.jpg         # photo / outro cards: a proxy frame
python3 $R/prep.py cutout clip01 9.0  stills/item-pastry.png      # window items: BiRefNet (matte venv), cropped to the object
python3 $R/prep.py avatar clip10 30.0 stills/avatar.jpg           # comment avatar: YuNet face crop
# 4. list.json (start from example/list.json), build, lint, LOOK at every beat
node $R/build.mjs $P                     # shots, beats + snapshot times, SFX table, music, WARNINGS
$HF lint                                 # 0 errors, 0 warnings
python3 $R/snap.py beats $P --shots      # build/snaps/<beat>.jpg + overview.jpg: read every strip, fix, rebuild
# 5. after the user's yes: render, QA, the frame-exact cut check, per-block strips
$HF render -o renders/<name>.mp4 --quiet
python3 $S/scripts/qa.py $P renders/<name>.mp4         # A/V lengths, loudness, SFX vs voice on a stem, silences, contact sheet
python3 $R/snap.py cuts $P renders/<name>.mp4          # each visible cut shows exactly its proxy frame (best offset 0)
python3 $R/snap.py strips $P renders/<name>.mp4        # build/strips/<beat>.jpg from the render
```
Against a reference: `snap.py compare REF.mp4 RENDER.mp4 --pairs "label=refT,...:ourT,...;..." -o compare`.
approval_sheet.py and render_report.py read reel.json, so for this recipe send the user `build/snaps/overview.jpg` and
the strips as the approval page, then deliver as in SKILL.md step 8.
A Python generator (a reel's own short script) imports the plumbing from `$R/seoul.py` instead of writing
a lib: `sys.path.insert(0, "$R"); from seoul import *`, then `setup("$P", cut="<clip>/edit")`, `W(word, near)` for word times,
`vid` / `card` / `still_clip` for stock inserts, `write(spec)` (list.json + build.mjs + the readability CSS) and `measure(spec)`.
`python3 $R/seoul.py --api` lists every call with its signature; the reel's own new components stay in its generator.

## list.json

Top level (all optional except `shots`):

| key | default | |
|---|---|---|
| `voice` | `assets/voice.wav` | from `prep.py voice` |
| `words` | `build/words.json` | from `prep.py words`; re-run whenever the voice changes |
| `clips` | `clips` | the proxy folder; a clip is named without `.mp4` |
| `fixes` | | whisper corrections used for matching: `{"Five": "5"}` |
| `tail` | `1.0` | seconds after the last word |
| `sfx` | `restrained` | `reference` (hook word, photo fly-in, outro send), `restrained` (+ one per block), `standard` (+ every sticker, swap and item, ~10 per 10 s), `none` |
| `mix.roleDb` | ui -14, whoosh -12, impact -8 | SFX level per role, dB against the voice's p95 peak (as build.mjs) |
| `music` | none | `{"id": "lo-fi-02"}` (library/music) or `{"src": ...}`; `db` -14 vs the voice, `duck` -6 dB under speech, `start`, `fadeIn` 0.6, `fadeOut` 1.2 |
| `blue` | `#0B84FE` | highlight and bubble blue |
| `title`, `fps` | `Seoul list`, 30 | the frame is always 1080x1920 |

**Time refs.** A time is a VO second (number) or a word ref, matched case-insensitively, ё = е, punctuation ignored, after
`fixes`: `"Lisbon"` = first occurrence at or after the previous ref in list order (minus 0.3 s); `"in#2"` = the 2nd
occurrence in the whole voice (**a repeated word needs #n**); `"^life"` = the word's end; `"Portugal+0.2"`, `"^coffee-0.1"`
= an offset. A word not in the voice stops the build and prints the words it has.

**shots** run back to back from 0 to the end: `{"at", "clip", "in", "zoom", "tx", "txDur", "txSfx"}`. `at` = when it
starts (ignored on the first), `in` = clip second (proxy = source times), `zoom: [1, 1.06]` = slow push, `tx` = a
transitions.py transition INTO this shot (`zoom_blur` is the reference's whip; `python3 $S/scripts/transitions.py list`).
The build stops if a clip is too short.

**beats** share `at` (start), `to` (end; a text beat ends at the next text beat or scene, max 2.4 s; a scene at the next
scene, max 6 s: **give flashes and collages a `to`**), `y` (0-1), `sfx` (false, an id or a list: replaces the default
hit), `label`. Per type:
- **word:** `big` = a string (its words appear as spoken) or `[{text, at, family, size, color}]` segments (e.g. an upright
  "5"); `family` serif (default, italic) | serif-up | sans (800) | sans-it; `size` 150 serif / 140 sans (base); `width`
  = on-screen target px (660 serif / 620 sans; the page scales the big text to it x0.6-1.7; 0 keeps `size`); `caps`,
  `color`, `together` (all at once 0.1 s apart), `maxWidth` 960. `sub` = string | `{text, at, pos, size, family, color,
  caps}` | array; `pos` below-right (default) | below-left | above-left | above-right | below | above; size 54; default
  time = its first word as spoken near the big word (give `at` if it is not spoken). `subPos` / `subSize` for all subs.
- **list:** `items` (strings or `{text, at}`), `size` 104, `lineGap` 0.92, `family` sans, `caps`.
- **highlight:** `items` (strings or `{text, at, emoji}`), `size` 84, `x` 96 or `align: "center"`, `y` 0.47.
- **flash:** `text`, `family` sans, `size` 92 (kept as set), `sub` (e.g. `{"text": "&", "pos": "below-left"}`), `y` 0.48.
- **collage:** `shrink: {}` or `{scale: 0.63, until}` (the current shot shrinks into a card, dissolves at `until` / the
  big word); `line` (string or `{text, at, size, family}`, word by word; 58 px over a card, 88 px over a photo); `photo`
  (path or `{src, at, w 792, h 446, y, tilt 16}`, flies in tilted); `big` (string or `{text, at, family, size, color,
  caps, glitch, sub, y}`; `glitch: true` = red ghost copies + glow, colour #FF3B30); `stickers: [{emoji, x, y, size 150,
  at, to}]` (x/y = centre px; default time just after the big word, 0.12 s apart). Without a photo the line drops under
  the big word as its subline; with a photo the line sits above the card and the big word below it.
- **triptych:** `clips` (three `{clip, in, pos}`; `pos` = vertical object-position %), `stagger` (s between band
  slide-ins; omit for a hard cut). Black page underneath.
- **comment:** `text` (each word appears on its spoken word), `emoji` (pops right after the last word), `avatar`
  (`prep.py avatar`), `reply` (the faint label under the text, e.g. "Reply"; the built-in default is Instagram's Russian
  label, so set it for any other language).
- **window:** `bg: {clip, in}`; `items: [{img, label | logo, at}]` (cut-outs from `prep.py cutout`; each swaps in at its
  `at`, default 1 s after the previous); `w` 720, `h` 520, `dim` 0.58, `bgBlur` 3.
- **notify:** an iOS notification banner: `app` (upper-case header), `time` (e.g. "now"; the built-in default is the
  Russian iOS label, so set it for any other language), `title` (bold, blurs in at `titleAt`), `text` (typed word by word
  on the voice from its first spoken word, or `textAt`), `emoji` (the app tile), `tile` (tile colour), `y` 0.19. A number
  or a fact with its source ("Study review / 38,000+ workers").
- **imessage:** `word` (bubble text, timed to that spoken word, or `at_word`), `at` (outro start; default `lead` 1.05 s
  before the word; the build warns under 1 s), `emoji` (tapback), `cards` (up to 4 stills), `typing` 0.42, `x` 150,
  `y` 0.5, `typingColor`, `sendSfx` (send-swoosh). It runs to the end.

Outputs: `index.html`, `assets/` (hard links to the used proxies, fonts, emoji, SFX, stills, transition windows),
`build/sfx_events.json` + `build/transitions.json` (qa.py), `build/beats.json` (snap.py), and the printed report.

## Rules (each one bit the smoke test or comes from the reference)

- Everything is keyed to the VO's word times; write list.json from the whisper printout. Whisper can write a spoken hook
  number as a word ("Five things" -> "Five"): fix it in `fixes`, then refs can say "5".
- Every word lands on its own spoken time, including a big word whose block opens on a small word said first, and a
  subline (key it to its FIRST word). The smoke build showed three big words 0.22-0.56 s early; fixed in build.mjs.
  Checked on the render: whisper word times = words.json (58/59 within 20 ms), audio offset 0 samples, every caption
  frame equal to the timeline's.
- Read every strip from `snap.py beats` before rendering. The first smoke build had glitch ghosts visible from frame 0
  (a ghost's first tween started at opacity .85; the seek-safe helper applies the first from-state at load), 3 px word
  gaps (an em gap on a 16 px parent), a subline floating above the word next to a 330 px "7", a comment emoji with no
  size (`.cm-text span {display: inline}` won over `.iemo`), an outro card that went empty when its footage ended before
  its fly-off, and a typing bubble on top of the still-shrinking card. All fixed in build.mjs; this class of bug only
  shows in the snapshots.
- The window's glass is a blurred second copy of the background video one frame later (identical copies trip
  hyperframes' `duplicate_media_discovery_risk`); not backdrop-filter.
- Keep SFX sparse (the reference has 3 hits in 46 s); `restrained` is one hit per block. A bed is the user's call.
- Photo and outro cards are frames from the reel's own clips. The avatar is the speaker's face crop or a photo the user
  gives; confirm it.
- No 720p B-roll (proxy.sh refuses it). Proxy on the machine that holds the footage; never move or modify originals.

## Worked example

`example/list.json` with `example/script.txt`: an English voice-over, "5 things that surprised me in Lisbon" (7 lines,
71 words, about 30-35 s), 16 shots from `clip01`-`clip10`, 17 beats, every block type except `notify` at least once
(word, collage with a shrinking card and with a photo card, flash, highlight, window, triptych, comment, list,
imessage), a zoom-blur whip into the outro, lo-fi-02 bed at -14 dB ducked -6 dB. It is for reading and copying: the
recording, the clips and the stills are yours to supply. Record script.txt (one block per line), proxy your clips as
`clips/clip01.mp4` ..., make the stills with `prep.py still / cutout / avatar` under the names list.json uses, run
`prep.py words assets/voice.wav build/words.json --lang en`, then re-time the `in` values to your clips. Every word ref
in list.json resolves, in order, against script.txt; check them again against your words.json (whisper may write
"Five" or "5"; `fixes` maps it so refs can say "5"). A dry run (test-pattern clips, a tone for the voice, word times
synthesised from script.txt) builds with no errors and lints 0/0; it has not been rendered with real footage.
