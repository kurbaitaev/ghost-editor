#!/usr/bin/env python3
"""Export the licensed-only public edition of this skill into <dest>.

    export_public.py <dest-dir>

The private repo keeps YouTube-ripped meme sounds and green-screen memes (fine
for personal IG/TikTok use, not ours to redistribute). The public edition ships
only assets with a redistribution-safe source:
  - sound effects and music from Mixkit (free licence, commercial use)
  - fonts under the SIL OFL, the YuNet face model (MIT)
and it drops:
  - every `yt:` entry from the SFX kit and the manifest
  - library/memes/* (users add their own with meme_add.py, their rights)
  - examples that depend on ripped memes
Code and docs are copied from the committed tree (git archive), so uncommitted
local files never leak.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
DROP_EXAMPLES = {"gameplan-memes-ru.reel.json"}
PUBLIC_DESCRIPTION = ("AI video editor for talking-head reels. Turns a raw phone recording of someone talking to camera "
    "(retakes, pauses, false starts) into a finished vertical 1080x1920 reel for Instagram, TikTok or Shorts: best take of "
    "each sentence, pause trimming, word-timed captions that never cover the face and stay inside the platform safe area, "
    "motion scenes on the spoken word, sound effects and music mixed against the voice, in seven styles (clean, editorial, "
    "meme, cinematic, launch, kinetic, pop). It can also reverse-engineer a reference edit the user likes and apply that "
    "style to their recording. Use when the user hands over a talking-head video and says \"edit this\", \"make a reel\", "
    "\"make it look like this video\", \"add captions/motion graphics/sound effects\", \"pick the best takes\", "
    "\"remove the pauses\", or asks for a re-cut. Not for landscape screen recordings.")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = os.path.abspath(sys.argv[1])
    if os.path.exists(dest) and os.listdir(dest) and not os.path.exists(os.path.join(dest, ".public-edition")):
        sys.exit(f"{dest} exists and is not a previous public export; refusing to overwrite")
    tmp = tempfile.mkdtemp()
    tar = os.path.join(tmp, "src.tar")
    subprocess.run(["git", "-C", REPO, "archive", "--format=tar", "-o", tar, "HEAD"], check=True)
    if os.path.exists(dest):
        for f in os.listdir(dest):
            if f != ".git":
                p = os.path.join(dest, f)
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(tar) as t:
        t.extractall(dest, filter="data")

    # 1. SFX kit: drop the YouTube rip entries from the fetch list and the manifest
    kit = os.path.join(dest, "scripts", "sfx_fetch.py")
    src = open(kit).read()
    src = "\n".join(l for l in src.splitlines() if '"yt:' not in l) + "\n"
    open(kit, "w").write(src)
    man_p = os.path.join(dest, "library", "sfx", "manifest.json")
    man = json.load(open(man_p))
    kept = {k: v for k, v in man.items() if "Mixkit" in v.get("licence", "") or v.get("mixkit_id")}
    json.dump(kept, open(man_p, "w"), indent=2)
    # 2. memes: none ship; users add their own
    mdir = os.path.join(dest, "library", "memes")
    shutil.rmtree(mdir, ignore_errors=True)
    os.makedirs(mdir)
    open(os.path.join(mdir, "README.md"), "w").write(
        "# Your meme library\n\nEmpty on purpose: memes are other people's media. Add clips you have the rights to use:\n\n"
        "```bash\npython3 scripts/meme_add.py <id> <url-or-file> --tags ... --use ... --triggers ...\n```\n")
    # 3. examples that need ripped memes
    for f in DROP_EXAMPLES:
        p = os.path.join(dest, "examples", f)
        if os.path.exists(p):
            os.remove(p)
    # 4. rebrand: the public edition is ghost-editor; README from public/, a generic SKILL description
    NAME = "ghost-editor"
    readme = os.path.join(dest, "public", "README.md")
    if os.path.exists(readme):
        shutil.copy(readme, os.path.join(dest, "README.md"))
    shutil.rmtree(os.path.join(dest, "public"), ignore_errors=True)
    for root, _, files in os.walk(dest):
        if ".git" in root.split(os.sep):
            continue
        for f in files:
            p = os.path.join(root, f)
            if f == "export_public.py" or not f.endswith((".md", ".py", ".mjs", ".sh", ".json", ".js", ".txt")):
                continue
            t = open(p, encoding="utf8").read()
            t2 = t.replace("meme-reel", NAME)
            if t2 != t:
                open(p, "w", encoding="utf8").write(t2)
    sk = os.path.join(dest, "SKILL.md")
    t = open(sk, encoding="utf8").read()
    t = re.sub(r"^description: .*$", "description: " + PUBLIC_DESCRIPTION, t, count=1, flags=re.M)
    t = t.replace("Check that it is the right person (per the user's rules,\nshow the frames and confirm when there is any doubt)", "Check that it is the right person (show the frames\nand confirm with the user when there is any doubt)")
    open(sk, "w", encoding="utf8").write(t)
    # 5. mark the edition
    open(os.path.join(dest, ".public-edition"), "w").write("licensed-only export of meme-reel\n")
    rips = len(man) - len(kept)
    print(f"-> {dest}\n   sfx kept {len(kept)}, dropped {rips} rips; memes cleared; examples dropped: {', '.join(DROP_EXAMPLES)}")
    left = subprocess.run(["grep", "-rIl", "yt:", os.path.join(dest, "scripts"), os.path.join(dest, "library")], capture_output=True, text=True).stdout.strip()
    if left:
        print("   check these for leftover rip references:\n   " + left.replace("\n", "\n   "))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
