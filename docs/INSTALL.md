# Installing ghost-editor

The easy way: paste this into [Claude Code](https://claude.com/claude-code):

> Install the ghost-editor skill: clone https://github.com/kurbaitaev/ghost-editor into ~/.claude/skills/ghost-editor and follow its docs/INSTALL.md.

Your agent does the rest and tells you if it needs anything from you.

---

## For the agent doing the install

Work through these steps in order. Tell the user in plain words what you're installing and why.

1. **Clone** (skip if already there):
   ```bash
   git clone https://github.com/kurbaitaev/ghost-editor ~/.claude/skills/ghost-editor
   ```
2. **Check what's missing:**
   ```bash
   bash ~/.claude/skills/ghost-editor/scripts/doctor.sh
   ```
   Every `MISS` line ends with the command that fixes it. Run those.
   - On a Mac they use Homebrew. If `brew` is missing, ask the user to install it from https://brew.sh first (it needs their password).
   - Install Python packages with `pip install` (or `pip3`). If pip refuses with "externally managed environment", use `pip install --user`, or ask the user whether they prefer a virtualenv.
3. **Download the sound effects, music and animated emoji** (free Mixkit licence and Microsoft's MIT Fluent emoji, ~60 MB):
   ```bash
   python3 ~/.claude/skills/ghost-editor/scripts/library_restore.py
   ```
4. **Run `doctor.sh` again** until it ends with `0 missing`. Lines marked `opt` are optional.
5. **Gemini key (recommended, free tier).** It runs the B-roll check (each shot matches its line and keeps the user's
   people rules), finds the user's own footage by what is in it, copies the look of a reel they show you, and makes AI
   B-roll stills. Without it the presets work and the B-roll check is skipped. Ask the user for one:
   - they get a free key at https://aistudio.google.com/apikey
   - `pip install google-genai pillow`
   - save it with `echo 'GEMINI_API_KEY=<key>' >> ~/.claude/skills/ghost-editor/.env` (the file is gitignored)
   - tell them the frames being checked are sent to Google.
   Then ask whether they have rules for who or what may appear in B-roll (for example no women, no children, no flags or
   religious symbols). If they do, write them into `people-rules.json` in the format of `people-rules.example.json`;
   if not, leave it empty. Never add rules they didn't ask for.
6. **ElevenLabs key (optional).** Only for the vector explainer's narrator. If the user wants it: a key from elevenlabs.io (Profile → API keys),
   saved as `ELEVENLABS_API_KEY=<key>` in the same `.env`. Noise removal (`scripts/denoise.sh`) needs no key; it sets itself up on first use
   (python3.11 + uv, about 1 GB).
7. **Optional extras (ask first; each is one command and sets up its own venv, weights go to `~/.cache`):**
   - `bash scripts/setup_looks.sh`: film-stock looks (generates the LUTs, ~1 GB venv, a minute).
   - `bash scripts/setup_matte.sh`: the clean person cut-out for words behind the speaker (~2.4 GB with the model).
   - `bash scripts/setup_audioqa.sh`: pause detection on noisy recordings and voice super-resolution (~1.9 GB).
   - `bash scripts/setup_captions.sh`: only to add a new font to the caption templates.
   Without them everything else works; `doctor.sh` lists them as `opt`.
8. **Tell the user it's ready**, and that they can now say, for example: "Edit ~/Downloads/my-video.mov into a reel."

Restart Claude Code (or start a new session) so the skill shows up.

---

## Windows

The core pipeline (prep, transcription, face track, build, approval sheet, render, QA) runs on Windows 10/11. Tested on
Windows 11 with an AMD GPU; the optional venvs (matte, audio QA, film looks) are set up the same way but have not been
exercised there. What is different:

- **Run the shell scripts from Git Bash** (comes with Git for Windows; `bash scripts/doctor.sh`). PowerShell and cmd
  are not supported for the `.sh` steps. Everything else is `python <script>` and `node <script>`.
- **`python`, not `python3`.** The Store alias `python3` on Windows is a stub. `doctor.sh` detects this and says so; in the
  commands of SKILL.md read `python3` as `python`. Install Python from python.org or `winget install Python.Python.3.12`.
- **ffmpeg**: `winget install Gyan.FFmpeg` (the *full* build: libvpx for the alpha WebM memes and libass). `prep.sh` picks a
  hardware H.264 encoder that works on the machine (NVIDIA NVENC, Intel QSV, AMD AMF) and falls back to libx264.
- **Node 18+**: `winget install OpenJS.NodeJS.LTS`. HyperFrames (the renderer) is fetched by `npx` on first use.
- **The caption check** (`broll_qa.py`: size and contrast of the captions in the render) uses macOS Vision on a Mac and
  **tesseract** elsewhere: `winget install UB-Mannheim.TesseractOCR`, then add `rus.traineddata` from
  [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) to its `tessdata` folder (or to any folder named in
  `GHOST_TESSDATA`). Without tesseract the caption check is skipped and the report says so.
- **Your own footage** (`own_footage.py`) looks in `~/Videos` and `~/Pictures` (no Photos library on Windows).
- **Cyrillic and other non-Latin output**: the Windows console is cp1252 by default. The scripts that print transcripts
  switch themselves to UTF-8; for everything else set `PYTHONUTF8=1` in your environment once (`setx PYTHONUTF8 1`).
- The optional venvs land in `~/.venvs/<name>/Scripts/` (not `bin/`); `scripts/lib/venv.sh` handles the difference, and
  Python 3.11 is found through the `py -3.11` launcher (`winget install Python.Python.3.11`).

## Doing it by hand

Built and tested on a Mac with Apple silicon; Windows 10/11 works with the notes above; Linux and Intel Macs are untested.
You need:
- ffmpeg (with libvpx and libass): `brew install ffmpeg`
- Node 18 or newer: `brew install node`
- Whisper: `pip install openai-whisper`
- Python packages: `pip install numpy opencv-python pillow`
- Recommended: `pip install google-genai` and a Gemini key (see above); optional: `brew install yt-dlp` to pull reference videos from a link

```bash
git clone https://github.com/kurbaitaev/ghost-editor ~/.claude/skills/ghost-editor
cd ~/.claude/skills/ghost-editor
bash scripts/doctor.sh
python3 scripts/library_restore.py
```

**Other agents** (untested; it is built with Claude Code). Codex, or any agent that reads Agent Skills: clone or symlink the folder into that agent's skills directory. Any other agent: tell it "Follow `<path>/ghost-editor/SKILL.md` to edit this recording." Every step is a plain shell command.
