#!/usr/bin/env python3
"""Caption words from verified SOURCE word times (Whisper medium, text checked against
Gemini 2.5 Pro and the speaker), mapped to edit time through build/edl_map.json.
Robust to re-cuts: edit edl.json, run assemble.py, then this. -> build/words.fixed.json

Type the text yourself: whisper heard "lunch" as "lunge" here and wrote a "Thank you." into the silence at a clip's end.
Starts are the voice onsets (whisper stretches a first word back over the silence before it)."""
import json

LINES = [  # (clip, [(word, start, end), ...]) one sentence each, source seconds
    ("gull", [("20", 41.02, 41.22), ("minutes", 41.22, 41.58), ("at", 41.58, 41.78), ("the", 41.78, 41.9), ("seaside,", 41.9, 42.4),
              ("and", 42.4, 42.54), ("I've", 42.54, 42.8), ("already", 42.8, 43.14), ("lost", 43.14, 43.44), ("my", 43.44, 43.7),
              ("lunch.", 43.7, 44.12)]),
    ("pier", [("Okay,", 8.02, 8.28), ("look", 8.8, 8.92), ("at", 8.92, 9.04), ("that", 9.04, 9.22), ("water.", 9.22, 9.56)]),
    ("kiosk", [("One", 4.02, 4.22), ("large", 4.22, 4.54), ("fries,", 4.54, 5.04), ("please.", 5.22, 5.58)]),
    ("bench", [("Did", 5.02, 5.14), ("you", 5.14, 5.26), ("know", 5.26, 5.46), ("gulls", 5.46, 5.72), ("can", 5.72, 5.92),
               ("remember", 5.92, 6.32), ("your", 6.32, 6.54), ("face?", 6.54, 6.96)]),
    ("bench", [("This", 9.52, 9.68), ("one", 9.68, 9.86), ("is", 9.86, 10.02), ("definitely", 10.02, 10.46), ("remembering", 10.46, 11.1),
               ("mine.", 11.1, 11.52)]),
    ("gull", [("No,", 18.62, 18.82), ("no,", 19.1, 19.42), ("no!", 19.66, 19.96)]),
    ("gull", [("That", 20.28, 20.54), ("was", 20.54, 20.7), ("my", 20.7, 20.92), ("lunch!", 20.92, 21.26)]),
]
mp = json.load(open("build/edl_map.json"))


def to_edit(clip, t):
    for s in mp:
        if s["clip"] == clip and s["speed"] > 0 and s["src_a"] <= t < s["src_b"]:
            return round(s["edit_start"] + (t - s["src_a"]) / s["speed"], 3)
    return None


segs = []
for clip, ws in LINES:
    words = []
    for w, a, b in ws:
        ea, eb = to_edit(clip, a), to_edit(clip, min(b, b - 1e-3))
        if ea is None or eb is None:
            continue  # this word's source moment is not in the cut
        words.append({"word": " " + w, "start": ea, "end": max(eb, ea + 0.08), "probability": 1.0})
    if words:
        segs.append({"start": words[0]["start"], "end": words[-1]["end"], "text": "".join(w["word"] for w in words), "words": words})
d = {"text": "".join(s["text"] for s in segs), "segments": segs, "language": "en"}
json.dump(d, open("build/words.fixed.json", "w"), ensure_ascii=False, indent=1)
for s in segs:
    print(f"{s['start']:6.2f}-{s['end']:6.2f} {s['text']}")
