# Playbook: every style, every building block, everything we learned

The one-page inventory of this skill. Each style says how to ask for it.

## Named styles (recipes)

| style | ask for it | what it is | best for |
|---|---|---|---|
| **Clean OS** | "edit this in Clean OS" | An Apple-ad talking head that lives inside your phone. 1–3 lowercase word cards resolving from blur (Inter), wide/tight cuts from one 4K camera, literal iOS scenes for what you say (date picker, lock-screen notifications, a search with a loading bar stuck at 97%, a Photos memory card), a red Figma selection box with a cursor, perspective text with a draining ring, one handwritten word (Great Vibes), a small sound on every graphic. | reflective or explanatory monologues |
| **Vector explainer** | "make an animated explainer" | No footage. One continuous SVG world a camera travels through, a subject that draws itself, serif headlines on panels, words that rise from blur as the narrator says them, an ElevenLabs narrator, a piano bed. | parables, life lessons, concepts you can draw |
| **POV montage** | "cut these POV clips into a reel" | Several first-person clips cut into a story: a flash-forward hook, speed-ups, text behind you, a cursor-click fact card, a freeze frame with a zoom, a record scratch and a meme, on the editorial motion layer. | trips, vlogs, a day from smart glasses or a GoPro |

Each lives in `recipes/<name>/` with a README (the full grammar and pipeline), its scripts and a worked example.

## Presets (one line in reel.json: `"style": "<name>"`)

| style | looks like | best for | sound · music |
|---|---|---|---|
| `clean` | bold mixed-case captions, one keyword colour, snap zooms | business advice | restrained · none |
| `editorial` | lowercase blur-in captions, tilted pill tags, highlight wipes, full-screen scenes | data, insight | standard · tense electronic |
| `meme` | outline captions, emoji and memes beside the head, chips and big cards | entertainment, hot takes | rich · quirky |
| `cinematic` | film grade, grain, vignette, B&W B-roll, glowing serif keywords | stories, founder journeys | restrained · ambient |
| `launch` | dark UI windows with typed prompts, phone chats, glitch cuts | product and AI launches | standard · upbeat electronic |
| `kinetic` | full-screen word-by-word type, speaker in a round window | hooks, quotes, manifestos | standard · percussive |
| `pop` | giant words behind the speaker, uppercase captions in hot colour boxes | personal brand, bold claims | standard · upbeat pop |

Or show it a reel you love: `scripts/reference_study.py` reverse-engineers it (Gemini 2.5 Pro edit log + frames) and the agent maps it onto your recording. A look you like can be saved as a new preset or recipe.

## Pipeline

0. `doctor.sh`: tools, keys, library, each with its fix.
1. `prep.sh`: 1080×1920, voice at −16 LUFS; a contact sheet; confirm the right person is on screen.
2. `denoise.sh` for outdoor takes (DeepFilterNet3, capped at 20 dB).
3. `transcribe.py` (every take, word times) and `face_track.py` (keeps captions off the face).
4. Choose the best complete take per line (or `autocut.py` for one clean take); re-transcribe the cut; Gemini 2.5 Pro verbatim audit.
5. Pick a preset or recipe; plan beats on spoken words.
6. `build.mjs`, lint, snapshot every beat, look.
7. Render; `qa.py`: loudness, true peak, each SFX against the voice, caption placement.

## Building blocks

- **Captions:** house (Arial bold 56, outline, lower third), pill, clean, editorial (lowercase blur-in, tags, highlight wipes), mini, word cards (Clean OS).
- **Card beats on the word:** big (claim slam, count-up), chips, strike, quote, list + stamp, emoji / logo / meme (reaction slot), behind (giant word behind you), title, broll, endcard.
- **Full-screen scenes:** card (pill + cursor click), stats (glass badges), fly3d (camera through 3D words), image (still B-roll), ui (typed prompt), device (phone chat), kinetic (word-by-word + round window), sentence (hero word lands).
- **Motion:** hard cuts by default; blur / expand / wipe / glitch only at section changes; snap zooms; slow pushes; wide ↔ tight; freeze frames.
- **Layout:** face-aware placement (below the chin, above the head, shrink; never on the eyes or mouth) inside the Instagram / TikTok / Shorts safe area, clear of the like column; one card and one reaction at a time.
- **Look:** grade, grain, vignette per style; person matte for text behind you; keep the footage's own mood.

## Sound

- **Effects:** UI (pop, click, tick, keyboard, notification, ding, shutter), whooshes and risers, impacts and booms, plus a private meme kit. The public edition ships only Mixkit sounds (free commercial licence).
- **Music beds (13, Mixkit):** calm (lo-fi-02, digital-clouds, silent-descent, vastness), tech (deep-techno-ambience, cyberpunk-city, infinity, brainiac), fun (comical, keeping-fit, happy-times, life-is-a-dream), rhythm (vocal-percussions).
- **Mixing:** the voice is levelled first; each SFX role sits a fixed dB under your measured voice peak; music ducks under speech (`music.duck`); final −14 to −16 LUFS, true peak ≤ −1 dB.
- **Voices:** ElevenLabs (`tts_elevenlabs.py`, e.g. Spuds Oxley for a wise elder), Kokoro as a free local fallback.

## Type (free, OFL, Latin + Cyrillic)

Inter (Clean OS), Great Vibes (script word), Montserrat (presets), Playfair Display (cinematic, explainer headlines), Geist and Geist Mono, JetBrains Mono (UI windows), Unbounded, Oswald. Arial Bold for house subtitles.

## What we learned (each rule came from a real mistake or a measurement)

**Cutting and takes**
- Transcribe everything and choose takes from the table; cut on word times, never segment times.
- Whisper merges restarts into one clean sentence and smears timestamps. Re-transcribe the cut voice and audit it with Gemini 2.5 Pro.
- A long stretch of voice with few transcript words is a hidden retake. A throat-clear is a short voiced hum with falling pitch (find it with a pitch scan).
- Leave ~0.2 s of breath between sentences. Confirm the right person on screen before rendering.

**Audio**
- Full-strength denoise leaves a thin, watery voice: cap at 20 dB and add a little warmth.
- Level the voice first; never add gain to the finished mix. The SFX check must exclude the music bed.

**Captions and layout**
- Never cover the face; stay inside the safe area. Light accents need dark text. Hide captions while a headline says the same words. No em dashes on screen; one emphasis mechanism per video.

**Motion and rendering (HyperFrames)**
- Anything tweened twice needs `fromTo` with explicit values. Grow SVG shapes with `attr`, not scale. Every video needs an id. Lint, snapshot every beat, look, then render.
- Top reels: 113 of 119 transitions are hard cuts, median shot ~3 s, B-roll 20–35 % of runtime, audible SFX 0.4–0.9 per 10 s on graphics, not cuts.

**Sound and memes**
- A small sound on every graphic, none on bare cuts. Never the same meme sound twice; 1–3 per minute; never on a word. Meme rips are for Instagram and TikTok only.

**Footage and B-roll**
- 4K vertical gives two shot sizes from one camera. No 720p B-roll; on Mixkit only clips offered in 2160p are free for commercial use. Your own unused frames make good B-roll.

**Tools**
- Search the HyperFrames registry (`npx hyperframes catalog --query`) before hand-building a look. Validate API keys with one call before a batch.
