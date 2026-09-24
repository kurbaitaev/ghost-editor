# Sound and memes

## Why the old kit sounded bad (and what this skill does instead)

The upstream skill synthesized 7 sine blips in Python and set their volume
against a -27 LUFS phone voice, then lifted the finished mix ~10 dB into a
limiter. Measured: pops at -9 dBFS and the thud at -6 dBFS over voice peaks
of -13.5 dBFS, so every hit was louder than the voice and then squashed, and
the thud's 120 to 75 Hz sine is below what a phone speaker reproduces.

Here:
1. `prep.sh` normalizes the VOICE to -16 LUFS before anything is mixed.
2. Kit files are real recordings, trimmed and peak-normalized to -1 dBFS once
   (`sfx_fetch.py`, manifest in `library/sfx/manifest.json`).
3. `build.mjs` measures this recording's voice peak (p95 of 50 ms windows
   over kept words) and sets each hit relative to it by role:
   ui -14 dB, whoosh -12, impact -8, meme -3. The HyperFrames mixer is linear
   with no normalization by track count (tested), so the math holds.
4. Round-robin variants (pop-1/2/3, whoosh-1/2/3, impact-1/2) so a row of
   chips never machine-guns the same sample.
5. `qa.py` renders an SFX-only stem and prints every hit's real level vs the
   voice. Integrated loudness is left alone (never add gain after the mix).

## Density (what good editors do)

- 6 to 12 subtle sounds per minute (pops, whooshes on cards) and 1 to 3 meme
  sounds per minute. Never the same meme sound twice.
- Hormozi-style edits leave cuts dry; `snapSfx` is off by default for that
  reason. The old skill put a tap on every snap.
- Text slam = whoosh leading into an impact on the frame (the `big` default).
- A meme sound goes in air: after the punchline word, in the pause. Cut the
  take a little later to keep the pause if you have to.

## Kit (library/sfx)

Editing layer (Mixkit free licence, commercial OK): whoosh-1/2/3, whoosh-cine,
pop-1/2/3, click-1, tick-1, typing-1, impact-1/2, riser-1, ding-1, buzzer-1,
kaching-1, shutter-1.

Meme layer (YouTube rips via yt-dlp; fine on IG/TikTok, risky on YouTube
Content ID): vine-boom, bruh, record-scratch, xp-error, metal-pipe, fahhh,
oh-no, sad-violin, dun-dun, crowd-ooh, emotional-damage, huh-cat, rizz,
taco-bell, crickets, anime-wow, airhorn (use airhorn rarely, it is dated).

Entries with `"review"` in the manifest were disputed by an automated
listen; audition them (`audition.py --open`) before relying on them, then
delete the `review` key or replace the sound (`sfx_fetch.py --only <id>
--force` after editing its query in `KIT`).

## Memes (library/memes)

Each meme is `library/memes/<id>/` with `clip.webm` (VP9 + alpha + its own
Opus audio) or `image.png`, a `preview.png` over magenta, and `meta.json`
(`emotion`, `use_case`, `trigger_phrases`, `trend_status`, `sfx`, `source_url`).

Adding one:
```bash
yt-dlp "ytsearch5:<meme name> green screen" --flat-playlist --print "%(id)s %(duration)s %(title)s"
scripts/meme_add.py <id> https://youtu.be/<id> --tags "disbelief,sus" --use "when ..." \
  --triggers "trust me,supposedly" --trend hot [--in 1.2 --out 3.4] [--sfx vine-boom]
```
It keys green or blue automatically (corner-pixel check), crops to the
subject's alpha bounding box, scales to 360 px wide (x2 for sharpness) and
normalizes the audio. LOOK at preview.png: magenta must surround the
subject with no holes in the face; a fringe means raise `--similarity`.
A clip without a green screen (key none) renders framed like a still.
Stills: an image URL or file, `--crop w:h:x:y` to drop a caption band.

Picking: `meme_find.py "<the line>"` shortlists by tags, triggers and trend;
read the top three against the tone. Prefer `hot`. `trends.py` lists names
that are new on imgflip and Know Your Meme right now and marks what the
library already has; sourcing a new one is a human call.

Seeded library (2026-09-22): rock-eyebrow, doakes-stare (hot),
confused-nick-young, sad-hamster, john-cena-sure, chill-guy (hot),
aura-kid (hot), shocked-guy, surprised-pikachu (still).

Dead ends checked on 2026-09-22 (don't rebuild on them): Tenor API (shut
down 2026-06-30), Reddit anonymous JSON (403 since May 2026), myinstants and
101soundboards mp3s (Cloudflare 403 to scripts), Pixabay (no audio API),
GIPHY (100 calls/h, ToS forbids caching media). KLIPY is the live fallback
if a key is ever added.
