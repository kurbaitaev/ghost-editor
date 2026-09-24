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
3. **Download the sound effects and music** (free Mixkit licence, a few dozen small files):
   ```bash
   python3 ~/.claude/skills/ghost-editor/scripts/library_restore.py
   ```
4. **Run `doctor.sh` again** until it ends with `0 missing`. Lines marked `opt` are optional.
5. **Gemini key (optional).** Only needed to copy the look of a reel the user shows you, or to make AI B-roll images. Ask the user whether they want that. If yes:
   - they get a free key at https://aistudio.google.com/apikey
   - `pip install google-genai`
   - save it with `echo 'GEMINI_API_KEY=<key>' > ~/.claude/skills/ghost-editor/.env` (the file is gitignored)
6. **Tell the user it's ready**, and that they can now say, for example: "Edit ~/Downloads/my-video.mov into a reel."

Restart Claude Code (or start a new session) so the skill shows up.

---

## Doing it by hand

You need a Mac or Linux machine with:
- ffmpeg (with libvpx and libass): `brew install ffmpeg`
- Node 18 or newer: `brew install node`
- Whisper: `pip install openai-whisper`
- Python packages: `pip install numpy opencv-python`
- Optional: `pip install google-genai` and a Gemini key (see above); `brew install yt-dlp` to pull reference videos from a link

```bash
git clone https://github.com/kurbaitaev/ghost-editor ~/.claude/skills/ghost-editor
cd ~/.claude/skills/ghost-editor
bash scripts/doctor.sh
python3 scripts/library_restore.py
```

**Other agents.** Codex, or any agent that reads Agent Skills: clone or symlink the folder into that agent's skills directory. Any other agent: tell it "Follow `<path>/ghost-editor/SKILL.md` to edit this recording." Every step is a plain shell command.
