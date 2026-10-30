#!/usr/bin/env python3
"""The CC0 meme-sound pack: reaction sounds from Freesound that the uploader recorded or made
themselves and released as CC0 1.0 (public domain: commercial use, no credit, redistribution OK).
Unlike the Mixkit kit (fetched at setup, never shipped) and the YouTube rips (private only),
these files ship in the repo as library/sfx/cc0-<id>.wav.

    cc0_pack.py list                 # the pack, with sources
    cc0_pack.py build [--only a,b]   # download the HQ previews, trim, peak-normalize, merge manifest.json

Every entry was checked by hand on 2026-10-29: the sound page shows "Creative Commons 0" and the
description says the uploader recorded or synthesized it (no rips of the famous meme audio).
Re-check the page before adding a new one, and listen on the audition page before using it.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SFX = os.path.abspath(os.path.join(HERE, "..", "library", "sfx"))
PREVIEW = "https://cdn.freesound.org/previews/{a}/{id}_{uid}-hq.mp3"

# id, freesound id, uploader, uploader id, title, role, tags, max seconds, fade-out seconds, what it is
PACK = [
    ("deep-boom", 539968, "Za-Games", 12029332, "Deep Boom", "meme", ["punchline", "claim", "reveal", "sus"], 2.5, 0.6, "deep explosion boom"),
    ("vinyl-scratch", 71853, "ludvique", 1062668, "record_scratch.wav", "meme", ["wait", "freeze-frame", "twist"], 0.6, 0.05, "cartridge scratched over a vinyl record"),
    ("error-beep", 478191, "JonnyRuss01", 10233023, "Beep_Error_1.wav", "meme", ["wrong", "myth", "fail"], 0.5, 0.05, "soft error beep made from a metal bowl"),
    ("metal-clang", 125404, "jasonLON", 2279655, "Metallic Clang.aif", "meme", ["fail", "sudden", "absurd"], 1.8, 0.4, "baking pan hit with a bass-drum mallet, layered"),
    ("violin-sad", 234311, "andyssoundbox", 4232887, "Hearts and Flowers.wav", "meme", ["sad", "pity"], 5.5, 0.8, "Hearts and Flowers (1893, public domain) played on violin"),
    ("dark-sting", 578577, "nomiqbomi", 10522382, "Dark Crescendo 3", "meme", ["reveal", "twist", "drama"], 3.6, 0.5, "dark orchestral crescendo, made in Logic"),
    ("piano-sting", 183500, "ecfike", 2337290, "Piano Cord.wav", "meme", ["drama", "mystery", "reveal"], 1.75, 0.4, "minor piano chord hit"),
    ("group-ooh", 870650, "CHallSmith", 18412227, "Group Ooh 1", "meme", ["burn", "spicy", "shock"], 2.8, 0.3, "loop group's synchronized ooh"),
    ("gong-hit", 436486, "rabban625", 2988281, "gong-013.wav", "meme", ["punchline", "stop", "verdict"], 2.9, 0.8, "live orchestral gong"),
    ("cricket-chirp", 822935, "_sinny_", 14007850, "cricket chirping (slow)", "meme", ["awkward", "silence"], 2.8, 0.3, "a cricket, field recording"),
    ("air-horn", 414208, "jacksonacademyashmore", 6938106, "Airhorn", "meme", ["hype", "win"], 1.6, 0.15, "air horn made in Audacity"),
    ("huh-voice", 150505, "davdud101", 1883289, "Huh? - Vocal", "meme", ["confused", "disbelief"], 0.9, 0.05, "young male voice: huh?"),
    ("wow-voice", 167355, "willy_ineedthatapp_com", 3062051, "wow.mp3", "meme", ["impressive", "flex"], 1.6, 0.1, "wow in a high voice"),
    ("bike-honk", 188039, "AntumDeluge", 3403708, "Bicycle Horn", "meme", ["absurd", "dumb", "bad-joke"], 0.7, 0.05, "child's plastic bicycle horn"),
    ("whip-crack", 529925, "SciFiSounds", 11751070, "Whip Crack.m4a", "meme", ["roast", "savage", "fast"], 0.6, 0.05, "whip crack"),
    ("tada", 397355, "plasterbrain", 4284968, "Tada Fanfare A", "meme", ["win", "done", "reveal"], 1.75, 0.3, "brass tada in A major"),
    ("glass-break", 141563, "avrahamy", 1422573, "Glass Break", "meme", ["fail", "broke", "shatter"], 1.9, 0.3, "a glass window breaking"),
    ("cartoon-zip", 541507, "se2001", 8472935, "Cartoon Quick Zip 02", "meme", ["fast", "exit", "gone"], 0.3, 0.03, "mouth-made cartoon zip"),
    ("riser-short", 685256, "syntheffects", 12265588, "Riser sound effect short.wav", "riser", ["build-up", "suspense"], 3.05, 0.03, "noise riser"),
    ("oof-voice", 719053, "unfa", 1038806, "Oof (original)", "meme", ["fail", "pain", "ouch"], 0.35, 0.03, "an original oof, recorded by the uploader"),
    ("oh-no-voice", 801386, "Sadiquecat", 5287430, "Fear - ohno ohno ohno", "meme", ["mistake", "dread"], 1.7, 0.1, "male voice actor: oh no oh no oh no"),
    ("glitch-hit", 673773, "h0p1r4e7o", 10282604, "Glitch SFX - 1 sek.wav", "impact", ["error", "tech", "glitch"], 0.9, 0.05, "digital glitch"),
]


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def normalize(src, dst, max_s, fade):
    # trim silence at both ends, cap length, fade out, 48 kHz stereo, peak -1 dBFS (same house format as sfx_fetch.py)
    trim = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.01,"
            "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,areverse,"
            f"atrim=0:{max_s}")
    tmp = dst + ".tmp.wav"
    sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", trim, "-ar", "48000", "-ac", "2", tmp])
    dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tmp]).stdout)
    fade = min(fade, dur / 2)
    peak = float(re.search(r"max_volume: (-?[\d.]+) dB", sh(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", tmp, "-af", "volumedetect", "-f", "null", "-"]).stderr).group(1))
    sh(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", f"afade=t=out:st={dur - fade:.3f}:d={fade:.3f},volume={-1.0 - peak:.2f}dB",
        "-ar", "48000", "-c:a", "pcm_s16le", dst])
    os.remove(tmp)
    return round(dur, 3)


def build(only):
    man_p = os.path.join(SFX, "manifest.json")
    man = json.load(open(man_p))
    today = datetime.date.today().isoformat()
    for sid, fid, user, uid, title, role, tags, max_s, fade, what in PACK:
        if only and sid not in only:
            continue
        url = PREVIEW.format(a=fid // 1000, id=fid, uid=uid)
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "in.mp3")
            req = urllib.request.Request(url, headers={"User-Agent": "ghost-editor cc0_pack"})
            open(src, "wb").write(urllib.request.urlopen(req, timeout=60).read())
            dur = normalize(src, os.path.join(SFX, f"cc0-{sid}.wav"), max_s, fade)
        man[sid] = {"file": f"cc0-{sid}.wav", "role": role, "tags": tags, "duration": dur, "peak_db": -1.0,
                    "source": f"https://freesound.org/people/{user}/sounds/{fid}/ \"{title}\" by {user} (HQ preview, cdn.freesound.org/previews)",
                    "licence": "CC0 1.0 public domain (Freesound; commercial OK, no credit, redistribution OK)",
                    "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/", "licensed": True,
                    "freesound_id": str(fid), "what": what,
                    "edit": f"silence trimmed, max {max_s} s, {fade} s fade-out, 48 kHz stereo, peak -1 dBFS",
                    "added": man.get(sid, {}).get("added", today), "pack": "cc0",
                    "licence_checked": "2026-10-29 (sound page shows Creative Commons 0; uploader's own recording or synth)"}
        print(f"  {sid:15} {dur:5.2f} s  {role:6}  freesound {fid} by {user}")
    json.dump(man, open(man_p, "w"), indent=2, ensure_ascii=False)
    open(man_p, "a").write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "build"])
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if a.cmd == "list":
        for p in PACK:
            print(f"{p[0]:15} {p[5]:6} {','.join(p[6]):28} freesound.org/s/{p[1]}  {p[9]}")
    else:
        build(set(filter(None, a.only.split(","))))


if __name__ == "__main__":
    main()
