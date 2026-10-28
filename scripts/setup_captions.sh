#!/usr/bin/env bash
# Optional: the small venv for scripts/font_metrics.py, which regenerates scripts/lib/metrics.json (the glyph widths the
# caption templates lay out with) after a font is added to templates/fonts. The caption templates themselves need nothing.
#   bash scripts/setup_captions.sh            -> ~/.venvs/ghost-captions (override with CAPTIONS_VENV=/path)
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib/venv.sh"
V="${CAPTIONS_VENV:-$HOME/.venvs/ghost-captions}"
PY="${PYTHON311:-$(command -v python3.11 || command -v python3 || command -v python)}"
venv_ok "$V" || "$PY" -m venv "$V"
VB=$(venv_bin "$V")
"$VB/python" -m pip install -q --upgrade pip
"$VB/pip" install -q "fonttools==4.66.1" "brotli==1.2.0"
"$VB/python" -c "import fontTools, brotli" && echo "captions venv ready: $V"
