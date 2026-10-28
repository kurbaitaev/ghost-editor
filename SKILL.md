---
name: ghost-editor
description: AI video editor for talking-head reels. Turns a raw phone recording of someone talking to camera (retakes, pauses, false starts) into a finished vertical 1080x1920 reel for Instagram, TikTok or Shorts: best take of each sentence, pause trimming, word-timed captions that never cover the face and stay inside the platform safe area, motion scenes on the spoken word, sound effects and music mixed against the voice, B-roll that is framed, graded to the speaker's footage, matched to its line and checked against the user's own people rules, in seven presets (clean, editorial, meme, cinematic, launch, kinetic, pop). It can also reverse-engineer a reference edit the user likes and apply that style to their recording. Use when the user hands over a talking-head video and says "edit this", "make a reel", "make it look like this video", "add captions/motion graphics/sound effects", "pick the best takes", "remove the pauses", or asks for a re-cut. Also the named styles "Clean OS" (Apple-clean word cards + phone-UI scenes + a Figma selection box), the vector explainer (no footage, an ElevenLabs narrator, a world drawn live), RESULT (a warm podcast edit with paper, film and handwriting), the POV montage (first-person clips with freeze-frame moments), "Seoul list" (a voice-over list over fast B-roll with serif/grotesk word beats, white collage pages, phone-UI stickers and an iMessage outro) and "stan style" (a seated tool tutorial: screen recordings in the top band behind the speaker, small chest captions, a hook card, a diagram, [Step n] labels, a comment-keyword CTA); see recipes/ and docs/PLAYBOOK.md. Not for landscape screen recordings.
---

# ghost-editor

One recording in, one reel out. The creative work is choosing takes and
planning beats. The scripts do everything else the same way every time: cut
math, zoom tweens, captions, SFX levels, asset copying, QA. Nothing on
screen says anything the speaker did not say. A meme is a reaction, so it
lands ON or just AFTER the punchline, never before it.

Skill dir: `~/.claude/skills/ghost-editor` (below: `$S`). A reel project is any
directory (`$P`); `build.mjs` copies what it needs into `$P/assets` so the
project renders on its own.

## Pipeline

```
prep.sh        -> $P/assets/talk.mp4        1080x1920 30 fps, voice at -16 LUFS
transcribe.py  -> $P/build/words.whisper.json + take table (all takes)
face_track.py  -> $P/build/face.json          (captions and cards never cover the face)
choose takes   -> $P/reel.json takes        (references/take-selection.md)
plan beats     -> $P/reel.json beats/zoom   (references/reel-json.md; taste.py prompt first)
film_look.py / transitions.py reel           optional: graded plate, transition windows (after takes are final)
build.mjs      -> $P/index.html             + SFX table + rule and taste warnings
approval_sheet.py -> build/approval.html    lint, a frame at every cut and beat; WAIT for the user's yes
own_footage.py -> the user's own clips for the lines (face-checked: only them); `sheet` -> show the picked frames, WAIT for yes
insert_prep.py -> every B-roll insert: people + line check, cut, SDR, fps conform, graded onto the speaker's plate as shot (never the reverse)
components.py plan/check -> new components per reel for a named style (catalog.json); record after the user's yes
broll_vision.py picks -> build/broll-picks.jpg: every B-roll shot + stock image, its line, the people check; WAIT for the user's yes
render         -> $P/build/reel.mp4
render_report.py  -> pass/fail per check + fixes (runs broll_qa.py too); fix and re-render, at most 3 rounds
qa.py          -> SFX-vs-voice on a stem, A/V lengths, contact sheet
deliver        -> ~/Desktop/<name>-reel.mp4  taste.py log-reel; save_style.py if the user loved it
```

### 0. Check the toolchain once per session
`bash $S/scripts/doctor.sh`: tools, GEMINI_API_KEY and the media library,
each with its fix. On Windows run the `.sh` steps from Git Bash and read `python3` below as `python`
(docs/INSTALL.md "Windows"); the caption check uses tesseract there instead of macOS Vision. The B-roll people and line check (`broll_vision.py`, `broll_qa.py`) needs GEMINI_API_KEY (the free
tier is enough); without it those checks warn or fail as unchecked. On a fresh machine run `python3 $S/scripts/library_restore.py`
first (SFX, memes, music and the animated emoji aren't in git). Say what is missing; don't
improvise around it. Lines marked `opt` are optional tools with their own `scripts/setup_<x>.sh`
(BiRefNet matte, audio QA, film-look LUTs, caption metrics); the core works without them.

### 1. Prep and look
```bash
bash $S/scripts/prep.sh <IMG_xxxx.MOV> $P
ffmpeg -v error -i $P/assets/talk.mp4 -vf "fps=1/10,scale=216:384,tile=6x3" -frames:v 1 -update 1 $P/build/sheet.jpg
```
Look at the sheet. Check that it is the right person (show the frames
and confirm with the user when there is any doubt). Note where the face
sits (the zoom origin, default `50% 29%`), where the chin is (the card band
starts at y 990), and how bright the wall is.

### 2. Transcribe everything
```bash
python3 $S/scripts/transcribe.py $P/assets/talk.mp4 --out $P/build/words.whisper.json --lang en
```
The table is the take map in original seconds; `*` marks restart phrases
("okay, again"). Fix mangled names later in `captions.fixes`.

### 2b. Track the face
```bash
python3 $S/scripts/face_track.py $P/assets/talk.mp4 --out $P/build/face.json
```
Always. The build places captions, cards and reactions around the face, inside the platform's safe area.

### 2c. Noisy outdoor audio?
Crickets, hum, wind, traffic: `bash $S/scripts/denoise.sh $P/assets/talk.mp4 $P/build/voice-clean.wav` (DeepFilterNet3,
capped at 20 dB; full strength makes the voice thin and watery). Use the clean track for the cut and the captions.
Band-limited voice (Bluetooth mic, a call, a downloaded clip): `voice_enhance.py IN OUT.wav --mode superres` (ClearerVoice;
does nothing on full-band phone audio). Speech islands on noisy raw audio: `vad_pauses.py` / `autocut.py --vad` (silero-vad).
Both run in the audio QA venv (`bash $S/scripts/setup_audioqa.sh` prints its python).

### 3. Choose takes (`references/take-selection.md`)
Ask for the script if there is one. Pick the take of each sentence that is
fluent and later, keep one-breath runs as one take, and cut on WORD times:
`a` = first word - 0.10..0.15, `b` = last word + 0.20..0.30. When a meme
will follow a line, end that take 0.6 to 1 s after the last word so the
meme sound has air. Aim for 45 to 75 s.

**Audit the rough cut before building.** Whisper merges restarts and false starts into one clean sentence and smears
timestamps across them ("And even the… and even the thing that…"). Render the rough cut, re-transcribe THAT voice, and ask
Gemini 2.5 Pro (analyze_video) for a verbatim audit: repeats, fillers, clipped words, breaths, look-aways. A long stretch of voice
with few words in the transcript is a hidden retake. A throat-clear ("khm") shows up in a pitch scan as a short voiced hum with
falling pitch; Gemini's sub-second timestamps are not reliable enough to cut on. Leave ~0.2 s of breath between sentences.

### 3b. A single clean take?
If the recording is already one good take, don't pick takes by hand:
`python3 $S/scripts/autocut.py $P/assets/talk.mp4 --noise -30` prints `takes` with the pauses removed.

### 4. Pick a style, plan beats (`references/styles.md`, `references/reel-json.md`)
Seven presets: `clean`, `editorial`, `meme`, `cinematic`, `launch`, `kinetic`, `pop`.
**Recipes** (custom builds, not reel.json presets; each has its own README, SYSTEM.md and scripts). Follow the README end to end:
- `recipes/clean-os/`, **Clean OS**: Apple-clean word cards, wide/tight from one 4K camera, literal phone-UI scenes
  (date picker, lock-screen notifications, search + stalled loading bar, Photos memory), a red Figma selection box with a cursor.
  Call: "Clean OS". Talking heads, reflective or explanatory.
- `recipes/explainer-vector/`, **Vector explainer**: no footage; an ElevenLabs narrator; one continuous SVG world a camera travels
  through, a subject that draws itself, serif headlines, word-reveal captions. Call: "animated explainer", "like the tree video".
- `recipes/result-podcast/`, **RESULT**: warm podcast edit: one or two Inter Tight words with a two-tier emphasis, Caveat handwriting,
  navy dust cards, polaroids, a stop-motion paper stack, film-burn leaks, comic props, dissolves between lines.
  Call: "RESULT style".
- `recipes/pov-montage/`, **POV montage**: several first-person clips cut into a story with an edit list (speed-ups, freezes),
  the editorial motion layer, a freeze-frame moment with a meme. Call: "cut these POV clips".
- `recipes/seoul-list/`, **Seoul list** (a format, not a footage source: the footage the user hands over first, then their
  library, then stock or AI full screen; one world conformed to the main footage as shot, no posed stock models, the
  people rules): a voice-over list of observations
  over 1.4 s B-roll shots (no talking head); one big
  word per line in Playfair Display Italic (mood, places) or Inter Tight 800 (facts) with a subline, white word flashes,
  white collage pages (shot shrinks into a card, red glitch word, photo card, Fluent stickers), triptychs, an Instagram
  comment card, a macOS frosted window swapping cut-outs, blue highlight words, an iMessage outro. Built from list.json +
  proxies + the VO (build.mjs). Call: "Seoul list", "a list reel over B-roll". Read its SYSTEM.md first.
- `recipes/stan-style/`, **stan style** (NEEDS real screen recordings of the tool; without them say so and propose Clean OS
  or RESULT): a seated talking-head tool tutorial on the core pipeline (reel.json beats from
  `scripts/lib/stan.mjs`): `panel` (a screen recording in the top band, behind the speaker's BiRefNet cut-out; the speaker moves down only
  as far as their eyes need, once per run of panels), `chest` captions (small lowercase phrases at 68 % that cut on their first word; single
  words in the hook and the diagram, forehead words near the end), a `hook` card (icon rows + black-on-white strip title),
  one white `diagram` with drawn-on lines entered by a zoom-blur, `step` and `cta` labels under the chin, `aside`.
  Call: "stan style", "tool tutorial". Read its SYSTEM.md first.
The visual inventory of every style (playing loops, soundboard, rules) is docs/PLAYBOOK.md.
**Check the style's prerequisite before planning** (references/broll.md section 6): stan style needs real screen
recordings, cinematic needs one consistent world of footage. If it is missing, say what is missing and propose another
style; never fill the gap with stock. Seoul list has no footage prerequisite: it is a format (its README
"Footage").
Ask the user which one (show `examples/gallery/` or the showcase video) or pick by
the speaker's energy. Start from `examples/gallery/<style>.reel.json`.
To match a reference edit: `python3 $S/scripts/reference_study.py <their-edit.mp4> --out <dir> [--raw <raw>]`
writes a 1 fps contact sheet, full-res frames every 2 s and Gemini 2.5 Pro's
second-by-second edit log with a mapping onto our beats. Treat the log as a
draft: verify type, sizes and framing against the frames. Then map every scene
to a word time. Start from the closest file in `examples/`.
Walk the transcript sentence by sentence. For each one, ask what the speaker
just made the viewer imagine, and show it on the word. Leave some sentences bare;
silence in the band makes the next card land.
**B-roll (references/broll.md; broll_qa.py fails the render past these):**
- **Hard rules (references/broll.md section 0):**
  - The B-roll people rules in `people-rules.json` (empty by default; the user sets what their channel needs, e.g.
    exclude women, children or symbols; `people-rules.example.json`). `insert_prep.py` refuses a shot that breaks one,
    `broll_vision.py picks` shows the user every shot before the render (WAIT for their yes), and `broll_qa.py` fails
    the render (`people`). Ask the user once whether they have rules; never invent any.
  - The speaker's face keeps its as-shot colour: never a house grade or filter on the plate. Inserts are conformed to it.
  - Fewer B-rolls (talking heads <= 3 a minute), and each one shows the line it sits on (`match`). Stock images in a
    frame, card or collage are welcome and beat several video cutaways.
- Sources in order:
  1. The user's own footage, found by `own_footage.py` in their Photos library and footage folders and face-checked so
     only they appear. Before the render, show them `own_footage.py sheet` and wait for their yes.
  2. Stills in one frame language: AI stills or stock images (polaroid, card, collage page).
  3. Stock video last, and only inside a frame (polaroid, phone, card): never full screen when anything else fits, never for
     a list. broll_qa.py fails full-screen stock. Exception: B-roll-led formats (Seoul list, POV montage) are
     full-screen B-roll by design. There stock or AI may fill the screen, but one graded world, no posed stock models,
     the reference pace and 1080p are checked instead.
- One fixed house look per style (`recipes/<style>/house.json`, the SYSTEM.md "House look" sections): type, captions,
  accents and insert framing stay, and the speaker's face as shot. Never a grade on the face: `house_look.py apply` is
  retired and broll_qa.py `as_shot` fails a regraded plate.
- **New components every reel** (so reels in one style don't look the same every time): phone-UI scenes, paper props, polaroid / card / collage treatments, transitions, hook and
  outro devices. Before planning a named-style reel run `components.py plan --style <s>` (what the last 7 reels used
  and what is free) and fill each slot with something unused; register new ones with `components.py add` (with a sig);
  `components.py check` / broll_qa.py `components` warn on a repeat; after the user's yes `components.py record`.
- One character per idea. One shot per idea: a spoken list becomes typography, never three 0.5 s clips.
- Frame inserts (PiP, polaroid, split) so the face stays on screen; full screen is for the turn.
- Talking heads: full-screen B-roll <= 25 %, the speaker's face on screen >= 65 %, <= 3 inserts per minute.
- Every insert goes through `insert_prep.py --ref <plate as shot> --line "<the words under it>"`, which refuses a shot
  that breaks the people rules or doesn't show the line, and grades the insert onto the speaker's plate.
- Small glances stay on screen. Cover only real look-aways (> 0.5 s or > 12 deg; `cover_windows.py` labels them),
  cheapest first: trim, tight-crop punch, hold the current graphic, framed insert, full-screen stock last. Memes: 1 to 3 per minute, on
punchlines, from the library:
```bash
python3 $S/scripts/meme_find.py "the line with the punchline"
python3 $S/scripts/meme_find.py --list
```
If the library has nothing that fits, say so and offer to add one (step 9).
Don't force a meme.

Read the taste first: `python3 $S/scripts/taste.py prompt --style <style>` lists every correction the user has made across
reels ("you said") and the rules the skill learned ("skill rule"). The build fills its defaults and warns on the rest; plan with them.

**v0.3 building blocks** (all in references/reel-json.md; restraint still rules: one or two per minute each):
- Caption templates: `captions.style` = `hype`, `explosive`, `line-focus`, `neo-minimal`, `karaoke-fill`, `highlighter`
  (one keyword per phrase: heuristic, `keywords`, or `ai: true`).
- Kinetic type: `textfx` beats `hook` (the first 1.5-3 s), `drum` (lists, "round and round"), `scramble`, `flipstack`, `headline`
  (+ `swap` for "not X -> Y"), `spring` (section titles). Give each a `to`; the build warns on a short reading hold.
- Shader backgrounds on any scene (`bg: {"look": "ink-warp"}`), the `word` scene, `look.shader` film-grain/halftone overlays.
- Emoji beats pop an animated Fluent emoji when the glyph or `name` is in `library/emoji` (size <= 280).
- `transitions` at take changes (`transitions.py reel $P`; hard cuts stay the default, at most 2 punchy ones per reel).
- `look.film` film stocks baked into the plate (`film_look.py apply ... --look vision3_500t`; check one `still` first).
- `matte: true` + `behind` beats: BiRefNet cut-out, only for the behind seconds (~4-5 min per word); `front: true` puts the
  word over the speaker, `through: true` slides it through the head (behind on one side, in front on the other).
- `cutout` beats (scripts/cutout_fx.py, BiRefNet in the matte venv; references/cutout-fx.md): bg-swap (new place, light wrap
  + colour match), bg-blur (portrait mode), selective colour, spotlight, sticker (die-cut freeze that pops and wiggles),
  neon outline, clones (three time-offset copies), pop (head breaks out of a phone frame). One alpha pass per beat, cached;
  lite@1024 by default (~0.53 s/frame on the M3 Air, ~1 min per 2.5 s beat; portrait@1024 is ~4x slower for the same look
  at reel size). Inside ONE take; the window is frame-exact against the take and eases back into it. Reel-wide:
  `look.cutout`. Covers: `cover` -> build/cover-9x16.jpg + cover-16x9.jpg on the approval sheet. At most 2 cutout beats per reel.

### 5. Build
```bash
node $S/scripts/build.mjs $P
```
Read its output: the edit timeline (a missing word means a cut inside it),
the caption text, the SFX table (time, sound, role, volume, why) and the
WARNINGS. Fix every warning in reel.json or explain why it stays.

### 6. The approval gate (before the slow render)
```bash
python3 $S/scripts/approval_sheet.py $P [--upstream <cut list of a pre-cut source>] --open
```
It rebuilds, lints (0 errors required; sub-composition/track-density warnings are fine), runs the taste checks and
snapshots the first frame, 1.5 s, just after every visible cut, each beat as it lands and fully built, and the end, into
one page (build/approval.html: contact sheet, timeline, takes, beats, captions, SFX, warnings). Look at it yourself first
and fix what is wrong (cards on the chin, text wrapping, a meme clipped by the edge, captions colliding with a card, a wrong
person). Then send the user the page and WAIT: they flag frames and paste a change list, or approve. After their yes:
`approval_sheet.py $P --mark-approved`. For a quick look without the page: `npx hyperframes lint` and
`npx hyperframes snapshot --at <edit seconds>` (edit seconds = the take's edit start + (original t - take a)).

### 7. Render, report, fix (at most 3 rounds)
```bash
npx hyperframes render -o build/reel.mp4 --quiet
python3 $S/scripts/render_report.py $P build/reel.mp4   # build/render-report.json + .html, exit 1 on a failure
python3 $S/scripts/qa.py $P build/reel.mp4              # SFX stem levels, A/V lengths, matte, transitions, shader flicker
```
The report checks streams, duration, A/V alignment, loudness, black frames, a frozen speaker, silences inside the speech
(mapped to the take), caption safe area, the first 1.5 s and the SFX levels, each failure with a fix. It also runs
`broll_qa.py` (the B-roll and motion checks). Run that on its own for custom builds without reel.json:
`python3 $S/scripts/broll_qa.py build/reel.mp4 --project $P [--profile talking-head|broll-led|graphics]`.
- budgets: full-screen B-roll, face on screen, inserts per minute;
- insert grade vs the plate;
- graphic scenes: length and motion;
- captions: >= 48 px and >= 3:1 contrast, via OCR;
- nothing over a face;
- frozen frames, HDR output, plate keyframes. PASS: deliver and
mention the warnings. FAIL in round 1 or 2: apply the "agent can apply" fixes to reel.json (never gain on the mix, never
hand-tuned data-volume), rebuild, lint, snapshot the changed times, re-render, report again. FAIL in round 3: stop and send
the user render-report.html. A visual change they have not seen goes back through the approval sheet first.

QA renders an SFX-only stem and prints each hit's peak against the voice
and its role target. Targets: ui ≈ -14, whoosh -12, impact -8, meme -3 dB
vs voice p95 peak; flags anything louder than the voice or inaudible. It
also checks loudness (-16 ±1.5 LUFS, TP ≤ -0.5), silences > 0.8 s inside
the speech, and writes `build/contact.jpg`. It never adds gain.

### 8. Deliver
Copy to `~/Desktop/<name>-reel.mp4` (plus a 720p preview under 30 MB if
asked). Handover: the takes chosen (original seconds and why), the beats and
memes in plain words, the SFX count per minute, anything QA flagged, and the
obvious follow-ups (music from the platform's library at post time, a
different meme, the URL for the end card). Then `python3 $S/scripts/taste.py log-reel $P --verdict shipped`; if the user
loved the look, offer `python3 $S/scripts/save_style.py $P <name> --best-for "..."`.

### 9. Library work
```bash
python3 $S/scripts/trends.py                 # what's new on imgflip / Know Your Meme, what we lack
python3 $S/scripts/meme_add.py <id> <url|file> --tags ... --use ... --triggers ... --trend hot
python3 $S/scripts/sfx_fetch.py --only <id> --force   # after editing KIT in sfx_fetch.py
python3 $S/scripts/audition.py --open         # soundboard + meme wall for a human listen
```
Always look at a new meme's `preview.png` before using it. Sounds with a
`review` flag in the manifest have not been confirmed by ear.
`references/sound-and-memes.md` has the mixing reasoning, sources, licences
and the dead ends not to retry. Animated emoji: `python3 -I $S/scripts/emoji_fetch.py` (library/emoji, Fluent, MIT).

### 10. Every correction is taste
When the user corrects an edit decision ("too many zooms", "that sound is cheesy"), fix the reel AND record it in their words:
`python3 $S/scripts/taste.py add "<what they said>" [--metric punch_ins --max 2 | --set captions.size=50 | --ban-sfx riser-1] --reel <project>`.
Only the user's own feedback is `from: user` (quoted "you said"); a rule you learned yourself is `--from skill`. `taste.py list`,
`forget <id>`, `restore <id>`, `tag <id> user|skill`. Taste is a prior: reel.json always wins.

## Rules that came from getting it wrong

- B-roll is the user's world, framed and graded, or nothing (an audit of 29 reels; references/broll.md).
  Reels went wrong in these ways:
  - forced covers on every glance (one reel: 31 windows, speaker on screen 33 %);
  - full-screen stock strangers 15-44 b* colder than the plate;
  - one 0.5 s clip per noun;
  - static graphic scenes;
  - small, low-contrast captions on a light hoodie;
  - panels opening over the speaker's face;
  - stan without screen recordings, and a Seoul list filled with unrelated posed stock models in three light worlds.
  The UI animation was fine; what went on screen, and how often, was not.
- One reel at a time through approval_sheet.py; never batch-render a wave of styles without a sheet per reel (7 styles
  rendered from one template in 7 minutes came out with 0-2 approval files).

- The speaker's plate must cover the whole reel: a talking-head clip that ends at the voice's length leaves the reel's
  tail (music fade, 0.3-0.5 s) black, which flashes at Instagram's loop point. Give the plate a held
  last frame (`tpad=stop_mode=clone`) and run it to the end; check the last 0.4 s of every render.
- Run `hyperframes render` as a tracked background job, never `nohup ... &` from a tool shell: when the parent shell exits
  the render cancels itself (`render_cancelled_parent_exited`). Masters with animated grain can come out as 10-bit HEVC at
  ~50 Mbit/s: deliver H.264 8-bit capped near 12 Mbit/s.
- A style is a SYSTEM, not a template. When breaking down a reference, write the invariants (what makes it the style),
  the house look (`house.json`: what stays fixed reel to reel), the content slots (what follows the script), a
  generator per slot, and a catalog of used components (`catalog.json`, read and written by `scripts/components.py`;
  see recipes/clean-os/SYSTEM.md section 5).
  - The default is one fixed house look per style, with small variation per reel.
  - Pasting the previous reel's scenes where the script doesn't call for them still reads as "the same edit".
  - Reusing the house's look is the point.

- Transcribe the whole recording; choose takes from the table, never by scrubbing.
- Cut on word times, never whisper segment times.
- Snap zooms, not crossfades, between takes of the same sentence.
- Voice loudness is fixed in prep, before SFX. Never lift the finished mix.
- SFX level is relative to this voice (build measures it). Never hand-tune `data-volume`.
- A meme sound never sits on top of a word. Give it a pause.
- No meme sound twice in one reel. Meme sounds: 1 to 3 per minute.
- One card in the band and one thing in the reaction slot at a time.
- No em dashes in on-screen text.
- Meme sounds and green-screen clips from the internet are usually other people's media: the user adds them at their
  own risk (fine for many IG and TikTok reactions, not for YouTube Content ID). Say so if the user mentions YouTube.

- Shoot or prefer 4K: one camera gives a wide and a tight shot with no upscaling. No 720p B-roll; on Mixkit only clips offered
  in 2160p carry the free commercial licence. Your own unused frames are often the best B-roll.
- HyperFrames: anything tweened more than once gets `fromTo` with explicit values (a bare `to()` locks a stale start value
  depending on the renderer's seek order). Grow SVG shapes with `attr`, not scale transforms. Every `<video>` needs an id.
  Lint, then snapshot every beat and look at it, before every render.
- Light accent colours (lime, yellow) need dark text on pills and tags: `brand.onAccent`.
- Music ducks under every spoken line (`music.duck`); under a freeze it nearly disappears. The QA SFX stem excludes the bed.
- Calibration (6 top reels): 113 of 119 transitions are hard cuts, median shot ~3 s, audible SFX 0.4-0.9 per 10 s on graphics
  (not on cuts), B-roll 20-35 % of runtime. Default to restraint.
- Hide jump cuts with short dissolves (0.2 s) or a shot-size change, not a zoom on every cut; the user found per-cut zooms annoying
  (at most three comic punch-ins per reel). Before cutting, build an attempt log of the WHOLE raw take with Gemini 2.5 Pro.
- Hide each caption with an explicit `fromTo` placed after its fade-in; a bare `set` inside the fade gets overridden.
- The person matte rebuilds itself when talk.mp4 or the behind beats change (signature in assets/talk-matte.json). On the u2net
  fallback (no matte venv), delete assets/talk-matte.webm after a re-cut or old cut-outs float over the new footage.
- Cutting picture and voice separately (Clean OS, POV montage): snap every segment to the frame grid and cut both at the same
  snapped times; otherwise each piece rounds to whole frames and the voice drifts early (43-54 ms by the end of a 23-piece cut).
  `qa.py --av-only` checks lengths; `tests/test_assemble_sync.py` is the regression test.
- HyperFrames clip times for footage (takes, holds, matte, transition and cutout windows) are frame counts / fps TRUNCATED
  to 6 decimals (`fgrid` in build.mjs), never rounded: the renderer snaps a start only within 0.001 frame and samples a
  video at floor((t - start) x fps), so `0.067` for 2/30 shows the clip a frame late and `0.066667` repeats its first frame.
  An ffmpeg window cut to match (cutout_fx.py) takes `-ss` as the exact frame time to 6 decimals and `-t` half a frame short.
- Per-letter or per-shader motion is a pure function of the timeline time (painters, the hf-seek event), never rAF or a
  chain of tweens. Animated emoji are WebM `<video>`, never APNG `<img>` (APNG animates on the wall clock).
- APIs: ElevenLabs through the direct key in .env (the MCP connector's grant budget runs out); Gemini 2.5 Pro for long video
  (Flash truncates), key checked with one call first; yt-dlp >= 2026.08.19 for YouTube; never pass Instagram cookies.

## Files

- `scripts/prep.sh` transcode + voice loudnorm
- `scripts/transcribe.py` whisper (PATH) → words json + take table
- `scripts/build.mjs` reel.json → HyperFrames index.html, SFX mixing and rules
- `scripts/qa.py` render QA with SFX stem level check, A/V lengths (`--av-only`), matte, transitions, shader flicker
- `scripts/broll_qa.py` B-roll and motion QA (budgets, grade, graphics motion, captions via `ocr_text.js` / macOS Vision,
  faces covered, stock inside a frame, own footage only the speaker, no posed stock models, people rules and line match
  (`broll_vision.py`, Gemini), the speaker's face as shot, 1080p sources, one world and shot pace for B-roll-led styles, freezes,
  HDR, keyframes); `scripts/broll_vision.py` the people / line check and the pick sheet;
  `scripts/own_footage.py` the user's own footage (index + Gemini tags, face check, confirmation sheet; library/me/ stays local);
  `people-rules.json` the configurable B-roll people rules (empty by default; `people-rules.example.json`);
  `recipes/<style>/house.json` the fixed house look per style (`scripts/house_look.py` measures; never applied to the face); `scripts/insert_prep.py` + `scripts/grade_lib.py` insert cut + SDR + fps +
  grade conform; `scripts/cover_windows.py` / `plan_cut.py` keep-or-cover verdict per off-lens window; `references/broll.md`
- `scripts/sfx_fetch.py` build/refresh the SFX kit (Mixkit), normalized, manifest
- `scripts/meme_add.py` add a meme clip/still (key, crop, alpha WebM, preview)
- `scripts/meme_find.py` shortlist memes and meme sounds for a line
- `scripts/trends.py` trending meme names not yet in the library
- `scripts/audition.py` HTML soundboard + meme wall
- `scripts/doctor.sh` checks tools, key and library, with fixes
- `scripts/reference_study.py` reverse-engineer a reference edit (sheet, frames, Gemini edit log)
- `references/reference-study-prompt.md` the edit-log prompt (improve it here)
- `examples/` real reel.json files from shipped reels (English): one per preset in `examples/gallery/`, two motion edits
- `README.md` install, agent setup (Claude Code / Codex / any agent), quick start
- `scripts/lib/motion.mjs` scenes (card, stats, fly3d, image, sentence), scene transitions, editorial captions, music bed
- `scripts/autocut.py` pause-trimmed takes for a single clean take
- `scripts/broll_gen.py` AI still B-roll with Gemini (9:16), needs GEMINI_API_KEY
- `scripts/tts_elevenlabs.py` narrator voiceover with word timings (ElevenLabs, takes by seed)
- `scripts/denoise.sh` DeepFilterNet3 speech denoise, capped at 20 dB (sets up its own py3.11 venv)
- `recipes/<name>/` named styles beyond the presets (README + SYSTEM.md + scripts; an English worked example for the
  vector explainer, Seoul list and stan style)
- `docs/PLAYBOOK.md` every style, toolkit and rule in one place (the shareable inventory)
- `library/music/` licensed music beds + manifest
- `library/sfx/` kit + manifest.json; `library/memes/<id>/` clips + meta.json
- `templates/fonts/` Geist, Inter, Inter Tight, Playfair Display, Montserrat, Oswald, Unbounded, JetBrains Mono (OFL, latin + cyrillic woff2)
- `references/reel-json.md` the spec and beat types
- `references/take-selection.md` choosing takes (adapted from mariagorskikh/talking-head-reel, MIT)
- `references/sound-and-memes.md` mixing, sources, licences, dead ends
- `scripts/lib/caption-templates.mjs` (+ `metrics.json`, `ai-tag.mjs`) six caption templates; `scripts/font_metrics.py` regenerates the metrics
- `scripts/lib/stan.mjs` stan style blocks (panel, hook, diagram, step, cta, aside) and the chest captions
- `scripts/lib/kinetic.mjs` textfx blocks; `scripts/lib/shader-layer.mjs` + `templates/vendor/hf-paper.js` shader looks; `scripts/lib/emoji-pop.mjs` + `scripts/emoji_fetch.py` Fluent emoji
- `scripts/transitions.py`, `scripts/film_look.py`, `scripts/gen_luts.py` transitions and film stocks (LUTs in library/luts)
- `scripts/matte.py` BiRefNet person matte; `scripts/vad_pauses.py`, `scripts/voice_enhance.py` audio QA
- `scripts/cutout_fx.py` BiRefNet effects (cutout beats, look.cutout, covers, model demos on stills); `references/cutout-fx.md`;
  `tests/test_cutout_fx.py` (fake model, no GPU: every effect, the frame grid, release); `tests/test_decode_levels.py`
  (RGB decode matches the BT.709 spec, a decode -> Writer round trip keeps the levels)
- `scripts/approval_sheet.py`, `scripts/render_report.py`, `scripts/taste.py` (+ `lib/taste.mjs`, `taste.json`), `scripts/save_style.py` workflow
- `scripts/setup_{captions,looks,matte,audioqa}.sh` the optional venvs; `docs/THIRD_PARTY/` sources and licences per pack
