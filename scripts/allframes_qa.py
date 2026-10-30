#!/usr/bin/env python3
"""Every-frame QA of a FINISHED reel: ONE Gemini call on the whole render at a high frame rate.

The sampled check (broll_qa.py -> broll_vision.py) looks at 6 frames per detected B-roll layer. This one uploads the whole
final render (Gemini Files API), asks with videoMetadata.fps = N (default 10, the API maximum is 24: 30 is refused) and gets back a
strict JSON list of every moment that breaks the user's rules:

  - the rules in people-rules.json (read from the file, so a rule change applies here too; empty by default),
  - a card / caption / graphic covering the speaker's face,
  - a visibly broken frame (black or blank flash, glitch, corrupted frame).

    allframes_qa.py RENDER.mp4 [--fps 10] [--model gemini-2.5-flash] [--out FILE.json] [--media-res default|low]
                    [--thinking 4096] [--rules all|people] [--keep-file]

Each finding: t_start, t_end (seconds), what, rule, confidence (0-1). Prints the token usage and the cost (gemini-2.5-flash:
$0.30 / 1M input, $2.50 / 1M output incl. thinking tokens; the usage fields of the response are the source). The uploaded file
is deleted at the end (always, also on an error). Transient errors (5xx, timeouts, a bad / cut-off / degenerate answer) are
retried up to 3 times; anything else (bad key, 429 spending cap, blocked) stops at once. Every attempt is billed, also a cut-off
one: the cost printed is the sum over all attempts. An error is NEVER written as a result: no JSON file is written, exit code 2.
Exit code: 0 = no finding, 1 = findings, 2 = could not check.
Measured limits: times are good to about 1 s (Gemini reads a 1 s clock), a run is stochastic (the same
file finds a 0.1-0.5 s overlay in one run and not in the next), the face_covered / broken_frame asks are mostly noise
(--rules people drops them).

Key: GEMINI_API_KEY, or the skill's .env. Rules file: BROLL_PEOPLE_RULES, default people-rules.json next to SKILL.md.
Cost on a 29 s reel (gemini-2.5-flash, default media resolution = 258 tokens per frame): ~0.03 USD at 10 fps, ~0.07 at 24 fps (see --media-res low).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.environ.get("BROLL_PEOPLE_RULES") or os.path.join(HERE, "..", "people-rules.json")
PRICE_IN, PRICE_OUT = 0.30, 2.50          # USD per 1M tokens, gemini-2.5-flash (output includes thinking tokens)
PROMPT_V = 2          # v2: seconds format spelled out (v1 once answered 00:08 as 0.08), short appearances count
MAX_FPS = 24          # the API refuses videoMetadata.fps > 24 (400 INVALID_ARGUMENT, found by trying 30)
RETRIES = 3

PEOPLE_EXTRA = ()     # ids of EXTRA_RULES that --rules people keeps too (none: add your own rules to people-rules.json)

# checks that are not in people-rules.json: they are about the edit itself, not about who or what is shown
EXTRA_RULES = [
    ("face_covered", "FACE COVERED: a card, panel, sticker, graphic, caption or blur covering the face of the main speaker "
                     "(the person talking to camera) by more than about a quarter, for any length of time, even one frame (say "
                     "'one frame of a transition' in `what` if it is only one frame)."),
    ("broken_frame", "BROKEN FRAME: a black, white or blank flash, a frozen or stuttering picture, glitch, tearing, a "
                     "corrupted or garbled frame, a one-frame flash of unrelated content, a half-rendered scene."),
]


def load_rules(path=RULES_PATH):
    cfg = {"context": "a short talking-head video", "language": "", "rules": []}
    if os.path.exists(path):
        cfg.update(json.load(open(path, encoding="utf8")))
    return cfg


def rule_list(cfg, mode="all"):
    """[(id, text)] the people-rules.json rules and (mode "all") face_covered + broken_frame"""
    out = []
    for r in cfg["rules"]:
        ask = re.sub(r"^\s*true if\s+", "", r["ask"].strip()).replace("answer true", "report it")
        out.append((r["id"], f"{r.get('label', r['id'].upper())}: breaks the rule when {ask[:1].lower() + ask[1:] if ask[1:2].islower() else ask}"))
    return out + (EXTRA_RULES if mode == "all" else [r for r in EXTRA_RULES if r[0] in PEOPLE_EXTRA])


def build_prompt(cfg, fps, dur, mode="all"):
    rules = rule_list(cfg, mode)
    ids = [i for i, _ in rules]
    return ("You are the final QA reviewer of a FINISHED vertical short video: " + cfg["context"] + ". The video is "
            f"{dur:.1f} s long and you see it at {fps:g} frames per second, so you can check EVERY moment. Look at every "
            "second, including the corners of the frame, small or blurred things, photos, posters, screens and reflections, "
            "and report every moment that breaks one of these rules:\n\n"
            + "\n".join(f"- rule id \"{i}\": {t}" for i, t in rules) + "\n\n"
            "The main speaker (the person talking to camera) is allowed and is NOT a finding. "
            "Report only what you really see; do not guess. An uncertain case gets a lower confidence, not a skip.\n\n"
            "A thing visible for only a few frames (a tenth of a second) counts too. "
            "Answer with a JSON list. One item per moment (merge consecutive frames of the same thing into one item), each: "
            "t_start and t_end = SECONDS from the start of the video as a plain decimal number, never minutes.seconds "
            "(the clock 00:08 is 8.0, 00:28 is 28.0, 01:05 is 65.0), with one decimal (a single frame: t_end = t_start); "
            "what = one short sentence: what you see and where in the frame; "
            f"rule = one of {ids}; "
            "confidence = 0 to 1 (how sure you are that it is real and breaks the rule). An empty list [] if nothing breaks a rule.")


def schema(ids):
    return {"type": "array", "items": {"type": "object",
            "properties": {"t_start": {"type": "number"}, "t_end": {"type": "number"}, "what": {"type": "string"},
                           "rule": {"type": "string", "enum": ids}, "confidence": {"type": "number"}},
            "required": ["t_start", "t_end", "what", "rule", "confidence"]}}


def api_key():
    key = os.environ.get("GEMINI_API_KEY")
    envp = os.path.join(HERE, "..", ".env")
    if not key and os.path.exists(envp):
        m = re.search(r"GEMINI_API_KEY\s*=\s*['\"]?([^'\"\n]+)", open(envp).read())
        key = m.group(1).strip() if m else None
    if not key:
        raise RuntimeError("no GEMINI_API_KEY (env or the skill's .env)")
    return key


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise RuntimeError(f"ffprobe cannot read {path}")


class Transient(Exception):
    pass


class NoRules(Exception):
    pass


def is_transient(e):
    """5xx and timeouts / connection drops retry; a 4xx (bad key, 429 spending cap, blocked) does not"""
    code = getattr(e, "code", None)
    if isinstance(code, int):
        return 500 <= code < 600
    n = type(e).__name__
    return isinstance(e, (TimeoutError, ConnectionError)) or any(k in n for k in ("Timeout", "ConnectError", "RemoteProtocol", "ReadError", "WriteError", "NetworkError"))


def with_retries(fn, what):
    err = None
    for i in range(RETRIES + 1):
        if i:
            wait = (3, 8, 20)[i - 1]
            print(f"  retry {i}/{RETRIES} of {what} in {wait} s ({err})", file=sys.stderr)
            time.sleep(wait)
        try:
            return fn()
        except Transient as e:
            err = str(e)
        except Exception as e:      # noqa: BLE001
            if not is_transient(e):
                raise
            err = f"{type(e).__name__}: {str(e)[:160]}"
    raise RuntimeError(f"{what} failed after {RETRIES} retries: {err}")


def usage_of(r):
    u = r.usage_metadata
    if u is None:
        return {"prompt_tokens": 0, "by_modality": {}, "output_tokens": 0, "thought_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    by = {}
    for d in (getattr(u, "prompt_tokens_details", None) or []):
        by[str(getattr(d.modality, "name", d.modality))] = d.token_count
    pt, ct, th = u.prompt_token_count or 0, u.candidates_token_count or 0, u.thoughts_token_count or 0
    return {"prompt_tokens": pt, "by_modality": by, "output_tokens": ct, "thought_tokens": th,
            "total_tokens": u.total_token_count or (pt + ct + th),
            "cost_usd": round(pt * PRICE_IN / 1e6 + (ct + th) * PRICE_OUT / 1e6, 5)}


def total_usage(spent):
    """every attempt is billed, also a cut-off or rejected answer: the sum over all of them is the cost of the run"""
    by = {}
    for u in spent:
        for k, v in u["by_modality"].items():
            by[k] = by.get(k, 0) + v
    t = {k: sum(u[k] for u in spent) for k in ("prompt_tokens", "output_tokens", "thought_tokens", "total_tokens")}
    return {**t, "by_modality": by, "attempts": len(spent), "cost_usd": round(sum(u["cost_usd"] for u in spent), 5)}


def clean(items, dur, ids):
    """validate the answer: a malformed item = a bad answer (retried), never a silent skip"""
    if not isinstance(items, list):
        raise Transient(f"answer is not a list: {str(items)[:120]}")
    out = []
    for x in items:
        if not isinstance(x, dict) or x.get("rule") not in ids:
            raise Transient(f"bad item: {str(x)[:160]}")
        try:
            a, b, c = float(x["t_start"]), float(x["t_end"]), float(x["confidence"])
        except (KeyError, TypeError, ValueError):
            raise Transient(f"bad item: {str(x)[:160]}")
        a, b = max(0.0, min(a, dur)), max(0.0, min(max(a, b), dur))
        out.append({"t_start": round(a, 2), "t_end": round(b, 2), "what": str(x.get("what", ""))[:300],
                    "rule": x["rule"], "confidence": round(max(0.0, min(c, 1.0)), 2)})
    dead = [d for d in out if d["confidence"] < 0.05]
    if len(dead) > 3:       # seen once: it narrated every caption and picture as a "finding" with confidence 0
        raise Transient(f"degenerate answer: {len(dead)} items with confidence 0 (it described the video instead of listing rule breaks)")
    return sorted((d for d in out if d["confidence"] >= 0.05), key=lambda d: (d["t_start"], d["rule"]))


def run(path, fps, model, media_res, thinking, keep, mode="all"):
    from google import genai
    from google.genai import types
    cfg = load_rules()
    if not rule_list(cfg, mode):
        raise NoRules(f"no rules to check: {RULES_PATH} has none and --rules {mode} adds none (--rules all adds the face and frame checks)")
    dur = probe_duration(path)
    prompt = build_prompt(cfg, fps, dur, mode)
    ids = [i for i, _ in rule_list(cfg, mode)]
    client = genai.Client(api_key=api_key(), http_options=types.HttpOptions(timeout=600_000))
    up = None
    t0 = time.time()
    try:
        name = "allframes-" + re.sub(r"[^A-Za-z0-9]+", "-", os.path.basename(path))[:40].strip("-").lower()
        up = with_retries(lambda: client.files.upload(file=path, config=types.UploadFileConfig(mime_type="video/mp4", display_name=name)),
                          "upload")
        t_wait = time.time()
        while up.state is not None and up.state.name != "ACTIVE":
            if up.state.name == "FAILED":
                raise RuntimeError(f"Gemini could not process the upload ({up.name}): {getattr(up, 'error', None)}")
            if time.time() - t_wait > 600:
                raise RuntimeError(f"upload still {up.state.name} after 600 s")
            time.sleep(2)
            up = with_retries(lambda: client.files.get(name=up.name), "file status")
        print(f"uploaded {os.path.basename(path)} ({os.path.getsize(path) / 1e6:.1f} MB), ACTIVE after {time.time() - t0:.0f} s", file=sys.stderr)
        safe = [types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in
                ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")]
        gen = types.GenerateContentConfig(
            response_mime_type="application/json", response_json_schema=schema(ids), temperature=0, safety_settings=safe,
            max_output_tokens=8192, thinking_config=types.ThinkingConfig(thinking_budget=thinking),
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW if media_res == "low" else None)
        part = types.Part(file_data=types.FileData(file_uri=up.uri, mime_type=up.mime_type or "video/mp4"),
                          video_metadata=types.VideoMetadata(fps=fps))

        spent = []

        def ask():
            r = client.models.generate_content(model=model, contents=[types.Content(role="user", parts=[part, types.Part(text=prompt)])], config=gen)
            spent.append(usage_of(r))
            if not r.text:
                fr = getattr(r.candidates[0], "finish_reason", None) if getattr(r, "candidates", None) else None
                pf = getattr(getattr(r, "prompt_feedback", None), "block_reason", None)
                raise RuntimeError(f"no answer (blocked: {pf or fr}); not retried")
            fin = getattr(r.candidates[0].finish_reason, "name", str(r.candidates[0].finish_reason))
            if fin not in ("STOP", "FinishReason.STOP"):
                raise Transient(f"answer cut off ({fin})")
            try:
                items = json.loads(r.text)
            except json.JSONDecodeError as e:
                raise Transient(f"answer is not JSON: {e}")
            return r, clean(items, dur, ids)

        t1 = time.time()
        try:
            r, findings = with_retries(ask, "analysis")
        except Exception:
            if spent:
                print(f"  (the failed attempts were billed too: {total_usage(spent)['attempts']} call(s), ${total_usage(spent)['cost_usd']:.4f})", file=sys.stderr)
            raise
        u = total_usage(spent)
        return {"render": os.path.abspath(path), "model": model, "fps": fps, "media_resolution": media_res, "rules": mode,
                "thinking_budget": thinking, "prompt_version": PROMPT_V, "duration_s": round(dur, 2),
                "seconds": {"upload_and_wait": round(t1 - t0, 1), "analysis": round(time.time() - t1, 1)},
                "usage": u, "cost_usd": u["cost_usd"], "findings": findings}
    finally:
        if up is not None and not keep:
            try:
                client.files.delete(name=up.name)
                print(f"deleted the uploaded file {up.name}", file=sys.stderr)
            except Exception as e:      # noqa: BLE001
                print(f"WARNING: could not delete the uploaded file {up.name}: {e} (Gemini removes it itself after 48 h)", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("render")
    ap.add_argument("--fps", type=float, default=10.0, help="frames per second Gemini samples (default 10; the API maximum is 24)")
    ap.add_argument("--model", default=os.environ.get("ALLFRAMES_MODEL", "gemini-2.5-flash"))
    ap.add_argument("--out", help="result JSON (default: ./<render name>.allframes-<fps>fps.json)")
    ap.add_argument("--media-res", choices=["default", "low"], default="default",
                    help="low = 66 instead of 258 tokens per frame (cheaper at 30 fps, smaller details are lost)")
    ap.add_argument("--rules", choices=["all", "people"], default="all",
                    help="all = people rules + face covered + broken frame; people = only the people rules "
                         "(face cover and broken frames are noisy here, see the notes: the CV checks of render_report.py do those)")
    ap.add_argument("--thinking", type=int, default=4096, help="thinking-token budget (0 = off, -1 = dynamic); default 4096")
    ap.add_argument("--keep-file", action="store_true", help="do not delete the uploaded file at the end")
    a = ap.parse_args()
    if not os.path.exists(a.render):
        print(f"allframes_qa: {a.render} not found", file=sys.stderr)
        sys.exit(2)
    if not 0 < a.fps <= MAX_FPS:
        print(f"allframes_qa: --fps must be in (0, {MAX_FPS}]: the Gemini API refuses a higher frame rate (use {MAX_FPS} for a 30 fps reel)", file=sys.stderr)
        sys.exit(2)
    try:
        res = run(a.render, a.fps, a.model, a.media_res, a.thinking, a.keep_file, a.rules)
    except NoRules as e:
        print(f"allframes_qa: {e}", file=sys.stderr)
        sys.exit(0)
    except Exception as e:      # noqa: BLE001
        print(f"allframes_qa: UNCHECKED, {type(e).__name__}: {str(e)[:400]}", file=sys.stderr)
        sys.exit(2)
    out = a.out or f"{os.path.splitext(os.path.basename(a.render))[0]}.allframes-{a.fps:g}fps.json"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    u = res["usage"]
    print(f"{os.path.basename(a.render)}: {len(res['findings'])} finding(s) at {a.fps:g} fps -> {out}")
    for f in res["findings"]:
        print(f"  {f['t_start']:6.2f}-{f['t_end']:6.2f} s  {f['rule']:<12} conf {f['confidence']:.2f}  {f['what']}")
    print(f"tokens: input {u['prompt_tokens']} {u['by_modality']}, output {u['output_tokens']}, thinking {u['thought_tokens']} "
          f"| {u['attempts']} call(s), cost ${res['cost_usd']:.4f} ({res['model']}, {a.media_res} media res) | {res['seconds']['analysis']} s")
    sys.exit(1 if res["findings"] else 0)


if __name__ == "__main__":
    main()
