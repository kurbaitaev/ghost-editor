#!/usr/bin/env python3
"""Clean OS recipe: download the style's fonts (Inter variable roman+italic, Great Vibes) from Google Fonts
into <project>/assets/fonts/ with a local @font-face file (fonts-local.css). Latin + Cyrillic. SIL OFL.

    python3 $S/recipes/clean-os/fetch_fonts.py <project>
"""
import os, re, sys, urllib.request

dst = os.path.join(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "."), "assets", "fonts")
os.makedirs(dst, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
url = "https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300..800;1,14..32,300..800&family=Great+Vibes&display=swap"
css = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA})).read().decode()
out = []
for sub, block in re.findall(r"/\* ([a-z-]+) \*/\s*@font-face \{(.*?)\}", css, re.S):
    if sub not in ("cyrillic", "cyrillic-ext", "latin"):
        continue
    fam = re.search(r"font-family: '([^']+)'", block).group(1)
    sty = re.search(r"font-style: (\w+)", block).group(1)
    src = re.search(r"url\((https[^)]+)\)", block).group(1)
    fn = f"{fam.replace(' ', '')}-{sty}-{sub}.woff2"
    urllib.request.urlretrieve(src, os.path.join(dst, fn))
    out.append("@font-face {" + block.replace(src, fn) + "}")
open(os.path.join(dst, "fonts-local.css"), "w").write("\n".join(out))
print(f"{len(out)} faces -> {dst}")
