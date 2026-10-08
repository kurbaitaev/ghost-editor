#!/usr/bin/env python3
"""Caption words from verified SOURCE word times (Whisper medium, text checked against
Gemini 2.5 Pro and the speaker), mapped to edit time through build/edl_map.json.
Robust to re-cuts: edit edl.json, run assemble.py, then this. -> build/words.fixed.json"""
import json

LINES = [  # (clip, [(word, start, end), ...]) one sentence each, source seconds
    ("5875", [("У", 3.46, 3.58), ("нас", 3.58, 4.0), ("39", 4.0, 4.8), ("минут,", 4.8, 5.48), ("блин,", 5.7, 5.88),
              ("я", 5.94, 6.04), ("немного", 6.04, 6.42), ("опоздал.", 6.42, 7.2)]),
    ("5851", [("Офигеть.", 24.14, 25.4)]),
    ("5851", [("Идём", 43.98, 44.66), ("на", 44.66, 44.84), ("велик.", 44.84, 45.18)]),
    ("5869", [("Какой", 5.94, 6.72), ("красивый", 6.72, 7.24), ("Сан-Фран.", 7.24, 7.81)]),
    ("5869", [("Вон", 9.78, 9.96), ("ту", 9.96, 10.3), ("башню", 11.18, 11.5), ("кто-то", 11.5, 11.8), ("узнает?", 11.8, 12.42),
              ("Из", 12.84, 13.0), ("GTA.", 13.0, 13.6)]),
    ("5869", [("Я", 15.42, 15.64), ("на", 15.64, 15.7), ("неё", 15.7, 15.84), ("залетал", 15.84, 16.26), ("постоянно.", 16.26, 17.04)]),
    ("5887", [("Не,", 133.68, 133.84), ("не,", 133.84, 134.08), ("не.", 134.08, 134.4)]),
    ("5887", [("Он", 135.46, 135.86), ("мне", 135.86, 136.04), ("засадить", 136.04, 136.48), ("хотел,", 136.48, 136.88),
              ("что", 136.88, 136.96), ("ли?", 136.96, 137.2)]),
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
d = {"text": "".join(s["text"] for s in segs), "segments": segs, "language": "ru"}
json.dump(d, open("build/words.fixed.json", "w"), ensure_ascii=False, indent=1)
for s in segs:
    print(f"{s['start']:6.2f}-{s['end']:6.2f} {s['text']}")
