#!/usr/bin/env python3
"""Transcribe the WHOLE recording (every take) with whisper word timestamps
and print the segment table: the take map you choose takes from.

    transcribe.py <project>/assets/talk.mp4 --out <project>/build/words.whisper.json \
        [--model turbo] [--lang en] [--raw existing.json] [--backend whisper|mlx] [--mlx-model ~/.cache/mlxw-turbo]

Times are ORIGINAL-recording seconds, the unit reel.json uses. Product names
get mangled; fix them in reel.json -> captions.fixes, not here.
Backends: whisper = the openai-whisper CLI on PATH (or $WHISPER); mlx = mlx_whisper large-v3-turbo (Apple silicon; when
this python lacks mlx_whisper the script re-runs itself in $MLXW_PY or ~/.venvs/mlxw/bin/python). The audio goes in as
16 kHz mono. Both decode anti-merge: no conditioning on previous text (else a retake is merged into one clean
sentence), temperature fallback 0/0.2/0.4 (the CLI cannot cap it: 0..1 in steps of 0.2), no_speech 0.6, compression
ratio 2.2, hallucination_silence_threshold 1.0. The fallback samples: the mlx and python-API paths seed it (repeatable
runs); the whisper CLI cannot be seeded.
Importable: load_words(path) (islands.json / whisper json / flat list -> [{w, a, b, p}]), asr(lang) for the per-piece
transcribers (islands_tx.py, subcheck.py).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

RESTART = re.compile(r"(okay,? again|let me (do|say) that again|one more time|take two|from the top|let's try again|wait,? no)", re.I)
MLXW_PY = os.path.expanduser(os.environ.get("MLXW_PY", "~/.venvs/mlxw/bin/python"))
MLX_MODEL = "~/.cache/mlxw-turbo"
ANTI_MERGE = dict(condition_on_previous_text=False, temperature=(0.0, 0.2, 0.4), no_speech_threshold=0.6,
                  compression_ratio_threshold=2.2, hallucination_silence_threshold=1.0)


def find_whisper():
    w = os.environ.get("WHISPER") or shutil.which("whisper")
    if not w:
        sys.exit("whisper not found: pip install openai-whisper (or set WHISPER=/path/to/whisper)")
    return w


def has_mlx():
    try:
        import mlx_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_mlx(script):
    """re-run `script` (same argv) in a python that has mlx_whisper; returns False when there is none"""
    if has_mlx():
        return True
    if os.environ.get("_MLXW_REEXEC") or not os.path.exists(MLXW_PY):
        return False
    os.environ["_MLXW_REEXEC"] = "1"
    os.execv(MLXW_PY, [MLXW_PY, os.path.abspath(script)] + sys.argv[1:])


def seed(backend, n=0):
    """fix the sampling PRNG: the temperature fallback samples, so unseeded runs differ (one 3-min take: 156, 200, 207 words)"""
    if backend == "mlx":
        import mlx.core as mx
        mx.random.seed(n)
    else:
        import torch
        torch.manual_seed(n)


def asr(lang, mlx_model=MLX_MODEL, whisper_model="turbo"):
    """-> (backend name, f(audio path or 16 kHz float32 array, **decode) -> whisper result dict); mlx first"""
    if has_mlx():
        import mlx_whisper
        seed("mlx")
        path = os.path.expanduser(mlx_model)
        return "mlx", lambda x, **kw: mlx_whisper.transcribe(x, path_or_hf_repo=path, language=lang, **kw)
    import whisper
    seed("whisper")
    m = whisper.load_model(whisper_model)
    return "whisper", lambda x, **kw: m.transcribe(x, language=lang, fp16=False, **kw)


def load_words(path):
    """islands.json ([{a, b, text, words: [{w, a, b, p}]}]), a whisper json ({segments: [{words: [{word, start, end}]}]})
    or a flat [{w|word, a|start, b|end}] list -> [{w, a, b, p}] in time order"""
    d = json.load(open(path))
    if isinstance(d, dict):
        return [{"w": x["word"].strip(), "a": x["start"], "b": x["end"], "p": x.get("probability", 1)}
                for s in d["segments"] for x in s.get("words") or []]
    if d and "words" in d[0]:
        return [{"w": x["w"], "a": x["a"], "b": x["b"], "p": x.get("p", 1)} for i in d for x in i["words"]]
    return [{"w": (x.get("w") or x.get("word", "")).strip(), "a": x.get("a", x.get("start")), "b": x.get("b", x.get("end")),
             "p": x.get("p", x.get("probability", 1))} for x in d]


def transcribe(src, model, lang, backend="whisper", mlx_model=MLX_MODEL):
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "audio.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
        if backend == "mlx":
            import mlx_whisper
            seed("mlx")
            return mlx_whisper.transcribe(wav, path_or_hf_repo=os.path.expanduser(mlx_model), language=lang,
                                          word_timestamps=True, **ANTI_MERGE)
        cmd = [find_whisper(), wav, "--model", model, "--word_timestamps", "True",
               "--output_format", "json", "--output_dir", td, "--fp16", "False",
               "--condition_on_previous_text", "False", "--temperature", "0", "--temperature_increment_on_fallback", "0.2",
               "--no_speech_threshold", "0.6", "--compression_ratio_threshold", "2.2", "--hallucination_silence_threshold", "1.0"]
        if lang:
            cmd += ["--language", lang]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        return json.load(open(os.path.join(td, "audio.json")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="turbo")
    ap.add_argument("--lang", default=None)
    ap.add_argument("--raw", help="reuse an existing whisper json")
    ap.add_argument("--backend", choices=("whisper", "mlx"), default="whisper")
    ap.add_argument("--mlx-model", default=MLX_MODEL, help="mlx_whisper model dir (large-v3-turbo)")
    a = ap.parse_args()
    if a.backend == "mlx" and not a.raw and not ensure_mlx(__file__):
        sys.exit(f"--backend mlx: no mlx_whisper in this python or {MLXW_PY} (set MLXW_PY)")
    data = json.load(open(a.raw)) if a.raw else transcribe(a.src, a.model, a.lang, a.backend, a.mlx_model)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(data, open(a.out, "w"))
    print("\n  start    end   gap  text   (original seconds; * = restart marker)")
    prev = 0.0
    for s in data["segments"]:
        t = s["text"].strip()
        if not t:
            continue
        ws = s.get("words") or []
        st = ws[0]["start"] if ws else s["start"]
        en = ws[-1]["end"] if ws else s["end"]
        mark = "*" if RESTART.search(t) else " "
        print(f"{st:7.2f} {en:7.2f} {st - prev:5.1f} {mark}{t}")
        prev = en
    n = sum(len(s.get("words") or []) for s in data["segments"])
    print(f"\n{n} words -> {a.out}")


if __name__ == "__main__":
    main()
