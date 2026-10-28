#!/usr/bin/env python3
"""One fixed house look per style, small variation per reel (references/broll.md 5b).

GRADE RULE: the speaker's face shots are NEVER regraded to a house look. The speaker's footage
keeps its natural, as-shot colour; inserts are conformed TO it (insert_prep.py --ref <plate as shot>). The house look is
type, captions, transitions, the emphasis device, the accent palette and the look of the style's own graphics. The
measured "grade" in house.json is reference data only; `apply` refuses, and broll_qa.py fails a regraded plate (as_shot).


    house_look.py measure --style clean-os RENDER [RENDER ...]    # the grade of the speaker's frames in approved reels -> recipes/<style>/house.json
    house_look.py apply ...                                         # RETIRED: the speaker's face is never regraded
    house_look.py check --style clean-os RENDER                    # how far the speaker's frames in a render are from the house grade

The house grade is the median of grade_lib stats (L*, white balance, chroma, contrast) over the frames of approved reels
where the speaker's face is on screen (YuNet + SFace vs library/me/face_ref.npz), or over all footage frames for a B-roll-led style
(measure --frames footage: Seoul list, whose reference has one recognisable frame of the speaker). "Small variation" = what is left inside the
tolerance after the conform: the solver moves each stat only to the edge of its band (grade_lib.TOL), so a dusk shoot
stays a little warmer than a noon one. Tolerance (house.json "tolerance"): |dL*| 8, |d wb b*| 5, |d wb a*| 4,
saturation and contrast x0.85-1.15. broll_qa.py --style fails a render outside it.
The rest of the house look (type, captions, insert frame, transitions, accent palette, emphasis device) is in the same
house.json and the recipe's SYSTEM.md "House look" section; the build reads them instead of inventing a new look per reel.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade_lib as G  # noqa: E402

RECIPES = os.path.join(HERE, "..", "recipes")
TOLERANCE = {"L": 8.0, "wb_b": 5.0, "wb_a": 4.0, "sat": [0.85, 1.15], "contrast": [0.85, 1.15]}


def house_path(style):
    p = os.path.join(RECIPES, style, "house.json")
    if not os.path.isdir(os.path.dirname(p)):
        sys.exit(f"no recipe {style}")
    return p


def load(style):
    p = house_path(style)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def footage_frames(video, fps=2.0):
    """BGR frames (270 wide) of a render that are footage (not a flat graphic or a white page): B-roll-led styles"""
    from broll_qa import decode, nb_features, is_graphic
    info = G.probe(video)
    w, h = 270, int(270 * info["h"] / info["w"]) // 2 * 2
    return [im for im in decode(video, w, h, fps=fps) if not is_graphic(nb_features(im)) and (im > 235).mean() < 0.35]


def frames_for(video, house):
    return footage_frames(video) if house.get("grade_frames") == "footage" else his_frames(video)


def his_frames(video, fps=2.0):
    """BGR frames (270 wide) of a render where the speaker's face is on screen"""
    import own_footage as OF
    from broll_qa import decode
    ref = OF.load_ref()
    info = G.probe(video)
    w, h = 540, int(540 * info["h"] / info["w"]) // 2 * 2
    out = []
    for im in decode(video, w, h, fps=fps):
        fs = [f for f in OF.who(im, ref, 0.6) if f[4] == "me" and f[2] >= 0.09 * w]
        if fs:
            out.append(cv2.resize(im, (270, int(270 * h / w) // 2 * 2), interpolation=cv2.INTER_AREA))
    return out


def stats_of(frames):
    return G.median_stats([G.frame_stats(f) for f in frames])


def diff(st, house):
    tol = house.get("tolerance", TOLERANCE)
    g = house["grade"]
    d = {"dL": st["L"] - g["L"], "dwb_b": st["wb_b"] - g["wb_b"], "dwa": st["wb_a"] - g["wb_a"],
         "sat": st["C"] / max(g["C"], 1e-6), "contrast": st["Lstd"] / max(g["Lstd"], 1e-6)}
    off = []
    if abs(d["dL"]) > tol["L"]:
        off.append(f"exposure {d['dL']:+.0f} L*")
    if abs(d["dwb_b"]) > tol["wb_b"]:
        off.append(f"white balance {d['dwb_b']:+.0f} b*")
    if abs(d["dwa"]) > tol["wb_a"]:
        off.append(f"tint {d['dwa']:+.0f} a*")
    if not tol["sat"][0] <= d["sat"] <= tol["sat"][1]:
        off.append(f"saturation x{d['sat']:.2f}")
    if not tol["contrast"][0] <= d["contrast"] <= tol["contrast"][1]:
        off.append(f"contrast x{d['contrast']:.2f}")
    return {k: round(v, 2) for k, v in d.items()}, off


def cmd_measure(a):
    rows, used = [], []
    house = load(a.style)
    house["grade_frames"] = a.frames
    for v in a.render:
        fr = frames_for(v, house)
        if len(fr) < 10:
            print(f"skip {v}: only {len(fr)} usable frames ({a.frames})")
            continue
        rows.append(stats_of(fr))
        used.append({"render": os.path.basename(v), "frames": len(fr)})
    if not rows:
        sys.exit("no usable reference render")
    house["grade"] = {k: round(float(np.median([r[k] for r in rows])), 2) for k in rows[0]}
    house["grade_from"] = used
    house.setdefault("tolerance", TOLERANCE)
    json.dump(house, open(house_path(a.style), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(house["grade"]), "->", house_path(a.style))


def cmd_apply(a):
    sys.exit("house_look.py apply is retired: the speaker's face keeps its as-shot colour. Use the plate as it is "
             "and conform the inserts to it: insert_prep.py SRC OUT --ref <plate>.")
    house = load(a.style)
    if not house.get("grade"):
        sys.exit(f"{a.style} has no house grade yet (the first approved reel defines it: house_look.py measure)")
    info = G.probe(a.plate)
    tr = info["transfer"] if info["transfer"] in ("arib-std-b67", "smpte2084") else None
    ts = [info["dur"] * (i + .5) / 12 for i in range(12)]
    fr = G.sample_frames(a.plate, ts)
    p, before, after = G.solve(fr, house["grade"], strength=a.strength, transfer=tr, neutral_guard=False, s_range=(0.3, 1.8))
    _, off0 = diff(before, house)
    d1, off1 = diff(after, house)
    lut = tempfile.NamedTemporaryFile(suffix=".cube", delete=False).name
    G.write_cube(lut, p, tr)
    matrix = ":in_color_matrix=bt2020" if G.is_hdr(info) else ""
    vf = (f"scale=flags={G.SCALE_FLAGS}{matrix},format=rgb48le,lut3d=file='{G.filter_path(lut)}':interp=tetrahedral,"
          f"scale=out_color_matrix=bt709:out_range=tv:flags={G.SCALE_FLAGS},format=yuv420p,"
          f"setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv")
    g = max(1, int(round(info["fps"])))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.plate, "-map", "0:v", "-map", "0:a?", "-c:a", "copy", "-vf", vf,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-g", str(g), "-keyint_min", str(g),
                    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                    "-movflags", "+faststart", a.out], check=True)
    os.unlink(lut)
    rep = {"plate": os.path.abspath(a.plate), "style": a.style, "params": {k: round(v, 3) for k, v in p.items()},
           "before_off": off0, "after": d1, "after_off": off1}
    json.dump(rep, open(a.out + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False))
    print(f"-> {a.out}: {'inside' if not off1 else 'still off: ' + '; '.join(off1)} the {a.style} house look "
          f"(was: {'; '.join(off0) or 'inside'})")


def cmd_check(a):
    house = load(a.style)
    if not house.get("grade"):
        print(f"{a.style}: no house grade yet")
        return
    fr = frames_for(a.render, house)
    d, off = diff(stats_of(fr), house)
    print(json.dumps(d), "OFF: " + "; ".join(off) if off else "inside the house look")
    sys.exit(1 if off else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("measure"); p.add_argument("--style", required=True); p.add_argument("render", nargs="+")
    p.add_argument("--frames", choices=["his", "footage"], default="his", help="the speaker's face frames (talking heads) or all footage frames (B-roll-led)")
    p = sp.add_parser("apply"); p.add_argument("--style", required=True); p.add_argument("plate"); p.add_argument("out")
    p.add_argument("--strength", type=float, default=1.0)
    p = sp.add_parser("check"); p.add_argument("--style", required=True); p.add_argument("render")
    a = ap.parse_args()
    {"measure": cmd_measure, "apply": cmd_apply, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
