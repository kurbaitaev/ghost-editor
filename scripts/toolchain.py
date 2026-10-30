#!/usr/bin/env python3
"""Toolchain fingerprint of this machine, and the differences that change an edit between two machines.

    toolchain.py show                 this machine's fingerprint (JSON)
    toolchain.py record               write it to library/toolchain/<host>.json
    toolchain.py compare [--days 60]  this machine against every other host's recorded file; exit 1 when a difference
                                      changes the output

Two machines editing the same reels should cut, mix and render alike. library/ is shared between them (it is
gitignored media, synced like the SFX and memes), so each machine's doctor.sh records its fingerprint there and
compares it with the others' last record: no network or login to the other machine needed.

What changes the output (compare exits 1): ffmpeg major.minor and its x264 (every encode, the voice chain, HyperFrames'
own encode), libass, the HyperFrames version (scripts/HF_VERSION, or an HF_VERSION override) and its headless Chrome,
MediaPipe (facescan.py flags -> plan_cut.py edges), OpenCV major.minor (face_track.py placement), the whisper backend
(mlx_whisper vs openai-whisper: different words and times), silero-vad (speech islands), numpy major.
What does not (printed as info): node, the Python minor version, google-genai, patch versions.
"""
import argparse, glob, json, os, re, shutil, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
DIR = os.path.join(SKILL, "library", "toolchain")

PYPROBE = r"""
import json, sys
v = {"python": sys.version.split()[0]}
for name, mod in [("numpy", "numpy"), ("opencv", "cv2"), ("mediapipe", "mediapipe"), ("google-genai", "google.genai"),
                  ("openai-whisper", "whisper"), ("mlx-whisper", "mlx_whisper"), ("silero-vad", "silero_vad"), ("torch", "torch")]:
    try:
        m = __import__(mod, fromlist=["_"])
        v[name] = getattr(m, "__version__", None) or "installed"
    except Exception:
        pass
if v.get("mlx-whisper") == "installed" or v.get("silero-vad") == "installed":
    from importlib.metadata import version
    for k in ("mlx-whisper", "silero-vad"):
        try:
            if v.get(k) == "installed": v[k] = version(k)
        except Exception:
            pass
print(json.dumps(v))
"""


def run(cmd, timeout=60, any_rc=False):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 or any_rc else ""
    except Exception:
        return ""


def host():
    """the machine's stable name (macOS LocalHostName, e.g. 'MacBook-Air-2'), else the hostname"""
    return run(["scutil", "--get", "LocalHostName"]).strip() or socket.gethostname().split(".")[0]


def py_versions(py):
    if not py or (not os.path.exists(py) and not shutil.which(py)):
        return None
    out = run([py, "-c", PYPROBE], timeout=120).strip().splitlines()
    try:
        return json.loads(out[-1]) if out else None
    except ValueError:
        return None


def media_py():
    """the python the skill's media scripts use: $MEDIA_PY, python3 when it has numpy, else ~/.venvs/media (doctor.sh)"""
    if os.environ.get("MEDIA_PY"):
        return os.environ["MEDIA_PY"]
    if shutil.which("python3") and subprocess.run(["python3", "-c", "import numpy"], capture_output=True).returncode == 0:
        return shutil.which("python3")
    p = os.path.expanduser("~/.venvs/media/bin/python")
    return p if os.path.exists(p) else shutil.which("python3")


def hf_pinned():
    f = os.path.join(HERE, "HF_VERSION")
    return open(f).read().strip() if os.path.exists(f) else None


def snapshot():
    fp = {"host": host(), "date": time.strftime("%Y-%m-%d %H:%M"), "skill_commit": run(["git", "-C", SKILL, "rev-parse", "--short", "HEAD"]).strip()}
    v = run(["ffmpeg", "-hide_banner", "-version"]).split("\n")[0]
    m = re.search(r"ffmpeg version (\S+)", v)
    conf = run(["ffmpeg", "-hide_banner", "-buildconf"])
    fp["ffmpeg"] = {"version": m.group(1) if m else None,
                    "libs": sorted(x for x in ("libass", "libx264", "libx265", "libvpx", "libzimg", "libplacebo", "libfreetype", "videotoolbox")
                                   if f"enable-{x}" in conf or (x == "videotoolbox" and "videotoolbox" in run(["ffmpeg", "-hide_banner", "-hwaccels"])))}
    if shutil.which("brew"):
        bv = {}
        for line in run(["brew", "list", "--versions", "ffmpeg", "x264", "x265", "libass", "node", "python@3.11", "python@3.12", "python@3.13", "python@3.14"], timeout=120, any_rc=True).splitlines():
            k, *vs = line.split()
            bv[k] = vs[0] if vs else ""
        # which formula built the ffmpeg on PATH (homebrew/core vs the homebrew-ffmpeg tap): its install receipt
        rec = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(shutil.which("ffmpeg") or "/"))), "INSTALL_RECEIPT.json")
        if os.path.exists(rec):
            src = json.load(open(rec)).get("source", {})
            bv["ffmpeg-formula"] = f"{src.get('tap', '?')}/ffmpeg"
        fp["brew"] = bv
    fp["node"] = run(["node", "-v"]).strip() or None
    cached = sorted({json.load(open(p)).get("version") for p in glob.glob(os.path.expanduser("~/.npm/_npx/*/node_modules/hyperframes/package.json"))},
                    key=lambda s: [int(x) if x.isdigit() else 0 for x in s.split(".")])
    fp["hyperframes"] = {"pinned": hf_pinned(), "override": os.environ.get("HF_VERSION") or None, "cached": cached,
                         "chrome": sorted(os.path.basename(p) for p in glob.glob(os.path.expanduser("~/.cache/hyperframes/chrome/*/*")))}
    mp = media_py()
    fp["media_python"] = {"path": mp, **(py_versions(mp) or {})}
    mlx = os.environ.get("MLXW_PY") or os.path.expanduser("~/.venvs/mlxw/bin/python")
    fp["mlx_python"] = ({"path": mlx, **(py_versions(mlx) or {})} if os.path.exists(mlx) else None)
    aq = os.path.join(os.environ.get("AUDIOQA_VENV") or os.path.expanduser("~/.venvs/ghost-audioqa"), "bin", "python")
    fp["audioqa_python"] = ({"path": aq, **(py_versions(aq) or {})} if os.path.exists(aq) else None)
    return fp


def mm(v, n=2):
    return ".".join(str(v).split(".")[:n]) if v else None


def whisper_backend(fp):
    """what islands_tx.py / transcribe.py --backend mlx actually run on this machine"""
    for k in ("media_python", "mlx_python"):
        if (fp.get(k) or {}).get("mlx-whisper"):
            return "mlx-whisper " + fp[k]["mlx-whisper"]
    w = (fp.get("media_python") or {}).get("openai-whisper")
    return f"openai-whisper {w}" if w else None


# (label, getter, what it changes); a getter returns the comparable value
OUTPUT = [
    ("ffmpeg", lambda f: mm((f.get("ffmpeg") or {}).get("version")), "every encode, loudnorm and the voice chain; HyperFrames encodes with it too"),
    ("x264", lambda f: (f.get("brew") or {}).get("x264"), "the H.264 bitstream of every render"),
    ("ffmpeg libass", lambda f: "libass" in (f.get("ffmpeg") or {}).get("libs", []), "burned subtitles (ffmpeg subtitle pipelines only)"),
    ("HyperFrames", lambda f: (f.get("hyperframes") or {}).get("override") or (f.get("hyperframes") or {}).get("pinned"), "every render"),
    ("mediapipe", lambda f: (f.get("media_python") or {}).get("mediapipe"), "facescan.py flags -> plan_cut.py edges, keep/cover"),
    ("opencv", lambda f: mm((f.get("media_python") or {}).get("opencv")), "face_track.py (YuNet): caption and card placement"),
    ("whisper backend", whisper_backend, "transcripts: takes, subcheck, caption times"),
    ("silero-vad", lambda f: (f.get("audioqa_python") or {}).get("silero-vad"), "speech islands (vad_pauses.py)"),
    ("numpy", lambda f: mm((f.get("media_python") or {}).get("numpy"), 1), "array maths in every analysis script"),
]
INFO = [
    ("ffmpeg (exact)", lambda f: (f.get("ffmpeg") or {}).get("version")),
    ("ffmpeg formula", lambda f: (f.get("brew") or {}).get("ffmpeg-formula")),
    ("node", lambda f: f.get("node")),
    ("media python", lambda f: (f.get("media_python") or {}).get("python")),
    ("numpy (exact)", lambda f: (f.get("media_python") or {}).get("numpy")),
    ("opencv (exact)", lambda f: (f.get("media_python") or {}).get("opencv")),
    ("google-genai", lambda f: (f.get("media_python") or {}).get("google-genai")),
    ("headless chrome", lambda f: ",".join((f.get("hyperframes") or {}).get("chrome") or []) or None),
    ("skill commit", lambda f: f.get("skill_commit")),
]


def compare(me, other):
    out, info = [], []
    for label, get, why in OUTPUT:
        a, b = get(me), get(other)
        if a != b:
            out.append(f"{label}: {a} here, {b} on {other['host']}  ({why})")
    for label, get in INFO:
        a, b = get(me), get(other)
        if a != b:
            info.append(f"{label}: {a} here, {b} on {other['host']}")
    return out, info


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n\n", 1)[1])
    ap.add_argument("cmd", choices=["show", "record", "compare"])
    ap.add_argument("--days", type=float, default=60, help="ignore other hosts' records older than this")
    ap.add_argument("--dir", default=DIR)
    A = ap.parse_args()
    me = snapshot()
    if A.cmd == "show":
        print(json.dumps(me, indent=1)); return
    os.makedirs(A.dir, exist_ok=True)
    json.dump(me, open(os.path.join(A.dir, f"{me['host']}.json"), "w"), indent=1)
    if A.cmd == "record":
        print(f"recorded {os.path.join(A.dir, me['host'] + '.json')}"); return
    bad = 0; seen = 0
    for p in sorted(glob.glob(os.path.join(A.dir, "*.json"))):
        o = json.load(open(p))
        if o.get("host") == me["host"]:
            continue
        age = (time.time() - os.path.getmtime(p)) / 86400
        if age > A.days:
            continue
        seen += 1
        out, info = compare(me, o)
        print(f"vs {o['host']} (recorded {o.get('date')}):", "same toolchain" if not out and not info else "")
        for line in out:
            print("  DIFF ", line)
        for line in info:
            print("  info ", line)
        bad += len(out)
    if not seen:
        print(f"no other machine recorded in {A.dir} (run toolchain.py record there; doctor.sh does)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
