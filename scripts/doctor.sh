#!/usr/bin/env bash
# Check everything ghost-editor needs on this machine, and say how to fix what's missing.
#   bash scripts/doctor.sh
S="$(cd "$(dirname "$0")/.." && pwd)"
ok=0; bad=0
pass() { echo "  ok    $1"; ok=$((ok+1)); }
fail() { echo "  MISS  $1  ->  $2"; bad=$((bad+1)); }

# numpy/opencv/google-genai may live in a separate venv (MEDIA_PY, or ~/.venvs/media) on machines whose python3 has none
PY=${MEDIA_PY:-python3}; "$PY" -c "import numpy" 2>/dev/null || { [ -x "$HOME/.venvs/media/bin/python" ] && PY="$HOME/.venvs/media/bin/python"; }

echo "tools"
command -v ffmpeg >/dev/null && pass "ffmpeg $(ffmpeg -version | head -1 | awk '{print $3}')" || fail ffmpeg "brew install ffmpeg"
ffmpeg -hide_banner -buildconf 2>/dev/null | grep -q enable-libvpx && pass "ffmpeg libvpx (alpha WebM memes)" || fail "ffmpeg libvpx" "brew reinstall ffmpeg"
ffmpeg -hide_banner -buildconf 2>/dev/null | grep -q enable-libass && pass "ffmpeg libass" || fail "ffmpeg libass" "brew reinstall ffmpeg"
command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ] && pass "node $(node -v)" || fail "node >= 18" "brew install node"
# HyperFrames is pinned in ONE place (scripts/HF_VERSION), read by hf.sh, hf_version.py and build.mjs
hv=$(cat "$S/scripts/HF_VERSION" 2>/dev/null)
v=$(bash "$S/scripts/hf.sh" --version 2>/dev/null | tail -1)
[ -n "$v" ] && [ "$v" = "${HF_VERSION:-$hv}" ] && pass "hyperframes $v (pinned in scripts/HF_VERSION)" || fail "hyperframes $hv (scripts/HF_VERSION)" "bash $S/scripts/hf.sh --version (needs network once)"
[ -n "$HF_VERSION" ] && [ "$HF_VERSION" != "$hv" ] && echo "  WARN  HF_VERSION=$HF_VERSION overrides scripts/HF_VERSION ($hv): renders here differ from the other machine; unset it after the test"
un=$(grep -rnE 'npx (-y )?hyperframes([^@]|$)|"npx", "hyperframes"' "$S" --include='*.md' --include='*.py' --include='*.sh' --include='*.mjs' --include='*.js' 2>/dev/null | grep -v -e '/public/' -e node_modules | grep -iv -e unpinned -e 'instead of')
[ -z "$un" ] && pass "no unpinned hyperframes calls in the skill" || { echo "  WARN  unpinned hyperframes calls (use \$S/scripts/hf.sh, or hf() from scripts/hf_version.py):"; echo "$un" | sed 's/^/          /'; }
# x264's thread count is pinned in ONE place (scripts/X264_THREADS): on automatic threads it follows the core count and
# each Mac writes different bytes. Every libx264 encode passes it right after libx264; HyperFrames' get it from hf_ffmpeg.sh.
# VideoToolbox's encoder gives different bytes on every run, so no script may use it.
xt=$(cat "$S/scripts/X264_THREADS" 2>/dev/null)
ux=$(grep -rnIE --include='*.py' --include='*.sh' --include='*.mjs' --include='*.js' -- "(-c:v|-vcodec|-codec:v)[\"', ]*(libx264|h264_videotoolbox|hevc_videotoolbox)" "$S" 2>/dev/null \
  | grep -v -e node_modules -e '/\.venv' -e '/scripts/doctor.sh:' | grep -vE -- "libx264[\"', ]*-threads.{0,60}X264_THREADS")
hx=$(HF_REAL_FFMPEG=echo bash "$S/scripts/hf_ffmpeg.sh" -i in.mp4 -c:v libx264 -preset medium out.mp4 2>/dev/null)
[ -n "$xt" ] && [ -z "$ux" ] && [ "$hx" = "-i in.mp4 -c:v libx264 -threads $xt -preset medium out.mp4" ] \
  && pass "every libx264 encode uses -threads $xt (scripts/X264_THREADS), HyperFrames' too (hf_ffmpeg.sh)" \
  || { echo "  WARN  x264 threads not pinned: these encodes give different bytes on each Mac (pass -threads from scripts/X264_THREADS right after libx264; no VideoToolbox encoder):"
       [ -z "$xt" ] && echo "          scripts/X264_THREADS is missing or empty"
       [ "$hx" = "-i in.mp4 -c:v libx264 -threads $xt -preset medium out.mp4" ] || echo "          scripts/hf_ffmpeg.sh does not add it to HyperFrames' encodes"
       [ -n "$ux" ] && echo "$ux" | sed 's/^/          /'; }
w=${WHISPER:-$(command -v whisper)}; [ -n "$w" ] && pass "whisper ($w)" || fail whisper "pip install openai-whisper (or set WHISPER=/path)"
command -v yt-dlp >/dev/null && pass "yt-dlp $(yt-dlp --version)" || echo "  opt   yt-dlp not installed: only needed to pull a reference video from a link -> brew install yt-dlp"
"$PY" -c "import numpy" 2>/dev/null && pass "python numpy ($PY)" || fail numpy "pip install numpy"
"$PY" -c "import cv2; cv2.FaceDetectorYN" 2>/dev/null && pass "python opencv (face tracking)" || fail opencv "pip install opencv-python"
"$PY" -c "import google.genai" 2>/dev/null && pass "python google-genai" || fail "python google-genai (B-roll people/line checks, QA)" "$PY -m pip install google-genai"
"$PY" -c "import PIL" 2>/dev/null && pass "python pillow" || fail pillow "$PY -m pip install pillow"

echo "keys"
# required: insert_prep.py, broll_vision.py and broll_qa.py's people / match checks ask Gemini, and an unchecked shot FAILS
# the render's QA. One cheap call proves the key works (a set but revoked key looks fine until the batch).
if [ -n "$GEMINI_API_KEY" ] || grep -qs '^GEMINI_API_KEY=' "$S/.env"; then
  r=$(S="$S" "$PY" - 2>&1 <<'PYEOF'
import os, re
from google import genai
from google.genai import types
k = os.environ.get("GEMINI_API_KEY")
if not k:
    m = re.search(r"GEMINI_API_KEY\s*=\s*['\"]?([^'\"\n]+)", open(os.path.join(os.environ["S"], ".env")).read())
    k = m.group(1).strip()
c = genai.Client(api_key=k, http_options=types.HttpOptions(timeout=30000))
print((c.models.generate_content(model="gemini-2.5-flash", contents="Reply with the single word ok.").text or "").strip()[:20])
PYEOF
)
  case "$r" in [Oo]k*) pass "GEMINI_API_KEY works (one test call)";;
    *) r=${r##*$'\n'}; fail "GEMINI_API_KEY is set but the test call failed: ${r:0:140}" "check the key at aistudio.google.com/apikey (env or $S/.env)";; esac
else fail "GEMINI_API_KEY (insert_prep.py, broll_vision.py, broll_qa.py people/match: unchecked shots fail)" "export GEMINI_API_KEY=... or put GEMINI_API_KEY=... in $S/.env (free key: aistudio.google.com/apikey)"; fi

if [ -n "$ELEVENLABS_API_KEY" ] || grep -qs '^ELEVENLABS_API_KEY=' "$S/.env"; then pass "ELEVENLABS_API_KEY (narrated explainers)"; else echo "  opt   ELEVENLABS_API_KEY not set: only scripts/tts_elevenlabs.py (explainer voiceover) needs it -> $S/.env"; fi
[ -x "${DF_VENV:-$S/.venv-df}/bin/deepFilter" ] && pass "DeepFilterNet (scripts/denoise.sh)" || echo "  opt   DeepFilterNet not set up: scripts/denoise.sh installs it on first use (needs python3.11 + uv)"

echo "optional tools (the core skill works without them)"
[ -f "$S/templates/vendor/hf-paper.js" ] && pass "Paper Shaders bundle (templates/vendor/hf-paper.js)" || fail "templates/vendor/hf-paper.js (shader looks)" "git checkout templates/vendor, or rebuild: cd $S/tools/paper && npm install && node build-vendor.mjs"
e=$(ls "$S"/library/emoji/*.webm 2>/dev/null | wc -l | tr -d ' ')
[ "$e" -ge 30 ] && pass "animated emoji ($e Fluent webm)" || echo "  opt   animated emoji not fetched: emoji beats fall back to the font glyph -> python3 -I $S/scripts/emoji_fetch.py (needs ffmpeg libvpx-vp9)"
l=$(ls "$S"/library/luts/*.cube 2>/dev/null | wc -l | tr -d ' ')
[ "$l" -ge 6 ] && pass "film-look LUTs ($l in library/luts)" || echo "  opt   film-look LUTs not generated: only look.film needs them -> bash $S/scripts/setup_looks.sh (venv ~/.venvs/ghost-looks)"
[ -x "${MATTE_VENV:-$HOME/.venvs/ghost-matte}/bin/python" ] && pass "BiRefNet matte (behind beats, cutout beats)" || echo "  opt   BiRefNet matte not set up: behind beats fall back to hyperframes remove-background (u2net), cutout beats need it -> bash $S/scripts/setup_matte.sh (~2.6 GB with weights)"
mc="${CUTOUT_FX_CACHE:-${GHOST_MATTE_CACHE:-$HOME/.cache/ghost-matte}}"
[ -x "${MATTE_VENV:-$HOME/.venvs/ghost-matte}/bin/python" ] && [ ! -f "$mc/hf/BiRefNet_lite/model.safetensors" ] && echo "  opt   BiRefNet_lite weights not cached: cutout beats will download them (176 MB) on first use -> bash $S/scripts/setup_matte.sh"
[ -x "${AUDIOQA_VENV:-$HOME/.venvs/ghost-audioqa}/bin/python" ] && pass "audio QA venv (vad_pauses, voice_enhance)" || echo "  opt   audio QA venv not set up: only autocut --vad, vad_pauses.py and voice_enhance.py need it -> bash $S/scripts/setup_audioqa.sh"
[ -x "${CAPTIONS_VENV:-$HOME/.venvs/ghost-captions}/bin/python" ] && pass "caption metrics venv (scripts/font_metrics.py)" || echo "  opt   caption metrics venv not set up: only needed to add a font to the caption templates -> bash $S/scripts/setup_captions.sh"

echo "recipes"
ls "$S"/templates/fonts/inter-tight-cyrillic.woff2 "$S"/templates/fonts/playfair-display-italic-cyrillic.woff2 >/dev/null 2>&1 && pass "Seoul list / RESULT fonts (Inter Tight, Playfair Display, OFL)" || fail "templates/fonts/inter-tight-*.woff2" "git -C $S checkout templates/fonts"
miss=""; for e in waving-hand hand-splayed point-right running yum eyes fire; do [ -f "$S/library/emoji/$e.webm" ] || miss="$miss,$e"; done
[ -z "$miss" ] && pass "Seoul list emoji (hands, eyes, runner, yum, fire)" || echo "  opt   Seoul list emoji missing (${miss#,}) -> python3 -I $S/scripts/emoji_fetch.py --only ${miss#,}"
[ -f "$S/library/sfx/send-swoosh.wav" ] && pass "Seoul list send sound (send-swoosh)" || echo "  opt   send-swoosh not fetched (Seoul list outro) -> python3 $S/scripts/sfx_fetch.py --only send-swoosh"

echo "library"
n=$(ls "$S"/library/sfx/*.wav 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -ge 30 ] && pass "sfx kit ($n files)" || fail "sfx kit ($n files)" "python3 $S/scripts/library_restore.py --sfx-only"
m=$(ls "$S"/library/memes/*/clip.webm "$S"/library/memes/*/image.png 2>/dev/null | wc -l | tr -d ' ')
if [ "$m" -ge 1 ]; then pass "memes ($m)"
elif [ -f "$S/.public-edition" ]; then echo "  opt   memes: none (public edition; add clips you have rights to with scripts/meme_add.py)"
else fail "memes" "python3 $S/scripts/library_restore.py --memes-only"; fi
ls "$S"/library/music/*.mp3 >/dev/null 2>&1 && pass "music beds" || fail "music beds" "python3 $S/scripts/library_restore.py --music-only"

echo "toolchain vs the other machine (scripts/toolchain.py: records this one in library/toolchain/, compares)"
tc=$(python3 "$S/scripts/toolchain.py" compare 2>&1); tcr=$?
echo "$tc" | sed -e 's/^  DIFF /  WARN  /' -e 's/^  info /  info  /' -e 's/^vs /  /' -e 's/^no other/  opt   no other/'
[ "$tcr" -ne 0 ] && echo "        the WARN lines change the edit (cut, mix or render); align them (docs/SYNC.md, Toolchain parity)"

echo; echo "$ok ok, $bad missing"
[ "$bad" -eq 0 ]
