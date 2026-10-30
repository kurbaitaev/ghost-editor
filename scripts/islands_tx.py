#!/usr/bin/env python3
"""Transcribe every VAD speech island on its own (whole-file whisper skips short restarts and merges retakes).

    islands_tx.py <audio> --vad build/vad.json [--lang ru] [--out build/islands.json] [--mlx-model ~/.cache/mlxw-turbo]

vad.json = vad_pauses.py output (its `islands`); audio = the same recording (any file ffmpeg reads; build/a16.wav).
Each island is padded 0.15 s each side and decoded with no conditioning (temperature 0, 0.2). Segments that are
whisper's Russian silence hallucinations (subtitle credits, "to be continued", "thanks for watching", HALL) or have
no_speech > 0.8 are dropped. mlx_whisper large-v3-turbo; when this python lacks it the script re-runs itself in $MLXW_PY or
~/.venvs/mlxw/bin/python, else falls back to openai-whisper (python API, turbo).
Out: [{a, b, text, words: [{w, a, b, p}]}] in original seconds (a/b = the VAD island)."""
import argparse, json, os, re, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcribe

HALL = re.compile(r"(продолжение следует|субтитр|редактор|спасибо за просмотр|подпишитесь|dimatorzok|amara)", re.I)
SR = 16000


def read16k(path):
    return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                        capture_output=True, check=True).stdout, np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio"); ap.add_argument("--vad", required=True); ap.add_argument("--lang", default="ru")
    ap.add_argument("--out", default="build/islands.json"); ap.add_argument("--mlx-model", default=transcribe.MLX_MODEL)
    a = ap.parse_args()
    transcribe.ensure_mlx(__file__)
    backend, run = transcribe.asr(a.lang, a.mlx_model)
    x = read16k(a.audio); out = []; t0 = time.time()
    for isl in json.load(open(a.vad))["islands"]:
        a0 = max(0.0, isl["a"] - 0.15); b0 = min(len(x) / SR, isl["b"] + 0.15)
        r = run(x[int(a0 * SR):int(b0 * SR)].copy(), word_timestamps=True, condition_on_previous_text=False, temperature=(0.0, 0.2), verbose=None)
        words = []
        for s in r["segments"]:
            if HALL.search(s["text"]) or s.get("no_speech_prob", 0) > 0.8: continue
            for w in s.get("words", []):
                words.append({"w": w["word"].strip(), "a": round(a0 + w["start"], 3), "b": round(a0 + w["end"], 3), "p": round(w.get("probability", 1), 3)})
        out.append({"a": isl["a"], "b": isl["b"], "text": " ".join(w["w"] for w in words), "words": words})
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=0)
    print(f"{len(out)} islands, {sum(len(i['words']) for i in out)} words ({backend}, {time.time() - t0:.0f} s) -> {a.out}", flush=True)


if __name__ == "__main__":
    main()
