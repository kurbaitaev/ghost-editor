#!/usr/bin/env python3
"""Prepare one B-roll insert for a reel in ONE ffmpeg pass: cut, HDR -> SDR BT.709, fps conform, grade conform to the
speaker plate, crop/scale, 1 s keyframes. Writes <out> + <out>.json (what was done, stats before/after vs the plate).

    insert_prep.py SRC OUT --in 3.5 --dur 2.0 --ref assets/plate.mp4 [--size 1080x1920] [--focus 0.5,0.45]
                   [--crop x:y:w:h] [--strength 1.0] [--no-grade] [--fps 30] [--fps-mode retime|drop] [--fit]
    insert_prep.py --check SRC --in 3.5 --dur 2.0 --ref assets/plate.mp4     # numbers only, no file
    insert_prep.py PHOTO.jpg OUT.jpg --ref assets/plate.mp4                    # a still (AI still, photo card): graded only

Rules it enforces (2026-10-13 B-roll audit, references/broll.md):
- people: the B-roll people rules (people-rules.json). Gemini checks the window (broll_vision.py); a shot that breaks
  one is refused. --line also checks that the shot shows the line it sits on. --vision-ok 'note' only after the user
  looked at it.
- --ref is THE SPEAKER'S PLATE AS SHOT: the insert is conformed to the speaker, never the speaker's face to a house look.
- never pads a clip past its end: when SRC has less than the needed span after --in it stops with the length available
  (--fit shortens the output instead). No tpad, no held last frame: that froze a cafe tile for 1.4 s.
- HDR sources (HLG / PQ, BT.2020: iPhone footage, some Pexels files) are tone-mapped to SDR BT.709 inside the LUT;
  one HDR clip in a HyperFrames composition switches the whole render to HDR.
- fps: 23.976/24/25 fps sources are RETIMED so every source frame plays once (no duplicated frames = no judder; the
  shot plays 1.2-1.25x faster, reported); 50/60 fps sources drop every other frame; 29.97 is treated as 30.
- 1 s keyframe interval (-g = fps): sparse keyframes made HyperFrames warn and seek slowly on every Oct 12 cut.
- grade: the insert's exposure, contrast, white balance and saturation are moved onto the plate's (grade_lib.py), so the
  QA (broll_qa.py) passes it: |d wb b*| <= 8, |d L*| <= 15, saturation x0.8-1.2. Clamps keep a night shot from being
  pushed to day; if the result still misses, the shot is from another world: pick another (the JSON says why).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grade_lib as G  # noqa: E402


def target_span(info, dur, fps, mode):
    """source seconds needed for `dur` output seconds, the speed factor and the fps filter"""
    sf = info["fps"]
    if abs(sf - fps) / fps < 0.002:                       # 29.97 / 30
        return dur * fps / sf, fps / sf, f"setpts=(PTS-STARTPTS)*{sf / fps:.6f}", "as is"
    if sf < fps and mode == "retime":                    # 23.976 / 24 / 25: every source frame once, faster
        return dur * fps / sf, fps / sf, f"setpts=(PTS-STARTPTS)*{sf / fps:.6f}", f"retimed {sf:g} -> {fps:g} fps (x{fps / sf:.3f} speed)"
    if sf > fps:                                         # 50 / 60: decimate
        return dur, 1.0, f"fps={fps}", f"{sf:g} -> {fps:g} fps (drop frames)"
    return dur, 1.0, f"fps={fps}", f"{sf:g} -> {fps:g} fps (duplicated frames: judder)"


def crop_expr(info, size, focus, crop):
    if crop:
        return f"crop={crop}"
    W, H = size
    sw, sh = info["w"], info["h"]
    if info.get("rotation") in (90, -90, 270, -270):
        sw, sh = sh, sw
    ar = W / H
    if sw / sh > ar:
        cw, ch = int(round(sh * ar / 2)) * 2, sh
    else:
        cw, ch = sw, int(round(sw / ar / 2)) * 2
    fx, fy = focus
    x = int(round(min(max(0, fx * sw - cw / 2), sw - cw)))
    y = int(round(min(max(0, fy * sh - ch / 2), sh - ch)))
    return f"crop={cw}:{ch}:{x}:{y}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--in", dest="tin", type=float, default=0.0, help="source in-point, seconds")
    ap.add_argument("--dur", type=float, default=None, help="OUTPUT duration, seconds (videos)")
    ap.add_argument("--ref", help="the speaker plate (video) whose grade the insert is conformed to")
    ap.add_argument("--ref-stats", help="JSON stats instead of --ref (grade_lib.plate_stats output)")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--focus", default="0.5,0.5", help="crop centre as fractions of the source frame")
    ap.add_argument("--crop", help="explicit ffmpeg crop w:h:x:y in source pixels (overrides --size aspect/--focus)")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--fps-mode", choices=["retime", "dup"], default="retime")
    ap.add_argument("--strength", type=float, default=1.0, help="0..1: how far to move the grade onto the plate")
    ap.add_argument("--sat-target", type=float, help="saturation as a ratio of the plate's (default: just inside x0.9-1.1). Styles that lay "
                    "big white type over the footage (Seoul list) read ~0.1 lower in the render: 1.1 there")
    ap.add_argument("--kind", choices=["auto", "own", "ai", "stock"], default="auto",
                    help="where SRC comes from (auto: by path/name). Stock is a last resort and only inside a frame (broll_qa fails "
                         "full-screen stock); own footage is face-checked: only the speaker may appear")
    ap.add_argument("--people-ok", action="store_true", help="the user confirmed the people in this own-footage window")
    ap.add_argument("--line", help="the spoken line this shot sits on: the vision check also asks whether the shot shows it")
    ap.add_argument("--vision-ok", metavar="NOTE", help="the user looked at the flagged shot and confirmed it (recorded in the sidecar)")
    ap.add_argument("--no-vision", action="store_true", help="skip the Gemini people / line check here (broll_qa.py still runs it)")
    ap.add_argument("--no-grade", action="store_true")
    ap.add_argument("--fit", action="store_true", help="shorten the output when the source runs out (never pad)")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--check", action="store_true", help="print the plan and the grade numbers, write nothing")
    a = ap.parse_args()
    if G.cv2 is None:
        sys.exit("needs numpy + opencv (pip install numpy opencv-python)")
    if not a.check and not a.out:
        sys.exit("OUT is required (or --check)")
    if G.STILL_EXT(a.src):
        return still(a)
    if a.dur is None:
        sys.exit("--dur is required for a video")
    info = G.probe(a.src)
    W, H = (int(v) for v in a.size.lower().split("x"))
    span, speed, fpsf, fps_note = target_span(info, a.dur, a.fps, a.fps_mode)
    have = info["dur"] - a.tin
    dur = a.dur
    if span > have + 1e-3:
        if not a.fit:
            sys.exit(f"{os.path.basename(a.src)}: needs {span:.2f} s of source after {a.tin:.2f} s, has {have:.2f} s "
                     f"(max output {have * a.dur / span:.2f} s). Move --in earlier, shorten the slot, or pass --fit. Never pad.")
        dur = round(have * a.dur / span - 1 / a.fps, 3)
        span = have - 1e-3
    hdr = G.is_hdr(info)
    transfer = info["transfer"] if info["transfer"] in ("arib-std-b67", "smpte2084") else None
    crop = crop_expr(info, (W, H), [float(v) for v in a.focus.split(",")], a.crop)
    kind = G.guess_kind(a.src) if a.kind == "auto" else a.kind
    rep = {"src": os.path.abspath(a.src), "kind": kind, "in": a.tin, "source_span": round(span, 3), "out_dur": dur, "fps": fps_note, "speed": round(speed, 4),
           "hdr": hdr, "transfer": info["transfer"], "src_size": f"{info['w']}x{info['h']}", "src_fps": round(info["fps"], 3), "crop": crop}
    p = None
    if not a.no_grade and (a.ref or a.ref_stats):
        ref = json.load(open(a.ref_stats, encoding="utf-8")) if a.ref_stats else G.plate_stats(a.ref)
        ts = [a.tin + span * (i + 0.5) / 6 for i in range(6)]
        fr = G.sample_frames(a.src, ts, crop=crop)
        p, before, after = G.solve(fr, ref, strength=a.strength, transfer=transfer, sat_target=a.sat_target)
        d0, f0, w0 = G.compare(before, ref)
        d1, f1, w1 = G.compare(after, ref)
        rep["grade"] = {"ref": a.ref or a.ref_stats, "ref_stats": {k: round(v, 2) for k, v in ref.items()}, "params": {k: round(v, 3) for k, v in p.items()},
                        "before": d0, "before_fail": f0, "after": d1, "after_fail": f1, "after_warn": w1,
                        "verdict": "fail: another world, pick another shot" if f1 else "pass"}
    elif transfer:
        p = dict(G.IDENT)        # tone-map only
    if kind == "own":
        rep["people"] = people_check(a.src, a.tin, span)
    vision_gate(a, rep, a.tin, span)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if kind == "own" and rep["people"].startswith("SOMEONE ELSE") and not a.people_ok:
        sys.exit(f"{os.path.basename(a.src)} {a.tin:.2f}+{span:.2f} s: {rep['people']}. Pick another window, or pass --people-ok once "
                 "the user has confirmed who it is (own_footage.py sheet shows them the frames).")
    if a.check:
        return
    vf = [crop]
    lut = None
    matrix = ":in_color_matrix=bt2020" if hdr else ""
    if p is not None:
        lut = tempfile.NamedTemporaryFile(suffix=".cube", delete=False).name
        G.write_cube(lut, p, transfer)
        vf += [f"scale={W}:{H}:flags=lanczos+{G.SCALE_FLAGS}{matrix}", "format=rgb48le", f"lut3d=file='{G.filter_path(lut)}':interp=tetrahedral",
               f"scale=out_color_matrix=bt709:out_range=tv:flags={G.SCALE_FLAGS}"]
    else:
        vf += [f"scale={W}:{H}:flags=lanczos+{G.SCALE_FLAGS}:out_range=tv"]
    vf += [fpsf, "setsar=1", "format=yuv420p",
           "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"]   # an HLG source's frame tags would survive -color_trc
    g = int(round(a.fps))
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{a.tin:.3f}", "-t", f"{span + 0.5 / info['fps']:.3f}", "-i", a.src, "-an",
           "-vf", ",".join(vf), "-r", f"{a.fps:g}", "-frames:v", str(int(round(dur * a.fps))),
           "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf), "-g", str(g), "-keyint_min", str(g), "-sc_threshold", "0", "-bf", "2",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    if lut:
        os.unlink(lut)
    o = G.probe(a.out)
    rep["written"] = {"path": os.path.abspath(a.out), "dur": round(o["dur"], 3), "size": f"{o['w']}x{o['h']}", "fps": round(o["fps"], 3), "transfer": o["transfer"]}
    json.dump(rep, open(a.out + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if rep.get("vision_ok"):
        import broll_vision as BV
        BV.confirm(a.out, rep["vision_ok"])      # the prepared clip is what broll_qa.py checks
    print(f"-> {a.out} ({o['dur']:.2f} s, {o['w']}x{o['h']} @ {o['fps']:g}); {fps_note}" + (f"; grade {rep['grade']['verdict']}" if "grade" in rep else ""))


def vision_gate(a, rep, tin, span):
    """the B-roll people rules (people-rules.json); the shot shows its line.
    A shot that breaks them is refused here, before it is prepared (broll_vision.py; broll_qa.py checks the render again)."""
    if a.no_vision:
        rep["vision"] = "skipped"
        return
    import broll_vision as BV
    r = BV.check(a.src, tin, span, a.line)
    rep["vision"] = r
    if "error" in r:
        print(f"WARNING: vision check unavailable ({r['error']}); broll_qa.py will fail this shot until it is checked", file=sys.stderr)
        return
    bad = BV.bad(r)
    if bad and a.vision_ok:
        BV.confirm(a.src, a.vision_ok)      # the user's OK, recorded where broll_qa.py reads it
    if bad and not a.vision_ok:
        sys.exit(f"{os.path.basename(a.src)}: {BV.verdict(r)}. People: {r['people']}. The rules: {BV.RULES['summary']}; every shot "
                 "shows its line. Pick another shot; --vision-ok 'note' only after the user looked.")
    if bad:
        rep["vision_ok"] = a.vision_ok


def people_check(src, tin, span):
    """own footage: only the speaker may appear (YuNet + SFace vs library/me/face_ref.npz; own_footage.py me builds it)"""
    try:
        import own_footage as OF
        v, hits, _ = OF.check_window(src, tin, span, OF.load_ref())
    except SystemExit as e:
        return f"unchecked ({e})"
    other = [h for h in hits if h[1] == "other"]
    return f"SOMEONE ELSE at {other[0][0]:.2f} s (cosine {other[0][2]})" if other else v


def still(a):
    """grade a still (an AI still, a photo card) onto the plate: same stats, same bands, written as an image"""
    import numpy as np
    im = G.cv2.imread(a.src, G.cv2.IMREAD_COLOR)
    if im is None:
        sys.exit(f"unreadable image: {a.src}")
    ref = json.load(open(a.ref_stats, encoding="utf-8")) if a.ref_stats else G.plate_stats(a.ref)
    rgb = im[..., ::-1].astype(np.float32) / 255.0
    small = G.cv2.resize(rgb, (270, max(2, int(270 * im.shape[0] / im.shape[1]))), interpolation=G.cv2.INTER_AREA)
    p, before, after = G.solve([small], ref, strength=a.strength, sat_target=a.sat_target)
    d0, f0, _ = G.compare(before, ref)
    d1, f1, w1 = G.compare(after, ref)
    rep = {"src": os.path.abspath(a.src), "kind": G.guess_kind(a.src) if a.kind == "auto" else a.kind, "grade": {"params": {k: round(v, 3) for k, v in p.items()}, "before": d0, "before_fail": f0,
                                                    "after": d1, "after_fail": f1, "after_warn": w1, "verdict": "fail: another world" if f1 else "pass"}}
    vision_gate(a, rep, 0.0, None)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if a.check:
        return
    out = (G.apply_lab(rgb, p)[..., ::-1] * 255 + 0.5).clip(0, 255).astype(np.uint8)
    G.cv2.imwrite(a.out, out, [G.cv2.IMWRITE_JPEG_QUALITY, 95])
    json.dump(rep, open(a.out + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if rep.get("vision_ok"):
        import broll_vision as BV
        BV.confirm(a.out, rep["vision_ok"])
    print(f"-> {a.out}; grade {rep['grade']['verdict']}")


if __name__ == "__main__":
    main()
