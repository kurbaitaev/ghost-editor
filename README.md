# ghost-editor

**An AI video editor that lives inside your coding agent.**
Send it a raw video of yourself talking to camera. Get back a finished reel for Instagram, TikTok or YouTube Shorts.

## Paid editor vs ghost-editor

Same raw recording. On the left, the edit I paid a human editor for. On the right, ghost-editor after seeing that edit once.

https://github.com/user-attachments/assets/312f6910-a8a0-4424-9dd4-612cd079a2e7

## What it does for you

- **Cuts the mess.** Keeps your best take of each sentence and removes the pauses and false starts.
- **Adds captions** timed to every word, placed so they never cover your face or the app's buttons.
- **Adds motion graphics**: numbers, cards and animated text that pop up right as you say them.
- **Adds B-roll that fits**: each shot shows what you're saying at that moment, sits in a frame so your face stays on screen, and is colour-matched to your footage. Your own clips come first.
- **Adds sound effects and music**, mixed so your voice always stays clear.
- **Checks its own work** before handing you the video, and fixes what it can.

## New in v0.3

**Two new named styles**
- **Seoul list**: a voice-over list over fast B-roll ("5 things that surprised me in Lisbon"). One big word per line in an italic serif or a heavy grotesk, white collage pages, phone stickers, an iMessage-style ending. No talking head needed.
- **stan style**: a seated tool tutorial. Your screen recordings fill the top of the frame *behind* your head, with small captions on your chest, a hook card, a diagram that draws itself, «[Step 1]» labels and a "comment the word" ending.

**B-roll that behaves**
- Every B-roll shot is checked against the words under it. A shot that doesn't show the line is flagged before the render, and fewer, better shots win over many loose ones.
- **Your people rules.** If your channel has rules about who or what may appear in B-roll (for example no women, no children, no flags or religious symbols), write them once in `people-rules.json`. Every stock clip, stock image and backdrop is checked against them, and you see a pick sheet before anything renders. The rules are empty by default; nothing is assumed.
- **Your own footage first.** It indexes your Photos library and footage folders, finds clips for a line, and face-checks them so only you appear. You confirm the frames before the render.
- **Your face stays as shot.** B-roll is colour-matched to you, never the other way round.
- **A new look every reel.** Each named style keeps its house look (type, captions, colours) but tracks the scenes, props and transitions it used, so the next reel doesn't repeat them.

**Everything else since v0.2**
- **Six new caption looks**: big punchy words, a karaoke colour sweep, a hand-drawn highlighter on the key word, a calm lyrics view, and more.
- **Moving type**: a hook that fills the screen in the first second, words spinning on a drum, text that scrambles into place, cards that pile up, headlines with a brush stroke, letters that bounce in.
- **Animated backgrounds and textures**, **animated emoji** next to your head, **smooth transitions** used sparingly, and **film looks** (Portra, Vision3, CineStill and more) with real film grain, only when you ask for them.
- **Words behind you** and **cut-out effects**: swap or blur the place behind you, black-and-white world with you in colour, a spotlight, a sticker freeze, a neon outline, three of you, your head breaking out of a phone frame, and covers for Reels and YouTube.
- **You approve before it renders**: a page with a frame at every cut and every graphic. Then it checks the finished video (pauses, sound levels, captions too small or low-contrast, B-roll budgets, anything covering a face) and fixes what it can, at most three times.
- **It remembers your corrections** ("fewer zooms", "no whoosh") and applies them next time.
- **Cleaner sound tools**: better pause detection on noisy recordings, a fix for thin phone-call voices, and lip sync that stays exact across every cut.

## All the styles

**Seven presets.** One word in the request:

| style | feels like |
|---|---|
| `clean` | bold captions, quick zooms, nothing distracting |
| `editorial` | soft lowercase captions and full-screen stats, like a news explainer |
| `meme` | emoji, reactions and punchy sounds |
| `cinematic` | film look, black-and-white B-roll, elegant type |
| `launch` | app windows and phone chats, made for product launches |
| `kinetic` | big words flying across the screen, you in a small circle |
| `pop` | giant words behind you, bright colour blocks |

**Six named styles.** Each is a full recipe in `recipes/` with its own guide:

| style | ask for it | what it is |
|---|---|---|
| **Clean OS** | *"edit this in Clean OS"* | An Apple-ad talking head that lives inside your phone: calm word cards that sharpen out of a blur, wide and tight shots from one 4K camera, an iPhone scene for each thing you name, a red Figma box that strikes out the words you reject. |
| **Vector explainer** | *"make an animated explainer"* | No camera needed. A narrator tells the story while one continuous illustration draws itself and the camera travels through it. |
| **RESULT** | *"edit this in RESULT style"* | A warm podcast-style edit: one or two words at a time, handwritten key words, navy cards with film dust, polaroids, a stop-motion paper stack, film-burn light leaks. |
| **POV montage** | *"cut these POV clips into a reel"* | Clips from smart glasses or a GoPro cut into a story: a flash-forward hook, speed-ups, text behind you, and a freeze frame on the moment that matters. |
| **Seoul list** | *"make a Seoul list"* | A voice-over list over fast B-roll with big serif words, collage pages and an iMessage ending. |
| **stan style** | *"edit this in stan style"* | A tool tutorial with your screen recordings behind your head, chest captions and step labels. Needs real screen recordings. |

The vector explainer:

https://github.com/user-attachments/assets/9d4208d6-a9eb-400f-8a8d-c3b1fbe5dfb9

**Or show it a reel you love.** It studies how that video was edited (the cuts, captions, animations and sounds) and edits yours the same way. Like the result? Ask it to save the look as your own style.

Everything the skill can do, in one page: [docs/PLAYBOOK.md](docs/PLAYBOOK.md).

## What you need

- **[Claude Code](https://claude.com/claude-code).** It needs a paid Claude plan (Pro, Max, Team) or API credits. ghost-editor itself is free.
- **A Mac with Apple silicon** (M1 or newer), what it is built and tested on, **or Windows 10/11** (run the shell steps from Git Bash; see [docs/INSTALL.md](docs/INSTALL.md#windows)). The caption check reads your finished video with macOS's built-in text recognition on a Mac and with tesseract on Windows. Linux and Intel Macs are untested.
- **Free tools** the install sets up for you: ffmpeg, Node, Python, Whisper, OpenCV. About 4 GB of disk for the speech model and the renderer's browser, plus up to about 6 GB more if you add the optional extras (the clean cut-out of your head, the noisy-audio tools, film looks).
- **A Gemini API key (free tier).** It powers the B-roll check (does each shot match its line, does it keep your people rules), finding your own footage by what's in it, copying a reel you show it, and AI-made stills. Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey); the free tier covers a reel. Without it the presets still work, but the B-roll check is skipped. The frames it checks are sent to Google.
- **An ElevenLabs key, only for the vector explainer's narrator.** Nothing else uses it.

**How long it takes** on an M3 MacBook Air with 16 GB (measured on the release test, 14 Oct 2026):

| step | time |
|---|---|
| one-time download of the sounds, music and emoji | about 3 min |
| transcribing a 30 s voice-over (Whisper turbo) | 25 s |
| rendering a 21 s reel in the `clean` preset | 41 s |
| checking that reel (render report, B-roll check with Gemini, caption check) | 1.5 min |
| Seoul list, 29 s: a snapshot of every beat to approve, then the render | 2.5 min + 2.5 min |
| Seoul list: sound check and B-roll check of 33 shots | 4 min + 4.5 min |
| stan style: cutting your head out over ~15 s of screen panels (BiRefNet) | 23 min, once (about 3 s a frame) |
| stan style, 33 s: the render | 1.5 min |

Our estimate from these numbers: a 60 s talking-head reel takes roughly 15 to 25 minutes of machine time from raw take
to checked video. Words behind you and stan-style panels add the slow cut-out (about 3 s per frame of the seconds
involved); cut-out effect beats use a faster model (about 0.5 s per frame). Claude's planning and your approval come on top.

## Get started

**1. Install.** Paste this into Claude Code:

> Install the ghost-editor skill: clone https://github.com/kurbaitaev/ghost-editor into ~/.claude/skills/ghost-editor and follow its docs/INSTALL.md.

It installs everything it needs, asks for your Gemini key, and tells you when it's ready. The sounds, music and emoji
take about 3 minutes to download; installing ffmpeg, Node and Whisper on a fresh Mac takes longer.

**2. Edit.** Start a new Claude Code session and say something like:

> Edit ~/Downloads/my-video.mov into a reel in the `pop` style.

> Make my video look like this reel: ~/Downloads/reel-i-love.mp4

> Make a Seoul list from my voice note ~/Downloads/lisbon.m4a and the clips in ~/Movies/Lisbon.

> Same video, but `cinematic`, and make it safe for TikTok.

## Questions

**Does it cost anything?** ghost-editor is free and open source (MIT). You need Claude Code, which needs a paid Claude plan. Everything renders on your computer. Gemini's free tier covers the B-roll checks for normal use; ElevenLabs is only for the narrated explainer.

**What videos work best?** Vertical phone videos of one person talking to camera, ideally 4K. Seoul list needs a voice-over and some clips; stan style needs screen recordings. It isn't made for landscape screen recordings on their own.

**Where do the sounds and music come from?** Mixkit's free library, downloaded to your computer during the install (nothing audio ships in this repo). Memes aren't included: add clips you have the rights to.

**Which languages?** Tested in English and Russian.

**Noisy outdoor recording?** It cleans the voice with DeepFilterNet (crickets, hum, wind), set to keep the voice natural.

**Can it make something new?** Yes. Ask for a new style or a new kind of animation and it writes one. Three of the seven presets and all six named styles were made that way.

**Other agents?** It's built and tested with Claude Code. Codex or another agent that can run shell commands can follow the same steps (see [INSTALL.md](docs/INSTALL.md)), untested.

## Under the hood

Whisper for transcription, OpenCV and MediaPipe for faces, Gemini for the B-roll checks, macOS Vision for the caption check, [HyperFrames](https://www.npmjs.com/package/hyperframes) for rendering, and royalty-free Mixkit sounds and music. Details: [HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md). Licences of everything bundled or downloaded: [docs/THIRD_PARTY](docs/THIRD_PARTY/README.md).

---

Built by [@kurbaitaev](https://x.com/kurbaitaev) on X. MIT licence.
