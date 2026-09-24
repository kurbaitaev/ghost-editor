# How ghost-editor works

The technical side, for developers and curious agents. For setup, see [INSTALL.md](INSTALL.md).

## The pipeline

1. **Prep.** The recording is scaled to 1080x1920 and the voice is levelled to -16 LUFS.
2. **Transcribe.** Whisper gives a timestamp for every word.
3. **Pick takes.** The agent keeps the best take of each sentence. On a single clean take it only trims the pauses.
4. **Track the face.** OpenCV's YuNet model follows the speaker's face through the video.
5. **Plan.** The agent writes `reel.json`: the takes, the style, and the beats (what appears on screen when).
6. **Build and render.** `build.mjs` turns `reel.json` into a [HyperFrames](https://www.npmjs.com/package/hyperframes) composition (HTML + GSAP rendered in headless Chrome).
7. **Check.** It lints and snapshots every beat before rendering. After rendering it checks loudness, true peak, each sound effect against the voice, and where every caption landed.

```bash
S=~/.claude/skills/ghost-editor; P=~/reels/my-reel
bash $S/scripts/prep.sh ~/Downloads/IMG_1234.MOV $P
python3 $S/scripts/transcribe.py $P/assets/talk.mp4 --out $P/build/words.whisper.json
python3 $S/scripts/face_track.py $P/assets/talk.mp4 --out $P/build/face.json
python3 $S/scripts/autocut.py $P/assets/talk.mp4 --noise -30
# the agent writes $P/reel.json: {"style": "launch", "takes": [...], "beats": [...]}
node $S/scripts/build.mjs $P
cd $P && npx hyperframes lint && npx hyperframes render -o build/reel.mp4
python3 $S/scripts/qa.py $P build/reel.mp4
```

## Styles

| style | looks like |
|---|---|
| `clean` | bold captions with the active word in an accent colour, snap zooms, nothing else |
| `editorial` | lowercase blur-in captions, tilted pill tags, full-screen data scenes over the voice |
| `meme` | outline captions, emoji and reactions beside the head, big number cards, punchy sounds |
| `cinematic` | film grade and grain, black-and-white B-roll, keywords in a glowing serif |
| `launch` | dark UI windows with typed prompts, phone chats, glitch cuts |
| `kinetic` | full-screen word-by-word type with a moving camera, the speaker in a round picture-in-picture |
| `pop` | giant words BEHIND the speaker (person cut-out), uppercase captions, colour blocks |

Each style is a preset in `styles/`. `references/styles.md` covers when to use each one and how to save a new one.

Motion scenes: cursor-click cards, glass stat badges, 3D word fly-throughs, kinetic sentences with a hand-drawn cross-out, typed prompts, phone chats, AI B-roll stills, text behind the speaker.

## Captions that stay off the face

Every caption block, card and reaction goes below the chin. If there's no room there it goes above the head, and if that's too tight it shrinks to fit. It always stays inside the platform's safe area (`instagram`, `tiktok`, `shorts`, `all`) and clear of the like and comment buttons. `build/caption_layout.json` records where each block landed.

## Sound

Sound effects are levelled against this speaker's measured voice, not guessed. Three density profiles (restrained, standard, rich) and a music bed per style keep the voice easy to follow.

## Copying a reference edit

```bash
python3 $S/scripts/reference_study.py ~/Downloads/their-edit.mp4 --out ~/reels/studies/their-edit [--raw ~/Downloads/raw.MOV]
```

It writes a contact sheet, full-resolution frames and a second-by-second edit log from Gemini 2.5 Pro, mapped onto this skill's beats. The agent checks the log against the frames before trusting it.

## What's in the repo

- `SKILL.md`: the workflow the agent follows, plus the rules learned from getting it wrong.
- `styles/`: the seven presets.
- `examples/gallery/`: one working `reel.json` per style.
- `scripts/`:
  - `build.mjs` (+ `lib/motion.mjs`, `lib/safezone.mjs`): `reel.json` → HyperFrames composition
  - `prep.sh`, `transcribe.py`, `autocut.py`, `face_track.py`
  - `qa.py`, `doctor.sh`
  - `reference_study.py`, `broll_gen.py`
  - `sfx_fetch.py`, `library_restore.py`, `audition.py`
  - `meme_add.py`, `meme_find.py`, `trends.py`: your own meme library
- `references/`: every `reel.json` field and beat type, styles, take selection, sound mixing.

## Licences

- Code: MIT.
- Sound effects and music: [Mixkit](https://mixkit.co/license/) (free, commercial use, no attribution). `library_restore.py` downloads them on your machine; none are stored in this repo.
- Fonts: SIL OFL.
- Face model (YuNet): MIT.
- No memes ship. Add clips you have the rights to with `scripts/meme_add.py`.

Take selection is adapted from [mariagorskikh/talking-head-reel](https://github.com/mariagorskikh/talking-head-reel) (MIT).
