#!/usr/bin/env python3
"""Render report: pass/fail per check on a finished render, a suggested fix for every failure,
and the round counter for the fix-and-re-render loop (at most 3 rounds).

    render_report.py <project> <render.mp4> [--upstream build/edl_map.json] [--stem build/sfx_stem.mp4]
                     [--out build/render-report.json] [--no-html] [--max-rounds 3]

Checks (each: pass | warn | fail | skip, value, target, details, fix):
  streams      1080x1920, 30 fps, H.264 yuv420p, an audio stream
  duration     render vs the build's planned total (reel.json takes + holds + outro)
  av_sync      video and audio both start at 0 and end within a frame of each other
  loudness     integrated -16..-13.5 LUFS pass (-17.5..-12.5 warn); true peak <= -1 dBTP pass (<= -0.5 warn)
  black        black frames >= 0.1 s
  frozen       frozen picture >= 0.5 s over the speaker (a stalled video track); long still scenes are a warning
  silences     silences > 0.8 s inside the speech (holds excluded), mapped to the take and its original time
  captions     caption blocks from build/caption_layout.json: outside the platform safe area (fail),
               close-up fallback under the mouth (warn), shrunk blocks (warn)
  hook         first 1.5 s: text on screen (captions or a beat) and motion (frame difference or a cut)
  sfx_levels   each SFX hit vs the voice on the SFX-only stem, when a fresh stem exists (qa.py renders one)
  build_match  the render is newer than the build and the build is the one approved on the approval sheet
  bq_*         broll_qa.py (references/broll.md): full-screen B-roll, face on screen, inserts per minute, insert grade
               vs the plate, graphic scenes' length and motion, caption size and contrast (OCR), nothing over a face,
               frozen frames, HDR output, plate keyframes. --broll-profile talking-head|tutorial|broll-led|graphics (default:
               reel.json "broll_profile", else broll-led for seoul-list / pov-montage, tutorial for stan-style panels);
               --no-broll skips it. Its full result: build/broll-qa.json + broll-qa-timeline.png.
Writes build/render-report.json (+ render-report.html). Exit code 1 when any check fails.
"""
import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from reelproj import beats_timeline, ffprobe_json, fmt_t, load_project, predicted_silences, sh  # noqa: E402

esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731
MAX_ROUNDS = 3


def chk(cid, title, status, value=None, target=None, details=None, fix=None, auto=False, times=None):
    return {"id": cid, "title": title, "status": status, "value": value, "target": target, "details": details or [],
            "fix": fix, "fix_auto": auto, "times": times or []}


def where(pr, te):
    """Edit time -> 'take k, orig X s (raw Y s)' for fix messages."""
    orig, ti, kind = pr.to_orig(te)
    raw, _ = pr.to_raw(orig) if kind == "take" else (None, None)
    s = f"take {ti} at orig {orig:.2f} s" if kind == "take" else f"{kind} after take {ti}"
    return s + (f" (raw {raw:.2f} s)" if raw is not None else ""), orig, ti, raw


# ------------------------------------------------------------------ analysis
def analyse(video):
    """One decode pass: black/freeze on a small picture, loudness curve, true peak, silences."""
    fc = ("[0:v]scale=270:480,blackdetect=d=0.1:pix_th=0.06:pic_th=0.98,freezedetect=n=-55dB:d=0.5[v];"
          "[0:a]silencedetect=noise=-38dB:d=0.8,ebur128=peak=true:framelog=info[a]")
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-f", "null", "-"])
    e = r.stderr
    out = {"black": [], "freeze": [], "silence": [], "curve": []}
    for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)", e):
        out["black"].append((float(m.group(1)), float(m.group(2))))
    fs = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", e)]
    fe = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", e)]
    out["freeze"] = [(a, fe[i] if i < len(fe) else None) for i, a in enumerate(fs)]
    ss = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    se = re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", e)
    out["silence"] = [(max(0.0, a), float(se[i][0]) if i < len(se) else None) for i, a in enumerate(ss)]
    for m in re.finditer(r"t:\s*([\d.]+)\s+TARGET:\S+ LUFS\s+M:\s*(-?[\d.]+|-inf)", e):
        out["curve"].append((float(m.group(1)), float(m.group(2)) if m.group(2) != "-inf" else -70.0))
    summ = e[e.rfind("Summary:"):] if "Summary:" in e else ""
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    lra = re.search(r"LRA:\s+(-?[\d.]+) LU", summ)
    tp = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS", summ)
    out["I"] = float(i.group(1)) if i else None
    out["LRA"] = float(lra.group(1)) if lra else None
    out["TP"] = float(tp.group(1)) if tp and tp.group(1) != "-inf" else None
    return out


def first_frames(video, secs=1.6, w=108, h=192):
    raw = sh_bytes(["ffmpeg", "-v", "error", "-t", str(secs), "-i", video, "-vf", f"fps=10,scale={w}:{h},format=gray", "-f", "rawvideo", "-"])
    n = len(raw) // (w * h)
    return np.frombuffer(raw[: n * w * h], np.uint8).reshape(n, h, w).astype(np.float32)


def sh_bytes(cmd):
    import subprocess
    return subprocess.run(cmd, capture_output=True).stdout


def thumb(video, t, w=216):
    data = sh_bytes(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", video, "-frames:v", "1", "-vf", f"scale={w}:-2", "-q:v", "5", "-f", "image2", "-c:v", "mjpeg", "-"])
    return base64.b64encode(data).decode() if data else None


# ------------------------------------------------------------------ checks
def run_checks(pr, video, an, info, stem, approval):
    C = []
    vs = [s for s in info.get("streams", []) if s["codec_type"] == "video"]
    au = [s for s in info.get("streams", []) if s["codec_type"] == "audio"]
    dur = float(info.get("format", {}).get("duration", 0))
    beats = beats_timeline(pr)
    full = [(b["t0"], b["t1"], b) for b in beats if b["t0"] is not None and b["full"]]
    holds = [(k.hold_start, k.hold_start + k.hold) for k in pr.takes if k.hold] + ([(pr.speech, pr.total)] if pr.outro else [])

    # streams
    v = vs[0] if vs else {}
    fr = v.get("r_frame_rate", "0/1").split("/")
    fps = float(fr[0]) / float(fr[1] or 1)
    det = [f"video {v.get('codec_name')} {v.get('width')}x{v.get('height')} {v.get('pix_fmt')} {fps:g} fps",
           f"audio {au[0].get('codec_name')} {au[0].get('sample_rate')} Hz {au[0].get('channels')} ch" if au else "audio: none"]
    bad = []
    if (v.get("width"), v.get("height")) != (1080, 1920):
        bad.append("not 1080x1920")
    if abs(fps - pr.fps) > 0.01:
        bad.append(f"{fps:g} fps, build is {pr.fps}")
    if v.get("codec_name") != "h264" or v.get("pix_fmt") != "yuv420p":
        bad.append("not H.264 yuv420p (Instagram re-encodes anything else)")
    if not au:
        bad.append("no audio stream")
    C.append(chk("streams", "Streams", "fail" if bad else "pass", f"{v.get('width')}x{v.get('height')} {fps:g} fps", f"1080x1920 {pr.fps} fps h264 + audio",
                 det + bad, "Re-render with `npx hyperframes render -o build/reel.mp4` (mp4 is H.264 yuv420p); the composition must be 1080x1920." if bad else None))

    # duration
    d = dur - pr.total
    st = "pass" if abs(d) <= 0.1 else "warn" if abs(d) <= 0.5 else "fail"
    C.append(chk("duration", "Duration", st, round(dur, 3), f"{pr.total} s (build) ±0.1", [f"render {dur:.3f} s, build plans {pr.total} s ({len(pr.takes)} takes, speech {pr.speech:.2f} s, outro {pr.outro} s)"],
                 None if st == "pass" else "Rebuild (`node build.mjs <project>`) and re-render: the render is from an older build or was cut short (read the render log).", auto=True))

    # av sync
    if vs and au:
        vst, ast = float(v.get("start_time", 0)), float(au[0].get("start_time", 0))
        vd, ad = float(v.get("duration", dur)), float(au[0].get("duration", dur))
        off = max(abs(vst - ast), abs(vd - ad))
        st = "pass" if abs(vst - ast) < 0.005 and abs(vd - ad) <= 1.5 / pr.fps else "warn" if off < 0.1 else "fail"
        C.append(chk("av_sync", "A/V alignment", st, f"start {vst:.3f}/{ast:.3f}, end diff {vd - ad:+.3f} s", "both start at 0, ends within a frame",
                     [], None if st == "pass" else "Streams drift: re-render; if the source was concat-cut, rebuild it with frame-snapped segments (recipes/clean-os/assemble.py).", auto=True))

    # loudness
    I, TP = an["I"], an["TP"]
    if I is None:
        C.append(chk("loudness", "Loudness", "skip", None, "-16..-13.5 LUFS", ["ebur128 gave no summary"]))
    else:
        si = "pass" if -16.5 <= I <= -13.5 else "warn" if -17.5 <= I <= -12.5 else "fail"
        stp = "pass" if TP is None or TP <= -1.0 else "warn" if TP <= -0.5 else "fail"
        st = max([si, stp], key=["pass", "warn", "fail"].index)
        fixes = []
        if si != "pass":
            fixes.append("Integrated loudness is set by the voice in prep.sh (-16 LUFS); re-run prep.sh on the source rather than adding gain to the mix."
                         + (" If music or SFX lift it, lower music.db by 2 dB or mix.roleDb." if I > -13.5 else ""))
        if stp != "pass":
            fixes.append("True peak too hot: `qa.py <project> <render> --fix out.mp4` applies a gentle limiter (never gain); or lower roleDb.impact by 2 dB and rebuild.")
        C.append(chk("loudness", "Loudness", st, f"{I} LUFS, TP {TP} dBTP, LRA {an['LRA']} LU", "I -16..-13.5 LUFS, TP <= -1 dBTP", [], " ".join(fixes) or None, auto=stp != "pass" and si == "pass"))

    # black frames
    bl = [(a, b) for a, b in an["black"]]
    det, times = [], []
    for a, b in bl:
        w, *_ = where(pr, a)
        on = next((bb for x, y, bb in full if x <= a <= y), None)
        det.append(f"{fmt_t(a)} to {fmt_t(b)} ({b - a:.2f} s): {w}" + (f", under #{on['i']} {on['label']}" if on else ""))
        times.append(a)
    C.append(chk("black", "Black frames", "fail" if bl else "pass", len(bl), "none >= 0.1 s", det,
                 "A black stretch means missing media or a beat outside the source: check the beat/take at that time "
                 "(asset path in assets/, `data-media-start` past the clip end), rebuild, re-render." if bl else None, auto=True, times=times))

    # frozen frames
    hard, soft, det, times = [], [], [], []
    for a, b in an["freeze"]:
        b = b if b is not None else dur
        cover = [(x, y) for x, y, _ in full] + holds
        # the part of the freeze that is over the speaker (not a scene, not a hold/outro)
        exposed = b - a
        for x, y in cover:
            exposed -= max(0.0, min(b, y) - max(a, x))
        w, *_ = where(pr, a)
        if exposed >= 0.5:
            hard.append((a, b))
            det.append(f"{fmt_t(a)} to {fmt_t(b)} ({b - a:.2f} s, {exposed:.2f} s over the speaker): {w}")
            times.append(a)
        elif b - a >= 2.5:
            on = next((bb for x, y, bb in full if x - 0.1 <= a <= y), None)
            soft.append((a, b))
            det.append(f"{fmt_t(a)} to {fmt_t(b)}: a still {'scene #' + str(on['i']) + ' ' + on['label'] if on else 'hold'} for {b - a:.1f} s")
            times.append(a)
    st = "fail" if hard else "warn" if soft else "pass"
    fix = None
    if hard:
        fix = ("The speaker's video stalled: every <video> needs an id and a source that covers data-media-start + duration; "
               "re-render with --no-best-effort to surface missing media, or --video-frame-format png.")
    elif soft:
        fix = "A full-screen scene holds still: end it earlier (`to`), add a slow push, or land the next word sooner."
    C.append(chk("frozen", "Frozen frames", st, f"{len(hard)} stalled, {len(soft)} long stills", "no freeze >= 0.5 s over the speaker", det, fix, auto=True, times=times))

    # silences inside speech: dead air in the mix, plus pauses in the VOICE track (the takes' source audio,
    # which is what the render plays) that a music bed would hide from a mix-level silence detector
    det, times, fixes = [], [], []
    gaps = []
    for a, b in an["silence"]:
        if b is None or a >= pr.speech:
            continue
        gaps.append((a, min(b, pr.speech), "dead air"))
    for a, b in predicted_silences(pr):
        if not any(x < b and a < y for x, y, _ in gaps):
            gaps.append((a, b, "voice pause under the music" if pr.spec.get("music") else "voice pause"))
    for a, b, kind in sorted(gaps):
        if b - a < 0.8 or any(x - 0.05 <= a and b <= y + 0.05 for x, y in holds):
            continue
        w, orig, ti, raw = where(pr, a)
        k = pr.takes[ti]
        o_end = orig + (b - a)
        det.append(f"{fmt_t(a)} to {fmt_t(b)} ({b - a:.2f} s, {kind}): {w}")
        times.append(a)
        k_end = k.start + k.dur
        if b > k_end + 0.05 and ti + 1 < len(pr.takes):  # the pause runs across the cut into the next take
            k2 = pr.takes[ti + 1]
            a2 = k2.a + (b - k_end)
            fixes.append(f"take {ti}: end it earlier, b = {orig + 0.25:.2f}" + (f"; take {ti + 1}: start it later, a = {a2 - 0.12:.2f}" if a2 - 0.12 > k2.a + 0.02 else ""))
        elif o_end >= k.b - 0.3:
            fixes.append(f"take {ti}: end it earlier, b = {orig + 0.25:.2f}")
        elif orig <= k.a + 0.3:
            fixes.append(f"take {ti}: start it later, a = {o_end - 0.12:.2f}")
        else:
            fixes.append(f"take {ti}: split it around the pause, {{a: {k.a}, b: {orig + 0.25:.2f}}} + {{a: {o_end - 0.12:.2f}, b: {k.b}}}"
                         + (f" (in the pre-cut source: raw {raw:.2f} s)" if raw is not None else ""))
    C.append(chk("silences", "Silences inside the speech", "fail" if det else "pass", len(det), "no dead air or voice pause > 0.8 s (holds excluded)", det,
                 ("; ".join(fixes) + ". Keep about 0.2 s of breath; cut only pauses longer than 0.7 s inside a line.") if fixes else None, auto=True, times=times))

    # captions
    lay = pr.layout
    if not lay:
        C.append(chk("captions", "Captions and safe area", "skip", None, None, ["no build/caption_layout.json; run face_track.py and rebuild"]))
    else:
        stp, sbt = lay["safeTop"], lay["safeBottom"]
        off = [b for b in lay["blocks"] if b["y"] < stp or b["y"] + b["h"] * b.get("scale", 1) > sbt + 1]
        low = [b for b in lay["blocks"] if b["mode"] == "lower-face"]
        tiny = [b for b in lay["blocks"] if b.get("scale", 1) < 0.85]
        modes = {}
        for b in lay["blocks"]:
            modes[b["mode"]] = modes.get(b["mode"], 0) + 1
        det = [f"{len(lay['blocks'])} blocks, {lay['platform']['name']} safe y {stp}-{sbt}: {modes}"]
        det += [f"outside the safe area at {fmt_t(b['t0'])} (y {b['y']}..{b['y'] + b['h']})" for b in off]
        det += [f"close-up fallback at {fmt_t(b['t0'])} (under the mouth on a backing)" for b in low]
        det += [f"shrunk to {b['scale']:.0%} at {fmt_t(b['t0'])}" for b in tiny]
        st = "fail" if off else "warn" if low or tiny else "pass"
        fix = None
        if off:
            fix = "Captions leave the safe area: lower captions.y / brand.capSize, or set layout.capBottom; rebuild (the placer clamps to the platform)."
        elif low or tiny:
            fix = "The face fills the frame there: drop the push-in at that time or move the block's text into a full-screen scene."
        C.append(chk("captions", "Captions and safe area", st, modes, "all inside the safe area, below the chin", det, fix, auto=True,
                     times=[b["t0"] for b in off + low + tiny]))

    # hook: text and motion in the first 1.5 s
    groups = (lay or {}).get("blocks", [])
    first_cap = min((b["t0"] for b in groups), default=None)
    if first_cap is None and pr.words_edit:
        first_cap = pr.words_edit[0]["start"]
    first_beat = min((b["t0"] for b in beats if b["t0"] is not None and b["texts"]), default=None)
    first_text = min([x for x in (first_cap, first_beat) if x is not None], default=None)
    fr = first_frames(video)
    motion = float(np.percentile(np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2)), 90)) if len(fr) > 1 else 0.0
    events = [c["t"] for c in pr.cuts() if c["t"] <= 1.5] + [b["t0"] for b in beats if b["t0"] is not None and b["t0"] <= 1.5]
    z = pr.spec.get("zoom") or {}
    events += [pr.E_safe(t) for t, _ in (z.get("snaps") or []) if (pr.E_safe(t) or 99) <= 1.5]
    events += [pr.E_safe(p["at"]) for p in (z.get("pushes") or []) if (pr.E_safe(p["at"]) or 99) <= 1.5]
    first_luma = float(fr[0].mean()) if len(fr) else 0.0
    has_text = first_text is not None and first_text <= 1.5
    has_motion = motion >= 1.5 or bool(events)
    words3 = " ".join(w["word"] for w in pr.words_edit if w["start"] < 3.0)
    first_word = pr.words_edit[0]["start"] if pr.words_edit else None
    det = [f"first text on screen at {first_text:.2f} s" if first_text is not None else "no text on screen found",
           f"motion: frame difference p90 {motion:.1f} (>= 1.5 reads as moving){'; edit events at ' + ', '.join(f'{x:.2f}' for x in events) + ' s' if events else ''}",
           f"first frame mean luma {first_luma:.0f}/255", f"voice starts at {first_word:.2f} s" if first_word is not None else "no words",
           f"first 3 s says: \"{words3}\""]
    st = "pass" if has_text and has_motion else "warn" if has_text or has_motion else "fail"
    if first_luma < 12:
        st = "fail"
        det.append("the first frame is black")
    fixes = []
    if not has_text:
        fixes.append("Put text on screen by 1.5 s: start captions on the first word, or open on a hook card/title on the first spoken word.")
    if not has_motion:
        fixes.append(f"Nothing moves in the first 1.5 s: open on a snap (zoom.snaps [[{pr.takes[0].a}, 1.1]]) or a scene in-transition.")
    if first_word is not None and first_word > 0.5:
        fixes.append(f"Dead air at the start: set take 0 a = {pr.takes[0].a + first_word - 0.1:.2f}.")
        st = "fail" if st == "fail" else "warn"
    C.append(chk("hook", "First 1.5 s (hook)", st, {"text_at": first_text, "motion": round(motion, 2)}, "text and motion by 1.5 s", det,
                 " ".join(fixes) or None, auto=True, times=[0.0, 0.5, 1.0, 1.5]))

    # sfx levels on the stem
    if stem and os.path.exists(stem) and pr.sfx:
        SR = 48000
        sx = np.frombuffer(sh_bytes(["ffmpeg", "-v", "error", "-i", stem, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]), np.float32)
        vp, roles = pr.sfx["voiceP95"], pr.sfx["roleDb"]
        det, loud, quiet, off = [], [], [], []
        for e in pr.sfx["events"]:
            i = int(e["t"] * SR)
            seg = sx[i:i + int((min(e["dur"], 3.0) + 0.1) * SR)]
            p = 20 * np.log10(max(float(np.abs(seg).max()) if len(seg) else 0, 1e-9))
            rel = p - vp
            tg = roles.get(e["role"], -12)
            if rel > 1.5:
                loud.append(e)
                det.append(f"{fmt_t(e['t'])} {e['id']} {rel:+.1f} dB vs voice (louder than the voice)")
            elif rel < -22:
                quiet.append(e)
                det.append(f"{fmt_t(e['t'])} {e['id']} {rel:+.1f} dB vs voice (inaudible)")
            elif abs(rel - tg) > 4:
                off.append(e)
        st = "fail" if loud or quiet else "warn" if len(off) > max(2, len(pr.sfx["events"]) // 5) else "pass"
        det.insert(0, f"{len(pr.sfx['events'])} hits vs voice p95 {vp} dBFS; {len(off)} more than 4 dB off their role target (often overlapping hits)")
        C.append(chk("sfx_levels", "SFX vs voice", st, f"{len(loud)} loud, {len(quiet)} inaudible, {len(off)} off target", "within role targets", det,
                     "Never hand-tune data-volume: set the beat's sfx to a quieter variant, `db` on a manual sfx, or mix.roleDb, then rebuild." if st != "pass" else None,
                     auto=True, times=[e["t"] for e in loud + quiet]))
    else:
        C.append(chk("sfx_levels", "SFX vs voice", "skip", None, None, ["no fresh SFX-only stem; `qa.py <project> <render>` renders one (slow), or pass --stem"]))

    # the build behind the render
    idx = os.path.join(pr.path, "index.html")
    det, st = [], "pass"
    if os.path.exists(idx) and os.path.getmtime(video) < os.path.getmtime(idx):
        st = "warn"
        det.append("the render is older than index.html: it may not show the current build")
    if approval is None:
        st = "warn" if st == "pass" else st
        det.append("no approval sheet for this build (approval_sheet.py)")
    else:
        from approval_sheet import build_hash  # noqa: E402
        h = build_hash(pr.path)
        if approval.get("hash") != h:
            st = "warn"
            det.append(f"the build changed since the approval sheet ({approval.get('hash')} -> {h})")
        elif not approval.get("approved"):
            st = "warn"
            det.append(f"approval sheet {h} made but not approved (approval_sheet.py <project> --mark-approved after the user's yes)")
        else:
            det.append(f"build {h} approved at {approval.get('approved_at')}")
    C.append(chk("build_match", "Render matches the approved build", st, None, "render newer than the build; build approved", det,
                 "Re-render from the current build after the approval sheet is approved." if st != "pass" else None))
    return C


# ------------------------------------------------------------------ html
def report_html(rep, pr, video, an):
    STC = {"pass": "#34d399", "warn": "#fbbf24", "fail": "#f87171", "skip": "#6b7280"}
    s = rep["summary"]
    title = pr.spec.get("title") or os.path.basename(pr.path)
    o = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Render report: {esc(title)}</title><style>'
         ':root{--bg:#0d0f13;--panel:#151820;--panel2:#1b1f29;--line:#272c38;--ink:#e9ebf0;--mute:#9aa1b0;--faint:#6b7280}'
         '*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Inter","Segoe UI",Roboto,sans-serif}'
         'main{max-width:1100px;margin:0 auto;padding:28px 16px 60px}h1{font-size:25px;margin:2px 0 6px;letter-spacing:-.3px}h2{font-size:14px;text-transform:uppercase;letter-spacing:.12em;color:var(--mute);margin:34px 0 12px}'
         '.sub{color:var(--mute);font-size:13px}.mono{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}'
         '.pill{display:inline-block;font-weight:800;letter-spacing:.06em;border-radius:999px;padding:4px 12px;font-size:13px;color:#0b0d12}'
         '.facts{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.f{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px}.f b{display:block;font-size:17px}.f span{color:var(--mute);font-size:12px}'
         '.next{margin-top:16px;background:var(--panel);border:1px solid var(--line);border-left:4px solid VAR;border-radius:10px;padding:12px 14px}'
         '.c{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--faint);border-radius:10px;padding:12px 14px;margin-bottom:10px}'
         '.c .h{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}.c .st{font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}'
         '.c .t{font-weight:650}.c .v{color:var(--mute);font-size:13px}.c ul{margin:6px 0 0;padding-left:18px;color:#cfd3dc;font-size:13px}'
         '.fix{margin-top:8px;background:var(--panel2);border-radius:8px;padding:8px 10px;font-size:13px}.fix b{color:#93c5fd}'
         '.strip{display:flex;gap:10px;flex-wrap:wrap}.strip figure{margin:0}.strip img{width:150px;border-radius:8px;display:block;border:1px solid var(--line)}.strip figcaption{font:11px ui-monospace,Menlo,monospace;color:var(--mute);margin-top:4px}'
         '.chart{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px}.chart svg{width:100%;display:block}'
         '</style></head><body><main>'.replace("VAR", STC["pass" if s["status"] == "pass" else "fail"])]
    o.append(f'<div class="sub">render report · round {rep["round"]} of {rep["max_rounds"]} · {esc(rep["created"])}</div><h1>{esc(title)}</h1>')
    o.append(f'<span class="pill" style="background:{STC[s["status"]]}">{s["status"].upper()}</span> <span class="sub">{s["pass"]} pass · {s["warn"]} warn · {s["fail"]} fail · {s["skip"]} skipped</span>')
    o.append(f'<div class="sub mono" style="margin-top:6px">{esc(video)}</div><div class="facts">')
    fx = rep["facts"]
    for v, k in [(fmt_t(fx["duration"]), "duration"), (f'{fx["I"]} LUFS', "integrated"), (f'{fx["TP"]} dBTP', "true peak"), (f'{fx["LRA"]} LU', "range"),
                 (f'{fx["width"]}x{fx["height"]}', f'{fx["fps"]:g} fps'), (f'{fx["size_mb"]} MB', "file")]:
        o.append(f'<div class="f"><b>{esc(v)}</b><span>{esc(k)}</span></div>')
    nx = rep["next"].split(": ", 1)
    body = "<br>".join("· " + esc(x) for x in nx[1].split(" | ")) if len(nx) > 1 and " | " in nx[1] else esc(nx[1]) if len(nx) > 1 else ""
    o.append(f'</div><div class="next"><b>Next: {esc(nx[0])}</b>{"<br>" + body if body else ""}</div>')
    # loudness curve
    cv = an["curve"]
    if cv:
        W, H, T = 1000, 150, max(fx["duration"], 0.1)
        X = lambda t: 40 + (W - 50) * t / T  # noqa: E731
        Y = lambda l: 10 + (H - 30) * (max(-50.0, min(-5.0, l)) - -5.0) / -45.0  # noqa: E731
        pts = " ".join(f"{X(t):.1f},{Y(m):.1f}" for t, m in cv[::2])
        g = [f'<svg viewBox="0 0 {W} {H}">']
        for l in (-10, -16, -30, -45):
            g.append(f'<line x1="40" x2="{W - 10}" y1="{Y(l):.1f}" y2="{Y(l):.1f}" stroke="{"#34d39966" if l == -16 else "#272c38"}" stroke-dasharray="{"" if l == -16 else "3 3"}"/><text x="2" y="{Y(l) + 4:.1f}" fill="#6b7280" font-size="10">{l}</text>')
        for c in rep["checks"]:
            if c["id"] in ("silences", "black", "frozen") and c["status"] in ("fail", "warn"):
                for t in c["times"]:
                    g.append(f'<rect x="{X(t):.1f}" y="10" width="4" height="{H - 30}" fill="{STC[c["status"]]}" opacity=".5"/>')
        g.append(f'<rect x="{X(pr.speech):.1f}" y="10" width="{max(0, X(T) - X(pr.speech)):.1f}" height="{H - 30}" fill="#5b4a2a" opacity=".35"/>' if pr.outro else "")
        g.append(f'<polyline points="{pts}" fill="none" stroke="#93c5fd" stroke-width="1.4"/>')
        t = 0
        while t <= T:
            g.append(f'<text x="{X(t):.1f}" y="{H - 4}" fill="#6b7280" font-size="10">{int(t)}s</text>')
            t += 10
        g.append("</svg>")
        o.append('<h2>Momentary loudness (LUFS)</h2><div class="chart">' + "".join(g) + '</div><div class="sub">green line: the -16 LUFS voice target; marks: flagged times</div>')
    # first 1.5 s
    o.append('<h2>First 1.5 seconds</h2><div class="strip">')
    for t in (0.0, 0.5, 1.0, 1.5):
        b = thumb(video, t, 300)
        if b:
            o.append(f'<figure><img src="data:image/jpeg;base64,{b}" alt="{t} s"><figcaption>{t:.1f} s</figcaption></figure>')
    o.append("</div>")
    o.append("<h2>Checks</h2>")
    for c in sorted(rep["checks"], key=lambda c: ["fail", "warn", "pass", "skip"].index(c["status"])):
        o.append(f'<div class="c" style="border-left-color:{STC[c["status"]]}"><div class="h"><span class="st" style="color:{STC[c["status"]]}">{c["status"]}</span>'
                 f'<span class="t">{esc(c["title"])}</span><span class="v">{esc(json.dumps(c["value"], ensure_ascii=False) if isinstance(c["value"], dict) else c["value"])}'
                 f'{" · want " + esc(c["target"]) if c["target"] else ""}</span></div>')
        if c["details"]:
            o.append("<ul>" + "".join(f"<li>{esc(d)}</li>" for d in c["details"][:12]) + (f"<li>+{len(c['details']) - 12} more</li>" if len(c["details"]) > 12 else "") + "</ul>")
        if c["fix"]:
            o.append(f'<div class="fix"><b>Fix{" (agent can apply)" if c["fix_auto"] else " (ask the user)"}:</b> {esc(c["fix"])}</div>')
        if c["status"] == "fail" and c["times"] and c["id"] != "hook":
            o.append('<div class="strip" style="margin-top:8px">')
            for t in c["times"][:6]:
                b = thumb(video, t + 0.05)
                if b:
                    o.append(f'<figure><img src="data:image/jpeg;base64,{b}" style="width:110px" alt=""><figcaption>{fmt_t(t)}</figcaption></figure>')
            o.append("</div>")
        o.append("</div>")
    if rep["history"]:
        o.append("<h2>Rounds</h2><div class='sub'>" + "<br>".join(f"round {h['round']}: {h['status']} {', '.join(h['fail']) if h['fail'] else ''} ({h['created']})" for h in rep["history"]) + "</div>")
    o.append(f'<p class="sub" style="margin-top:30px">render_report.py · {esc(pr.path)}</p></main></body></html>')
    return "".join(o)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("video")
    ap.add_argument("--skill")
    ap.add_argument("--upstream", help="cut list of a pre-cut source (build/edl_map.json or cut.json)")
    ap.add_argument("--stem", help="SFX-only stem render (default build/sfx_stem.mp4 when newer than sfx_events.json)")
    ap.add_argument("--out", help="report path (default <project>/build/render-report.json)")
    ap.add_argument("--no-html", action="store_true")
    ap.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    ap.add_argument("--broll-profile", choices=["talking-head", "tutorial", "broll-led", "graphics"])
    ap.add_argument("--no-broll", action="store_true", help="skip the B-roll and motion QA (broll_qa.py)")
    a = ap.parse_args()
    pr = load_project(a.project, a.skill, a.upstream)
    video = os.path.abspath(a.video)
    if not os.path.exists(video):
        sys.exit(f"no such render: {video}")
    out = a.out or os.path.join(pr.path, "build", "render-report.json")
    stem = a.stem
    ev_p = os.path.join(pr.path, "build", "sfx_events.json")
    dflt = os.path.join(pr.path, "build", "sfx_stem.mp4")
    if not stem and os.path.exists(dflt) and os.path.exists(ev_p) and os.path.getmtime(dflt) >= os.path.getmtime(ev_p):
        stem = dflt
    ap_p = os.path.join(pr.path, "build", "approval.json")
    approval = json.load(open(ap_p, encoding="utf-8")) if os.path.exists(ap_p) else None

    t0 = dt.datetime.now()
    info = ffprobe_json(video)
    print("analysing (one decode pass: black, freeze, loudness, silences)...")
    an = analyse(video)
    checks = run_checks(pr, video, an, info, stem, approval)
    if not a.no_broll:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import broll_qa
            prof = a.broll_profile or pr.spec.get("broll_profile") or \
                ("broll-led" if str(pr.spec.get("recipe", "")) in ("seoul-list", "pov-montage") else
                 "tutorial" if str(pr.spec.get("recipe", "")) == "stan-style" or any(b.get("type") == "panel" for b in pr.spec.get("beats", [])) else "talking-head")
            print(f"B-roll and motion QA (broll_qa.py, profile {prof})...")
            style = pr.spec.get("recipe") or ("stan-style" if prof == "tutorial" else None)
            bq = broll_qa.analyse(video, pr.path, prof, [{"w": w["word"], "s": w["start"], "e": w["end"]} for w in pr.words_edit], log=lambda *x: None,
                                  style=style if style and os.path.isdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "recipes", str(style))) else None)
            bp = os.path.join(pr.path, "build", "broll-qa.json")
            json.dump(bq, open(bp, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
            broll_qa.timeline_png(bq, os.path.splitext(bp)[0] + "-timeline.png")
            checks += [{**c, "id": "bq_" + c["id"]} for c in bq["checks"] if c["status"] != "skip"]
        except ImportError as e:
            checks.append(chk("bq", "B-roll and motion QA", "skip", f"needs numpy + opencv ({e}); run broll_qa.py in the media venv"))

    # round counter: a new render file (path or mtime) starts the next round
    prev = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else None
    mtime = os.path.getmtime(video)
    if prev and prev.get("render") == video and abs(prev.get("render_mtime", 0) - mtime) < 1e-3:
        rnd, hist = prev["round"], prev.get("history", [])[:-1]
    elif prev and prev.get("summary", {}).get("status") == "fail":
        rnd, hist = prev["round"] + 1, prev.get("history", [])
    else:
        rnd, hist = 1, []
    counts = {k: sum(1 for c in checks if c["status"] == k) for k in ("pass", "warn", "fail", "skip")}
    status = "fail" if counts["fail"] else "pass"
    fails = [c for c in checks if c["status"] == "fail"]
    if status == "pass":
        nxt = "deliver" + (f" (read the {counts['warn']} warning(s) first)" if counts["warn"] else "")
    elif rnd < a.max_rounds:
        nxt = f"fix and re-render (round {rnd + 1} of {a.max_rounds}): " + " | ".join(f"{c['id']}: {c['fix']}" for c in fails if c["fix"])
    else:
        nxt = f"stop: {a.max_rounds} rounds used. Hand the remaining failures ({', '.join(c['id'] for c in fails)}) to the user with this report."
    vs = [s for s in info.get("streams", []) if s["codec_type"] == "video"]
    fr = (vs[0].get("r_frame_rate", "0/1") if vs else "0/1").split("/")
    rep = {"tool": "render_report.py", "version": 1, "created": t0.isoformat(timespec="seconds"), "project": pr.path, "render": video,
           "render_mtime": mtime, "round": rnd, "max_rounds": a.max_rounds,
           "summary": {"status": status, **counts},
           "facts": {"duration": round(float(info.get("format", {}).get("duration", 0)), 3), "planned": pr.total, "speech": round(pr.speech, 3),
                     "I": an["I"], "TP": an["TP"], "LRA": an["LRA"], "width": vs[0].get("width") if vs else None, "height": vs[0].get("height") if vs else None,
                     "fps": float(fr[0]) / float(fr[1] or 1), "size_mb": round(os.path.getsize(video) / 1e6, 1)},
           "checks": checks, "fixes": [{"check": c["id"], "fix": c["fix"], "auto": c["fix_auto"]} for c in fails if c["fix"]],
           "next": nxt}
    rep["history"] = hist + [{"round": rnd, "created": rep["created"], "status": status, "fail": [c["id"] for c in fails]}]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(rep, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if not a.no_html:
        hp = os.path.splitext(out)[0] + ".html"
        open(hp, "w", encoding="utf-8").write(report_html(rep, pr, video, an))
    took = (dt.datetime.now() - t0).total_seconds()
    for c in checks:
        print(f"  {c['status'].upper():5s} {c['title']}: {c['value'] if not isinstance(c['value'], dict) else json.dumps(c['value'], ensure_ascii=False)}")
        if c["status"] in ("fail", "warn"):
            for d in c["details"][:4]:
                print(f"         {d}")
            if c["fix"]:
                print(f"         fix: {c['fix']}")
    print(f"\n{status.upper()} round {rnd} of {a.max_rounds} ({took:.0f} s). next: {nxt}")
    print(f"-> {out}" + ("" if a.no_html else f"\n-> {os.path.splitext(out)[0]}.html"))
    sys.exit(1 if status == "fail" else 0)


if __name__ == "__main__":
    main()
