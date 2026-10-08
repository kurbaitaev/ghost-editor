#!/usr/bin/env python3
"""Voiceover with ElevenLabs + word timings, for narrated explainers (recipes/explainer-vector).

    tts_elevenlabs.py script.txt --voice <voice_id> --out voice/ [--takes 2] [--model eleven_multilingual_v2] [--speed 0.92]

Writes voice/take<N>.mp3, voice/take<N>.align.json (character alignment) and voice/take<N>.words.json
([{w, s, e}] word timings) for every take. Takes differ by seed; listen and pick one.

Key: ELEVENLABS_API_KEY in the environment or in <skill>/.env. The key is checked with one cheap call
(/v1/user/subscription) before any generation. Library voices work by id without adding them to the account.
Voices used so far: Spuds Oxley "Grandpa" NOpBlnGInO9m6vDvFkFC (wise elder, chosen), Michael Moody PerZoH0r6nxBZXCoIPpv.
Pauses: write "..." and blank lines in the script; the model honours them.
"""
import argparse, base64, json, os, sys, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    env = os.path.join(HERE, "..", ".env")
    if not k and os.path.exists(env):
        for line in open(env):
            if line.startswith("ELEVENLABS_API_KEY="):
                k = line.split("=", 1)[1].strip()
    if not k:
        sys.exit("ELEVENLABS_API_KEY not set (environment or <skill>/.env)")
    return k


def call(path, body=None, k=None):
    req = urllib.request.Request(f"https://api.elevenlabs.io{path}", data=json.dumps(body).encode() if body else None,
                                 headers={"xi-api-key": k, "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs {path}: HTTP {e.code} {e.read()[:300]!r}")


def words_from(al):
    out, cur, s, pe = [], "", None, None
    for c, t0, t1 in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if c.isspace():
            if cur:
                out.append({"w": cur, "s": round(s, 3), "e": round(pe, 3)}); cur = ""
            continue
        if not cur:
            s = t0
        cur += c; pe = t1
    if cur:
        out.append({"w": cur, "s": round(s, 3), "e": round(pe, 3)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", default="voice")
    ap.add_argument("--takes", type=int, default=2)
    ap.add_argument("--model", default="eleven_multilingual_v2")
    ap.add_argument("--speed", type=float, default=0.92)
    ap.add_argument("--stability", type=float, default=0.55)
    a = ap.parse_args()
    k = key()
    sub = call("/v1/user/subscription", k=k)
    left = sub.get("character_limit", 0) - sub.get("character_count", 0)
    text = open(a.script).read().strip()
    if left < len(text) * a.takes:
        sys.exit(f"not enough ElevenLabs characters left ({left}) for {a.takes} takes of {len(text)}")
    os.makedirs(a.out, exist_ok=True)
    for n in range(1, a.takes + 1):
        body = {"text": text, "model_id": a.model, "seed": 11 * n,
                "voice_settings": {"stability": a.stability, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True, "speed": a.speed}}
        d = call(f"/v1/text-to-speech/{a.voice}/with-timestamps?output_format=mp3_44100_192", body, k)
        base = os.path.join(a.out, f"take{n}")
        open(base + ".mp3", "wb").write(base64.b64decode(d["audio_base64"]))
        json.dump(d["alignment"], open(base + ".align.json", "w"))
        w = words_from(d["alignment"])
        json.dump(w, open(base + ".words.json", "w"), ensure_ascii=False, indent=0)
        print(f"take {n}: {len(w)} words, {w[-1]['e']:.1f}s -> {base}.mp3")


if __name__ == "__main__":
    main()
