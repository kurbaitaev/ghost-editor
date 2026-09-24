#!/usr/bin/env bash
# Check everything ghost-editor needs on this machine, and say how to fix what's missing.
#   bash scripts/doctor.sh
S="$(cd "$(dirname "$0")/.." && pwd)"
ok=0; bad=0
pass() { echo "  ok    $1"; ok=$((ok+1)); }
fail() { echo "  MISS  $1  ->  $2"; bad=$((bad+1)); }

echo "tools"
command -v ffmpeg >/dev/null && pass "ffmpeg $(ffmpeg -version | head -1 | awk '{print $3}')" || fail ffmpeg "brew install ffmpeg"
ffmpeg -hide_banner -buildconf 2>/dev/null | grep -q enable-libvpx && pass "ffmpeg libvpx (alpha WebM memes)" || fail "ffmpeg libvpx" "brew reinstall ffmpeg"
ffmpeg -hide_banner -buildconf 2>/dev/null | grep -q enable-libass && pass "ffmpeg libass" || fail "ffmpeg libass" "brew reinstall ffmpeg"
command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ] && pass "node $(node -v)" || fail "node >= 18" "brew install node"
v=$(npx -y hyperframes --version 2>/dev/null | tail -1); [ -n "$v" ] && pass "hyperframes $v" || fail hyperframes "npx -y hyperframes --version (needs network once)"
w=${WHISPER:-$(command -v whisper)}; [ -n "$w" ] && pass "whisper ($w)" || fail whisper "pip install openai-whisper (or set WHISPER=/path)"
command -v yt-dlp >/dev/null && pass "yt-dlp $(yt-dlp --version)" || fail yt-dlp "brew install yt-dlp (keep it upgraded: YouTube breaks old builds)"
python3 -c "import numpy" 2>/dev/null && pass "python numpy" || fail numpy "pip install numpy"
python3 -c "import cv2; cv2.FaceDetectorYN" 2>/dev/null && pass "python opencv (face tracking)" || fail opencv "pip install opencv-python"
python3 -c "import google.genai" 2>/dev/null && pass "python google-genai" || fail google-genai "pip install google-genai (AI B-roll, reference study)"

echo "keys"
if [ -n "$GEMINI_API_KEY" ] || grep -qs '^GEMINI_API_KEY=' "$S/.env"; then pass "GEMINI_API_KEY (env or $S/.env)"; else echo "  opt   GEMINI_API_KEY not set: only AI B-roll (broll_gen.py) and reference_study.py need it -> export GEMINI_API_KEY=... or $S/.env"; fi

echo "library"
n=$(ls "$S"/library/sfx/*.wav 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -ge 30 ] && pass "sfx kit ($n files)" || fail "sfx kit ($n files)" "python3 $S/scripts/library_restore.py --sfx-only"
m=$(ls "$S"/library/memes/*/clip.webm "$S"/library/memes/*/image.png 2>/dev/null | wc -l | tr -d ' ')
if [ "$m" -ge 1 ]; then pass "memes ($m)"
elif [ -f "$S/.public-edition" ]; then echo "  opt   memes: none (public edition; add clips you have rights to with scripts/meme_add.py)"
else fail "memes" "python3 $S/scripts/library_restore.py --memes-only"; fi
ls "$S"/library/music/*.mp3 >/dev/null 2>&1 && pass "music beds" || fail "music beds" "python3 $S/scripts/library_restore.py --music-only"

echo; echo "$ok ok, $bad missing"
[ "$bad" -eq 0 ]
