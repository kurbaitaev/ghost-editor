# Stan style: a seated tool tutorial with screen recordings on top

Call it with: **"stan style"**, **"tool tutorial"** (also "edit this in stan style").

From @nicktarmo's tool tutorial (Oct 2026, 100 s). The numbers below come from its breakdown (verbatim script, every
element checked on full-res frames); this README corrects the breakdown where the frames disagree (see "Measured"
below). **Status (Oct 2026):** the mechanics are proven by a smoke test (a talking head plus three screen recordings,
every block once, compared with the reference). The look still has to be proven on the next real video. **Read SYSTEM.md
before planning a reel.**

**Prerequisite: real screen recordings of the tool being explained.** Without them, say so and propose Clean OS (the
idea as phone UI) or RESULT. Never fill the band with stock: a test reel filled it with stock people (a student with a
laptop, code over a shoulder), their heads cut by the band, and it read as filler.

**When to use:** a talking head explaining a tool, a workflow or a how-to in steps, with screen recordings of it
("here's how", "step one..."). One continuous take is the norm (choose takes as usual if not). It is NOT a separate
renderer: it is the core pipeline (prep.sh, transcribe.py, face_track.py, takes, build.mjs, approval sheet, render,
render_report.py, qa.py) with six beat types and the `chest` caption style from `scripts/lib/stan.mjs`.

## Anatomy (measured on the reference, 1080x1920)

| block | look | timing |
|---|---|---|
| speaker | one seated medium shot; the eyes sit at ~42 % (y 815); a hard punch-in for the benefit line + CTA (`zoom.snaps`) | the whole reel |
| `panel` (split screen, ~half the runtime) | the screen recording fills the top band edge to edge (cover-cropped), no frame, no shadow, BEHIND the speaker: their head is cut out and drawn over it, so the hair overlaps the screen (the reference band ends at y 700-780, 37-40 %). The speaker moves down only as far as the eyes need to sit ~80 px under the band (the reference never moved; the build computes it from face.json) | pops in (scale 1.05 -> 1 + fade, 0.2 s) and out (1 -> 0.95); the next panel pops in over the previous one with no speaker move between them; a mouse click on each cursor click |
| `chest` captions | small white lowercase phrases (3-6 words, ~38 px Inter medium, soft shadow, no box) centred at y ~1305 (68 %); no punctuation | each phrase CUTS in on its first word (no animation) |
| single words | one word at a time, ~66 px, same height: the hook (`captions.single`) and every diagram (black there, y ~1378) | cut on each word |
| forehead words | one word at a time, ~64 px at y ~557 (29 %): a stretch near the end (`captions.top`) and `emphasis` words | cut on each word |
| `hook` card | 1-2 rows of icons (~150 px) around a 1-2 line title in BLACK bold type on WHITE rounded strips (the breakdown said white on black: the frames show black on white), over the speaker | the first 1-5 s; at frame 0 it is simply there |
| `diagram` scene | the only full-screen graphic: white, icons (~100-130 px), a bold black word (~110 px, «Idea»), curved black lines that draw on, a ringed dot at a line's end | entered by a zoom-blur from the speaker, ~4 s, a scribble per line |
| `step` label | «[Step n]» (~46 px, medium) over a title (~46 px), the app icon(s) under them (~88 px), stacked just above the caption, under the chin | with the matching panel on top |
| `cta` label | «Comment "word" for the prompt» + the product logo, in the step's place | when the prompt is on screen and at the end over the close-up |
| `aside` | «*content sauce*» upright white (~66 px, semibold, the breakdown said italic: it is not) above the head | a spoken joke, on a full speaker shot |
| sound | (Gemini, not yet measured) a bed under the voice, a whoosh into the diagram, pen scribbles, mouse clicks | restrained |

Gemini's edit log was wrong about the captions (it said word by word at 52 %), missed the split screen, and claimed a
"24/7 strobe": frames 0.1 s apart show no strobe, so `strobe` exists but is off unless asked for.

Icons are user-supplied: `src` (their own logo files), `icon` (a simple-icons slug fetched at build time) or `emoji` (a
Fluent emoji from library/emoji, MIT). Brand logos are never bundled.

## reel.json (on top of references/reel-json.md)

```jsonc
{
  "captions": { "style": "chest",
    "single": [[0, 4.9]],                 // original-second windows: one bigger word at a time at the chest (the hook)
    "top": [[79.6, 95.7]],                 // one word at a time at the forehead
    "emphasis": ["find", { "word": "works", "at": 94.7 }],   // single words lifted to the forehead
    "strobe": [],                          // optional blink on a word (not in the reference)
    "y": 1305, "size": 38, "wordSize": 66, "topY": 557, "topSize": 64, "inkY": 1378, "maxWords": 6, "maxChars": 30, "lower": true },
  "zoom": { "origin": "52% 42%", "snaps": [[93.0, 1.22]] },          // the punch-in close-up
  "music": { "id": "lo-fi-02", "db": -22 },                           // optional bed
  "beats": [
    { "type": "hook", "at": 0, "to": 4.9, "title": ["AI automation tutorial", "for creative content ideas"],
      "icons": [[{ "src": "logos/video.png" }, { "src": "logos/app.png", "label": "the app" }],
                [{ "src": "logos/chat.png" }, { "src": "logos/newsletter.png" }, { "src": "logos/social.png", "bg": "#000" }]] },
    { "type": "diagram", "at": 5.1, "to": 9.5,
      "nodes": [{ "id": "src", "src": "logos/video.png", "x": 330, "y": 1000, "at": 5.4 },
                { "id": "app", "src": "logos/app.png", "label": "the app", "x": 540, "y": 600, "at": 6.6 },
                { "id": "idea", "text": "Idea", "x": 540, "y": 340, "at": 8.4 }],
      "links": [{ "from": "src", "to": "app" }, { "from": "app", "to": "idea", "dot": true }] },
    { "type": "panel", "at": 11.2, "to": 15.0, "src": "rec/app.mov", "in": 2.0 },
    { "type": "step", "at": 46.0, "to": 50.4, "n": 1, "title": "Create a private channel", "icons": [{ "src": "logos/chat.png" }] },
    { "type": "cta", "at": 66.0, "to": 70.0, "word": "ritual", "logo": { "src": "logos/app.png" } },
    { "type": "aside", "at": 30.0, "to": 31.4, "text": "content sauce" }
  ]
}
```

| type | fields | default sound |
|---|---|---|
| `panel` | `src` (mp4/mov, 1080p or better), `in` (seconds into it), `to`, `behind` (default true: the speaker's cut-out is drawn over the panel; `false` = the panel covers the speaker), `h` (band height px, default 768), `gap` (eyes under the band, default 80), `pos` (object-position, default `50% 50%`), `zoom` ([from, to] slow push), `clicks` (recording seconds; default: the `clicks` list of `<src>.json` if it exists; `false` = none), `clickSfx` | click-1 per click |
| `hook` | `title` (string or 1-2 lines), `icons` (one row, or two: `[[above], [below]]`), `iconSize` (150), `size` (title px, 62, shrinks to fit), `y` (top, default 250; moves up off the eyes) | pop (none at frame 0) |
| `diagram` | `nodes: [{id, x, y, emoji\|icon\|src\|text, label, size, at, sfx}]` (centre px), `links: [{from, to, at, dur, bend, dot, width}]` (a line draws from `from` to land when `to` appears, unless timed), `bg`, `ink`, `sfx` (the whoosh in) | whoosh in, marker-scribble per line |
| `step` | `n`, `title`, `icons`, `label` ("Step"; "Шаг" for Cyrillic), `size` (46), `iconSize` (88) | pop |
| `cta` | `word`, `text` (default «Comment "{word}" for the prompt» / «Напиши "{word}" в комментариях»), `logo` (an icon), `size` | pop |
| `aside` | `text` (asterisks added), `y`, `size` (66), `italic` | none |

Icons everywhere: `{emoji | icon | src, label, size, bg (a tile colour), invert}` or a bare emoji slug string.

What the build does for you: the person cut-out over every panel run (BiRefNet-portrait via scripts/matte.py for just those
source seconds, cached in assets/talk-matte.webm; a second copy of the camera wrappers keeps it on the speaker through zooms,
punch-ins and the speaker's move), the panel run's speaker move (from face.json and the camera zoom), the step/cta stack placed
above the caption and pushed (with the captions) under the chin when the speaker sits low, top words kept off the eyes and
moved to the chest while a panel covers the forehead, black diagram captions, a panel that stays up 0.2 s under the next
one, one file per icon use (the same image twice trips hyperframes' duplicate-media lint). It warns when a label covers the
chin, a hook card reaches the eyes, the eyes are too high for the band, or a recording is under 1080p.

## Pipeline (end to end)

```bash
S=~/.claude/skills/ghost-editor; P=~/reels/<name>; HF="$S/scripts/hf.sh"   # the pinned HyperFrames (scripts/HF_VERSION)
bash $S/scripts/prep.sh <IMG_xxxx.MOV> $P                                     # talk.mp4, voice at -16 LUFS
python3 $S/scripts/transcribe.py $P/assets/talk.mp4 --out $P/build/words.whisper.json --lang ru
python3 $S/scripts/face_track.py $P/assets/talk.mp4 --out $P/build/face.json   # required: the panel move and every label use it
mkdir -p $P/rec && cp <screen recordings> $P/rec/                              # Cmd-Shift-5 recordings; 1080p+; note the click times
# reel.json: takes, then beats from the transcript (start from example/reel.json); one panel per sentence that names
# something on screen, a step label per "step N", the CTA on the comment line
node $S/scripts/build.mjs $P                                                   # read the SFX table and every WARNING
python3 $S/scripts/approval_sheet.py $P --open                                 # lint 0 errors + a frame per beat; WAIT for the user's yes
$HF render -o build/reel.mp4 --quiet
python3 $S/scripts/render_report.py $P build/reel.mp4 && python3 $S/scripts/qa.py $P build/reel.mp4
```
(If plain `python3` has no numpy/opencv, run the Python steps with a venv that has them, e.g. `~/.venvs/media/bin/python`.)

## Rules (each one bit the smoke test or comes from the reference)

- Captions are PHRASES that cut, not karaoke: no per-word highlight, no box, no punctuation, lowercase.
- The screen goes BEHIND the head (what the reference does): the
  matte venv (`bash $S/scripts/setup_matte.sh`) is required; without it the build warns and the panels cover the speaker. Matting
  costs ~1.4 s per matted frame (BiRefNet-portrait, MPS): 11 min for 15 s of panels, cached after that;
  `"matte": {"stride": 2}` roughly halves it.
- The speaker moves only when the eyes would hide under the band; never more than the band height minus 60 px. List
  back-to-back panels in time order (the later one is drawn on top).
- Step and CTA labels go under the chin, above the caption; the build pushes both down when the face sits low and warns
  when even that covers the chin.
- Diagram captions turn black by the group's midpoint (a word that starts while the white frame fades in was white on
  white in the first build).
- Screen recordings of web pages: Google Chrome, not Playwright's Chromium (no H.264: every video tile recorded black).
- Screen recordings can show private material (other people's work, a private gallery): check every recording before
  publishing a render.

## Worked example

`example/reel.json` with `example/script.txt`: an English tutorial, "3 settings that make a notes app faster", cut from
a ~66 s seated recording into five takes (33 s): the hook card, one diagram, four panels (two back to back), an
aside, three step labels and the CTA, with `single`, `top`, `emphasis` and `strobe` captions and a punch-in close-up.
Icons are Fluent emoji from library/emoji, so no logo files are needed. It is for reading and copying: the recording
(`assets/talk.mp4` from prep.sh) and the screen recordings `rec/rec1.mp4`-`rec/rec3.mp4` are yours to supply.
script.txt holds the lines each take assumes with their source seconds; re-time `takes`, `captions` and every beat
`at`/`to` from your own transcript (`transcribe.py ... --lang en`). A dry run (test-pattern video, a tone for the
voice, word times synthesised from script.txt, panels in front instead of behind) builds and lints with 0 errors; it has
not been rendered with real footage.
