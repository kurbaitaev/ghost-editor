#!/usr/bin/env bash
# Optional: the BiRefNet person matte for `behind` beats (scripts/matte.py) and the cutout effects (scripts/cutout_fx.py:
# cutout beats, look.cutout, covers). Without it, behind beats fall back to `hyperframes remove-background` (u2net:
# blobby edges, a jumpy outline) and cutout beats stop the build. One-time: ~1.5 GB venv + ~1.1 GB weights (downloaded
# into ~/.cache/ghost-matte, never into the repo). Weights: BiRefNet-portrait + BiRefNet_lite, MIT. bria models are refused.
#   bash scripts/setup_matte.sh            -> ~/.venvs/ghost-matte (override with MATTE_VENV=/path)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
V="${MATTE_VENV:-$HOME/.venvs/ghost-matte}"
PY="${PYTHON311:-$(command -v python3.11 || echo /opt/homebrew/bin/python3.11)}"
[ -x "$V/bin/python" ] || "$PY" -m venv "$V"
"$V/bin/pip" install -q --upgrade pip
"$V/bin/pip" install -q -r "$HERE/matte-requirements.txt"
# warm the weights so the first build does not stall on a download
"$V/bin/python" -c "import sys; sys.path.insert(0, '$HERE'); import matte; matte.hf_dir('ZhengPeng7/BiRefNet-portrait'); print('weights ok:', matte.CACHE)"
# cutout beats default to BiRefNet_lite (+176 MB); the other models download on first use
"$V/bin/python" "$HERE/cutout_fx.py" --help >/dev/null && "$V/bin/python" -c "import sys; sys.path.insert(0, '$HERE'); import cutout_fx; cutout_fx.weights_dir('lite'); print('cutout_fx weights ok')"
echo "matte venv ready: $V"
