#!/usr/bin/env python3
"""Generate a still B-roll image with Gemini (vertical 9:16 by default).

    broll_gen.py "<prompt>" <out.png> [--aspect 9:16] [--model gemini-2.5-flash-image]

Needs GEMINI_API_KEY in the environment (or in <skill>/.env, gitignored);
the key is never printed. Needs google-genai (pip install google-genai).
Look at the image before using it: AI images get hands, text and logos wrong.
"""
import argparse
import os
import sys

FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


def key():
    k = os.environ.get("GEMINI_API_KEY")
    if not k and os.path.exists(FALLBACK):
        for line in open(FALLBACK):
            if line.startswith("GEMINI_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"')
    if not k:
        sys.exit("GEMINI_API_KEY not set")
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("out")
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--model", default="gemini-2.5-flash-image")
    a = ap.parse_args()
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key())
    cfg = types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio=a.aspect))
    resp = client.models.generate_content(model=a.model, contents=a.prompt, config=cfg)
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            open(a.out, "wb").write(part.inline_data.data)
            print(f"-> {a.out} ({len(part.inline_data.data) // 1024} KB, {a.model}, {a.aspect})")
            return
    sys.exit("no image in the response: " + str(resp)[:400])


if __name__ == "__main__":
    main()
