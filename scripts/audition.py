#!/usr/bin/env python3
"""Write library/audition.html: a soundboard of every SFX (with its role,
tags, source and licence) and every meme (preview + playable clip), so a
human can listen and look before a sound or meme goes into a reel.

    audition.py [--open]

Automated checks cannot tell a good vine boom from a bad rip; ears can.
Sounds flagged in manifest.json with "review" show a badge.
"""
import argparse
import html
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "library"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    sfx = json.load(open(os.path.join(LIB, "sfx", "manifest.json")))
    rows = []
    for role in ("meme", "impact", "whoosh", "ui"):
        for k, v in sfx.items():
            if v["role"] != role:
                continue
            flag = f'<span class="flag">{html.escape(v["review"])}</span>' if v.get("review") else ""
            rows.append(f'<tr><td><b>{k}</b>{flag}</td><td>{role}</td><td><audio controls preload="none" src="sfx/{v["file"]}"></audio></td>'
                        f'<td>{v["duration"]:.2f}s</td><td>{", ".join(v["tags"])}</td><td class="src">{html.escape(v["source"])}<br><i>{html.escape(v["licence"])}</i></td></tr>')
    cards = []
    mdir = os.path.join(LIB, "memes")
    for d in sorted(os.listdir(mdir)):
        p = os.path.join(mdir, d, "meta.json")
        if not os.path.exists(p):
            continue
        m = json.load(open(p))
        media = f'<video controls preload="none" poster="memes/{d}/preview.png" src="memes/{d}/{m["clip"]}"></video>' if m.get("clip") else f'<img src="memes/{d}/{m["image"]}">'
        cards.append(f'<div class="card">{media}<div><b>{html.escape(m["name"])}</b> <code>{d}</code> <span class="t {m["trend_status"]}">{m["trend_status"]}</span></div>'
                     f'<div>{", ".join(m["emotion"])}</div><div class="u">{html.escape(m["use_case"])}</div></div>')
    page = f"""<!doctype html><meta charset="utf-8"><title>ghost-editor library</title>
<style>body{{font:14px system-ui;margin:24px;background:#111;color:#eee}}table{{border-collapse:collapse;width:100%}}td{{border-bottom:1px solid #333;padding:6px 8px;vertical-align:middle}}
.src{{color:#999;font-size:12px}}.flag{{background:#b33;color:#fff;border-radius:6px;padding:1px 6px;margin-left:6px;font-size:11px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}}.card{{background:#1c1c1f;border-radius:12px;padding:10px}}
.card video,.card img{{width:100%;border-radius:8px;background:repeating-conic-gradient(#444 0 25%,#666 0 50%) 0/20px 20px}}
.u{{color:#aaa;font-size:12px}}.t{{font-size:11px;padding:1px 6px;border-radius:6px;background:#333}}.hot{{background:#c2410c}}.dying{{background:#555}}</style>
<h1>Sound effects ({len(sfx)})</h1><table>{''.join(rows)}</table><h1>Memes ({len(cards)})</h1><div class="grid">{''.join(cards)}</div>"""
    out = os.path.join(LIB, "audition.html")
    open(out, "w").write(page)
    print(out)
    if a.open:
        subprocess.run(["open", out])


if __name__ == "__main__":
    main()
