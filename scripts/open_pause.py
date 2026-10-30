#!/usr/bin/env python3
"""Open a pause in a finished cut: let a take run on a little at a hard cut, using its own raw frames and room tone.

    open_pause.py PROJECT --raw RAW.MOV --at 38.87:0.6 [--at 50.2:1.2 ...]
                  [--plate assets/plate_alt.mp4] [--voice assets/voice.wav] [--words build/words.cut.json]
                  [--raw-audio full.wav] [--tag pause]       --at J:D:hold freezes instead of running on

After a take ends the speaker often looks down, lowers the mic or stands up (the reach to stop the camera): watch the
run-on (a 5 fps strip of the new plate) and use :hold for anything longer than ~0.5 s or wherever they break. A freeze on
the speaker's face under a meme sound is the classic meme beat; a run-on that shows them leaving reads as a mistake.

Why: a meme sound goes in air, after the punchline (references/sound-and-memes.md), but a tight cut leaves
0.2-0.3 s between takes, so any rip lands on the next word. This is "cut the take a little later" done after the
fact: at each --at (edit seconds near a hard cut, then seconds to add) the take that ends there runs on for D s.

How:
  1. snaps J to the hard cut in the plate (largest frame difference within +-0.3 s; it must be a real cut);
  2. finds the take's raw time by cross-correlating the voice before J against the raw audio (score printed);
  3. matches the plate's last frame to the raw frame (scale 1.0-1.6 + offset), so wide / tight framing carries on;
  4. renders D s of raw at that framing, and the raw room tone at the voice's level (gain from the 1.5 s before J);
  5. writes, next to the inputs: <plate>.<tag>.mp4, <voice>.<tag>.wav, build/words.<tag>.json, build/face.json
     (old one kept as face.pre-<tag>.json; samples shifted, the gap filled with the last face box) and
     build/pauses.json [{"at": J, "dur": D, "raw": R, ...}]. shift(t) in this module maps old edit seconds to new.
Check the result: build/<tag>-<i>-seam.jpg (plate's last frame | the insert's first frame), frame J-1 / J / J+D of the new plate and a waveform around each pause (no step in framing or level).
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

FPS = 30
SR = 8000


def run(c):
    subprocess.run(c, check=True)


def pcm(path, ss=None, t=None, sr=SR):
    c = ["ffmpeg", "-v", "error"] + (["-ss", f"{ss:.4f}"] if ss is not None else []) + ["-i", path]
    c += (["-t", f"{t:.4f}"] if t is not None else []) + ["-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(c, capture_output=True, check=True).stdout, np.float32)


def frame(path, n, w=270, h=480):
    """frame number n (ffmpeg -ss T returns the first frame with pts >= T, so seek half a frame early)"""
    t = n / FPS - 0.5 / FPS
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.4f}", "-i", path, "-frames:v", "1", "-vf", f"scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
    if not raw and n > 0:                       # past the last decodable frame (a plate's very end): one frame back
        return frame(path, n - 1, w, h)
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3)


def snap_cut(plate, j):
    """the hard cut nearest j: frame k where the jump from k-1 is biggest (k/30 = first frame of the next take)"""
    k0 = round(j * FPS)
    ks = range(k0 - 9, k0 + 10)
    fr = [frame(plate, k).astype(np.float32) for k in [ks[0] - 1] + list(ks)]   # fr[i+1] = frame ks[i], fr[i] = the one before
    d = [np.abs(fr[i + 1] - fr[i]).mean() for i in range(len(ks))]
    i = int(np.argmax(d))
    med = float(np.median(d))
    if d[i] < max(12.0, 4 * med):
        sys.exit(f"no hard cut near {j:.2f}s (max frame jump {d[i]:.1f}, median {med:.1f}); --at must sit on a take change")
    return ks[i]


def find_raw(voice, raw_audio, j, n_ctx=1.5):
    """raw seconds of edit time j (the end of the take before the cut)"""
    tpl = pcm(voice, j - n_ctx, n_ctx)
    sig = pcm(raw_audio)
    tpl = (tpl - tpl.mean()) / (tpl.std() + 1e-9)
    n = len(sig) + len(tpl)
    nf = 1 << (n - 1).bit_length()
    cor = np.fft.irfft(np.fft.rfft(sig, nf) * np.conj(np.fft.rfft(tpl, nf)), nf)[:len(sig) - len(tpl)]
    c2 = np.convolve(sig ** 2, np.ones(len(tpl)), "valid")[:len(cor)]
    ncc = cor / (np.sqrt(c2) * np.sqrt(len(tpl)) + 1e-9)
    i = int(np.argmax(ncc))
    return i / SR + n_ctx, float(ncc[i])


def framing(plate, raw, k, r_end):
    """scale s and offset (x, y) in raw-scaled-to-1080x1920 space so that plate == raw cropped [x, x+1080/s] ..."""
    p = frame(plate, k - 1, 1080, 1920)
    rr = frame(raw, round(r_end * FPS) - 1, 1080, 1920)
    best = (-1, 1.0, (0, 0))
    for s in np.arange(1.0, 1.61, 0.01):
        tw, th = round(1080 / s), round(1920 / s)
        tt = cv2.resize(p, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(rr, tt, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (mx, round(float(s), 2), loc)
    return best


def shift_fn(pauses):
    def shift(t):
        return round(t + sum(p["dur"] for p in pauses if t >= p["at"] - 1e-4), 4)
    return shift


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--raw", required=True)
    ap.add_argument("--raw-audio", help="raw-timeline audio (default: the raw file's audio)")
    ap.add_argument("--at", action="append", required=True,
                    help="J:D[:hold]  (edit seconds near a cut : seconds to add; hold = freeze the first run-on frame)")
    ap.add_argument("--plate", default="assets/plate_alt.mp4")
    ap.add_argument("--voice", default="assets/voice.wav")
    ap.add_argument("--words", default="build/words.cut.json")
    ap.add_argument("--tag", default="pause")
    a = ap.parse_args()
    P = os.path.abspath(a.project)
    pj = lambda x: x if os.path.isabs(x) else os.path.join(P, x)  # noqa: E731
    plate, voice, raw = os.path.realpath(pj(a.plate)), os.path.realpath(pj(a.voice)), a.raw
    raw_audio = a.raw_audio or raw
    sr_v = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate", "-of", "csv=p=0",
                               voice], capture_output=True, text=True).stdout.strip())
    nfr = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                              "-of", "csv=p=0", plate], capture_output=True, text=True).stdout.strip())
    tmp = os.path.join(P, "build", f"_{a.tag}")
    os.makedirs(tmp, exist_ok=True)

    pauses = []
    for spec in sorted(a.at, key=lambda s: float(s.split(":")[0])):
        j0, d, *mode = spec.split(":")
        j0, d, hold = float(j0), float(d), mode == ["hold"]
        k = nfr if j0 >= nfr / FPS - 0.05 else snap_cut(plate, j0)    # the plate's end: the last take runs on
        J = k / FPS
        r_end, score = find_raw(voice, raw_audio, J)
        r_end = round(r_end * FPS) / FPS
        mx, s, (x, y) = framing(plate, raw, k, r_end)
        if score < 0.4 or mx < 0.75:
            sys.exit(f"at {J:.3f}s: weak match (audio {score:.2f}, picture {mx:.3f}); pass the raw time by hand or check the inputs")
        nd = round(d * FPS)
        pauses.append({"at": round(J, 4), "frame": k, "dur": round(nd / FPS, 4), "hold": hold, "raw": round(r_end, 4), "audio_score": round(score, 3),
                       "scale": s, "offset": [x, y], "picture_score": round(mx, 4)})
        print(f"cut at {J:.3f}s (frame {k}) = raw {r_end:.3f}s  audio {score:.2f}  framing x{s} at {x},{y} ({mx:.3f})  +{nd / FPS:.3f}s")

    # picture: plate segments + raw inserts, frame exact
    segs, prev = [], 0
    for i, p in enumerate(pauses):
        segs.append(("plate", prev, p["frame"]))
        segs.append(("raw", i))
        prev = p["frame"]
    segs.append(("plate", prev, nfr))
    ins = []
    for i, p in enumerate(pauses):
        s, (x, y) = p["scale"], p["offset"]
        # crop in 4K-ish raw pixels: scale to 1080x1920 first space -> iw/1080 factor
        vf = (f"crop=iw*{1 / s:.5f}:ih*{1 / s:.5f}:iw*{x / 1080:.5f}:ih*{y / 1920:.5f},scale=1080:1920:flags=lanczos,"
              f"fps={FPS},format=yuv420p,setsar=1")
        if p["hold"]:                               # freeze the take's first run-on frame (eyes still on camera)
            vf = vf.replace(f"fps={FPS},", f"fps={FPS},trim=end_frame=1,tpad=stop_mode=clone:stop={round(p['dur'] * FPS)},")
        out = os.path.join(tmp, f"ins{i}.mp4")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{p['raw']:.4f}", "-i", raw, "-frames:v", str(round(p["dur"] * FPS)), "-vf", vf, "-an",
             "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-g", "30", out])
        ins.append(out)
        cmp_ = os.path.join(P, "build", f"{a.tag}-{i}-seam.jpg")       # look at it: the plate's last frame | the insert's first
        a_ = frame(plate, p["frame"] - 1, 540, 960)
        b_ = frame(out, 0, 540, 960)
        cv2.imwrite(cmp_, np.hstack([a_, b_]))
        p["seam"] = os.path.relpath(cmp_, P)
    inputs, fc, labels = ["-i", plate], [], []
    for i, f in enumerate(ins):
        inputs += ["-i", f]
    for n, sg in enumerate(segs):
        if sg[0] == "plate":
            fc.append(f"[0:v]trim=start_frame={sg[1]}:end_frame={sg[2]},setpts=PTS-STARTPTS,setsar=1[s{n}]")
        else:
            fc.append(f"[{sg[1] + 1}:v]setpts=PTS-STARTPTS,setsar=1[s{n}]")
        labels.append(f"[s{n}]")
    base, ext = os.path.splitext(os.path.join(P, a.plate))
    out_plate = f"{base}.{a.tag}.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=1:a=0[o]",
         "-map", "[o]", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", "-g", "30",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", out_plate])

    # sound: voice segments + raw room tone at the voice's level
    v_ins = []
    for i, p in enumerate(pauses):
        vb = pcm(voice, p["at"] - 1.5, 1.5, sr_v)
        rb = pcm(raw_audio, p["raw"] - 1.5, 1.5, sr_v)
        g = float(np.sqrt((vb ** 2).mean()) / (np.sqrt((rb ** 2).mean()) + 1e-9))
        p["room_gain_db"] = round(20 * np.log10(g + 1e-9), 1)
        out = os.path.join(tmp, f"room{i}.wav")
        rt = pcm(raw_audio, p["raw"], p["dur"], sr_v) * g
        win = sr_v // 500                           # handling noise (a mic touch, a click) in the room tone: duck any 2 ms
        n = len(rt) // win                          # window more than 12 dB over the room's median back down to it
        rms = np.sqrt((rt[:n * win].reshape(n, win) ** 2).mean(1)) + 1e-9
        gain = np.minimum(1.0, np.median(rms) * 10 ** (12 / 20) / rms)
        gain = np.convolve(np.repeat(gain, win), np.ones(win) / win, "same")        # no steps
        rt[:n * win] *= np.minimum(gain[:n * win], 1.0)
        p["room_ducked_ms"] = int((gain < 0.99).sum() / sr_v * 1000)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(sr_v), "-ac", "1", "-i", "-", "-af",
                        f"afade=t=in:d=0.01,afade=t=out:st={p['dur'] - 0.01:.4f}:d=0.01", "-c:a", "pcm_s24le", out],
                       input=rt.astype(np.float32).tobytes(), check=True)
        v_ins.append(out)
    inputs, fc, labels, prev = ["-i", voice], [], [], 0.0
    for i, p in enumerate(pauses):
        inputs += ["-i", v_ins[i]]
    n = 0
    for i, p in enumerate(pauses):
        fc.append(f"[0:a]atrim={prev:.5f}:{p['at']:.5f},asetpts=PTS-STARTPTS,afade=t=out:st={p['at'] - prev - 0.01:.5f}:d=0.01[a{n}]")
        labels.append(f"[a{n}]"); n += 1
        labels.append(f"[{i + 1}:a]")
        prev = p["at"]
    fc.append(f"[0:a]atrim=start={prev:.5f},asetpts=PTS-STARTPTS,afade=t=in:d=0.01[a{n}]")
    labels.append(f"[a{n}]")
    vb_, _ = os.path.splitext(os.path.join(P, a.voice))
    out_voice = f"{vb_}.{a.tag}.wav"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[o]",
         "-map", "[o]", "-c:a", "pcm_s24le", out_voice])

    # words and the face track follow the new timeline
    shift = shift_fn(pauses)
    w = json.load(open(pj(a.words)))
    flat = [x for s in w["segments"] for x in s["words"]] if isinstance(w, dict) and "segments" in w else (w.get("words", w) if isinstance(w, dict) else w)
    out_w = []
    for x in flat:
        y = dict(x)
        for ks, ke in (("start", "end"), ("s", "e")):      # by the word's middle: whisper often starts a word a little early
            if ks in y:
                d_ = shift((float(y[ks]) + float(y[ke])) / 2) - (float(y[ks]) + float(y[ke])) / 2
                y[ks], y[ke] = round(float(y[ks]) + d_, 4), round(float(y[ke]) + d_, 4)
        out_w.append(y)
    json.dump({"words": out_w}, open(os.path.join(P, "build", f"words.{a.tag}.json"), "w"), ensure_ascii=False, indent=0)
    fp = os.path.join(P, "build", "face.json")
    if os.path.exists(fp):
        keep = os.path.join(P, "build", f"face.pre-{a.tag}.json")
        if not os.path.exists(keep):
            os.rename(fp, keep)
        fj = json.load(open(keep))
        step = 1 / fj.get("fps", 5)
        out_s = [[shift(smp[0])] + list(smp[1:]) for smp in fj["samples"]]
        for p in pauses:                                   # fill each gap with the last box before it
            t0 = shift(p["at"] - 1e-3)
            last = max((o for o in out_s if o[0] <= t0), key=lambda o: o[0])
            tt = t0 + step
            while tt < t0 + p["dur"]:
                out_s.append([round(tt, 4)] + last[1:])
                tt += step
        fj["samples"] = sorted(out_s, key=lambda o: o[0])
        json.dump(fj, open(fp, "w"))
    json.dump({"tag": a.tag, "plate": os.path.relpath(out_plate, P), "voice": os.path.relpath(out_voice, P), "pauses": pauses},
              open(os.path.join(P, "build", "pauses.json"), "w"), indent=1)
    print(f"-> {os.path.relpath(out_plate, P)}, {os.path.relpath(out_voice, P)}, build/words.{a.tag}.json, build/face.json, build/pauses.json")


if __name__ == "__main__":
    main()
