#!/usr/bin/env python3
"""Advance widths for the Product page type voices, so productpage.fit() can size a line without a browser.

    ~/.venvs/ghost-captions/bin/python fontwidths.py $P/build/metrics.json "Inter Tight|800" "Playfair Display Italic|600"

Each key is "<family>|<weight>"; the family names the files in templates/fonts ("Playfair Display Italic" = the
playfair-display-italic-*.woff2 pair). Same method as scripts/font_metrics.py (the variable font instanced at the weight,
thousandths of an em, kerning ignored, so widths err wide); the cyrillic file is read first, then latin. Keys already in
the file are kept. productpage.py runs this itself when build/metrics.json lacks a voice (it needs fontTools + brotli,
which only the ghost-captions venv has: bash scripts/setup_captions.sh).
"""
import json
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from font_metrics import advances  # noqa: E402

FONTS = SKILL / "templates" / "fonts"
STEM = {"Inter Tight": "inter-tight", "Inter": "inter", "Playfair Display": "playfair-display",
        "Playfair Display Italic": "playfair-display-italic", "Inter Tight Italic": "inter-tight-italic",
        "Oswald": "oswald", "Montserrat": "montserrat", "Unbounded": "unbounded", "PT Mono": "pt-mono"}


def table(key):
    fam, wt = key.split("|")
    stem = STEM[fam]
    files = sorted(FONTS / f"{stem}-{r}.woff2" for r in ("latin", "cyrillic") if (FONTS / f"{stem}-{r}.woff2").exists())
    if not files:
        sys.exit(f"fontwidths.py: no {stem}-latin/cyrillic.woff2 in {FONTS}")
    out = {}
    for p in files:
        for ch, a in advances(p, int(wt)).items():
            out.setdefault(ch, a)
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    dst = sys.argv[1]
    res = json.load(open(dst)) if os.path.exists(dst) else {}
    for key in sys.argv[2:]:
        if key not in res:
            res[key] = table(key)
            print(f"{key}: {len(res[key])} chars")
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    json.dump(res, open(dst, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
