"""Clean OS kit: the small parts that recur inside most Clean OS components (iOS chrome, list rows and toggles, counters,
bars and sliders, activity rings, taps, typing, notification stacks, alerts, shakes).

A reel composes them into its OWN new component (a scene, a chest card, a top widget). The catalog tracks components,
not parts: a counter or a toggle is not a repeat, the Wi-Fi list it sits in is. Every helper takes the reel R first
when it animates; HTML helpers return a string. Their CSS (kit.CSS) is on every Clean OS page already.

    K.status() + K.nav("Settings") + K.title("Notifications", "214 today")
    K.rows([{"name": "Mail", "icon": K.icon("mail", "#0A84FF", 88), "right": K.toggle(True, "t0")}, ...], top=480)
    K.flip(R, "#t0", R.t("mail"))               K.counter(R, "#n", 214, 41, a, b)      K.fill(R, "#bar i", .2, .9, a, b)
"""
from facereel import esc, r3

# white glyphs on system-colour squares (viewBox 0 0 80 80; currentColor = the square's colour)
GLY = {
    "folder": '<path d="M12 24h20l6 7h30v33a4 4 0 0 1-4 4H16a4 4 0 0 1-4-4z" fill="#fff"/>',
    "pin": '<path d="M40 10a19 19 0 0 1 19 19c0 15-19 38-19 38S21 44 21 29a19 19 0 0 1 19-19z" fill="#fff"/><circle cx="40" cy="29" r="7" fill="currentColor"/>',
    "note": '<rect x="18" y="12" width="44" height="56" rx="6" fill="#fff"/><path d="M26 28h28M26 38h28M26 48h18" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>',
    "bubble": '<path d="M16 16h48a6 6 0 0 1 6 6v28a6 6 0 0 1-6 6H36l-14 11V56h-6a6 6 0 0 1-6-6V22a6 6 0 0 1 6-6z" fill="#fff"/>',
    "heart": '<path d="M40 64S14 48 14 30a13 13 0 0 1 26-4 13 13 0 0 1 26 4c0 18-26 34-26 34z" fill="#fff"/>',
    "phone": '<path d="M26 14l10 12-6 7c3 7 8 12 15 15l7-6 12 10-6 9c-20 0-41-21-41-41z" fill="#fff"/>',
    "search": '<circle cx="35" cy="35" r="17" fill="none" stroke="#fff" stroke-width="7"/><path d="M48 48l14 14" stroke="#fff" stroke-width="8" stroke-linecap="round"/>',
    "photos": '<g opacity=".95"><circle cx="40" cy="25" r="11" fill="#FFCC00"/><circle cx="55" cy="40" r="11" fill="#34C759"/><circle cx="40" cy="55" r="11" fill="#0A84FF"/><circle cx="25" cy="40" r="11" fill="#FF3B30"/></g>',
    "wallet": '<rect x="14" y="20" width="52" height="40" rx="7" fill="#fff"/><rect x="14" y="30" width="52" height="8" fill="currentColor"/>',
    "clock": '<circle cx="40" cy="40" r="25" fill="none" stroke="#fff" stroke-width="6"/><path d="M40 26v15l10 6" stroke="#fff" stroke-width="6" stroke-linecap="round" fill="none"/>',
    "check": '<circle cx="40" cy="40" r="25" fill="#fff"/><path d="M28 41l8 8 16-17" stroke="currentColor" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "lang": '<text x="40" y="52" text-anchor="middle" font-family="Inter" font-weight="800" font-size="34" fill="#fff">Аа</text>',
    "cal": '<rect x="16" y="18" width="48" height="46" rx="8" fill="#fff"/><rect x="16" y="18" width="48" height="12" rx="6" fill="#FF3B30"/>',
    "wave": '<path d="M16 40h4M26 30v20M36 22v36M46 30v20M56 34v12M64 40h2" stroke="#fff" stroke-width="6" stroke-linecap="round"/>',
    "box": '<path d="M40 12l26 13v30L40 68 14 55V25z" fill="#fff"/><path d="M14 25l26 13 26-13M40 38v30" stroke="currentColor" stroke-width="4" fill="none"/>',
    "shop": '<path d="M14 30l6-14h40l6 14v6a8 8 0 0 1-16 0 8 8 0 0 1-16 0 8 8 0 0 1-16 0z" fill="#fff"/><rect x="18" y="44" width="44" height="22" rx="3" fill="#fff"/>',
    "share": '<rect x="18" y="32" width="44" height="36" rx="7" fill="none" stroke="#fff" stroke-width="6"/><path d="M40 12v34M28 24l12-12 12 12" stroke="#fff" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "lock": '<rect x="18" y="36" width="44" height="32" rx="7" fill="#fff"/><path d="M27 36v-8a13 13 0 0 1 26 0v8" stroke="#fff" stroke-width="6" fill="none"/>',
    "battery": '<rect x="10" y="26" width="52" height="28" rx="7" fill="none" stroke="#fff" stroke-width="5"/><rect x="64" y="34" width="6" height="12" rx="2" fill="#fff"/>',
    "chart": '<path d="M14 58l16-16 12 10 24-26" stroke="#fff" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "cash": '<rect x="12" y="22" width="56" height="36" rx="6" fill="#fff"/><circle cx="40" cy="40" r="9" fill="currentColor"/>',
    "gear": '<circle cx="40" cy="40" r="11" fill="none" stroke="#fff" stroke-width="7"/><path d="M40 12v10M40 58v10M12 40h10M58 40h10M20 20l7 7M53 53l7 7M20 60l7-7M53 27l7-7" stroke="#fff" stroke-width="7" stroke-linecap="round"/>',
    "bell": '<path d="M40 14a16 16 0 0 1 16 16v14l6 9H18l6-9V30a16 16 0 0 1 16-16z" fill="#fff"/><circle cx="40" cy="62" r="6" fill="#fff"/>',
    "moon": '<path d="M52 14a26 26 0 1 0 14 40A22 22 0 0 1 52 14z" fill="#fff"/>',
    "mail": '<rect x="12" y="20" width="56" height="40" rx="7" fill="#fff"/><path d="M14 24l26 20 26-20" stroke="currentColor" stroke-width="5" fill="none"/>',
    "user": '<circle cx="40" cy="30" r="13" fill="#fff"/><path d="M16 66a24 20 0 0 1 48 0z" fill="#fff"/>',
    "play": '<path d="M28 18l34 22-34 22z" fill="#fff"/>',
    "wifi": '<path d="M12 32a40 40 0 0 1 56 0M22 42a26 26 0 0 1 36 0M32 52a12 12 0 0 1 16 0" stroke="#fff" stroke-width="7" fill="none" stroke-linecap="round"/><circle cx="40" cy="62" r="5" fill="#fff"/>',
    "star": '<path d="M40 12l8 18 19 2-14 13 4 19-17-10-17 10 4-19-14-13 19-2z" fill="#fff"/>',
    "map": '<path d="M14 20l16-6 20 6 16-6v46l-16 6-20-6-16 6z" fill="#fff"/><path d="M30 14v46M50 20v46" stroke="currentColor" stroke-width="4"/>',
    "bell-slash": '<path d="M40 14a16 16 0 0 1 16 16v14l6 9H18l6-9V30a16 16 0 0 1 16-16z" fill="#fff"/><circle cx="40" cy="62" r="6" fill="#fff"/><path d="M14 14l52 52" stroke="currentColor" stroke-width="9"/><path d="M14 14l52 52" stroke="#fff" stroke-width="4" stroke-linecap="round"/>',
    "camera": '<rect x="12" y="24" width="56" height="38" rx="8" fill="#fff"/><circle cx="40" cy="43" r="11" fill="currentColor"/><rect x="30" y="16" width="20" height="10" rx="3" fill="#fff"/>',
}


def icon(name, bg, size=150, radius=None, cls="appi", style=""):
    """an app icon: a white glyph (GLY) on a coloured squircle; also a plain character (an emoji or a letter) as name"""
    r = radius or int(size * 0.24)
    col = bg if bg.startswith("#") else "#333"
    g = GLY.get(name)
    inner = (f'<svg viewBox="0 0 80 80" width="{int(size * 0.62)}" height="{int(size * 0.62)}">{g}</svg>' if g
             else f'<span style="font-size:{int(size * 0.56)}px;line-height:1;color:#fff">{esc(name)}</span>')
    return (f'<div class="{cls}" style="width:{size}px;height:{size}px;border-radius:{r}px;background:{bg};color:{col};{style}">{inner}</div>')


def gly(name, size=60, color="#fff", accent="#0A84FF"):
    """a bare glyph (no square), e.g. inside a row or a button"""
    return f'<svg viewBox="0 0 80 80" width="{size}" height="{size}" style="color:{accent}">{GLY[name].replace("#fff", color)}</svg>'


# ---------------------------------------------------------------- iOS chrome
def status(time="9:41", dark=False):
    """the status bar (time, signal, battery) at the top of a scene"""
    return f'<div class="status{" dk" if dark else ""}"><span>{time}</span><span class="sb"><i></i><i></i><i></i><b></b></span></div>'


def nav(back, right=""):
    """the navigation bar: ‹ back (accent colour) and an optional right action"""
    return f'<div class="nav"><span>‹ {esc(back)}</span><span>{esc(right)}</span></div>'


def title(big, small="", top=190):
    """the large title of an iOS screen, a grey line under it"""
    sm = f"<small>{small}</small>" if small else ""
    return f'<div class="big" style="top:{top}px">{big}{sm}</div>'


def section(text, top):
    """a grey section label above a group («TURN OFF WHAT YOU DON'T NEED»)"""
    return f'<div class="lbl" style="top:{top}px">{esc(text)}</div>'


def rows(items, top, left=40, right=40, cls=""):
    """a white rounded group of rows. item: {"name", "sub", "icon" (html), "right" (html: toggle(), a value, a chevron),
    "id"}. Returns the group html."""
    out = []
    for it in items:
        rid = f' id="{it["id"]}"' if it.get("id") else ""
        sub = f'<span class="sub">{it["sub"]}</span>' if it.get("sub") else ""
        out.append(f'<div class="row"{rid}>{it.get("icon", "")}<div class="nm">{it["name"]}{sub}</div>{it.get("right", "")}</div>')
    return f'<div class="grp {cls}" style="top:{top}px;left:{left}px;right:{right}px">{"".join(out)}</div>'


def ricon(name, bg):
    """an icon sized for a list row"""
    return icon(name, bg, 88, cls="ric")


def toggle(on=True, tid=None):
    """an iOS switch (html). Flip it with flip()"""
    i = f' id="{tid}"' if tid else ""
    return f'<span class="tgl{" on" if on else ""}"{i}><i></i></span>'


def flip(R, sel, t, on=False, snd="tech-ui-confirm"):
    """flip a toggle() at t (to on or off), with a small confirm sound"""
    acc = "#34C759" if on else "#E3E3E8"
    R.tween(sel, {}, {"backgroundColor": acc, "duration": 0.16}, t)
    R.tween(f"{sel} i", {}, {"x": 48 if on else 0, "duration": 0.18, "ease": "power2.out"}, t)
    if snd:
        R.sound(snd, t, f"toggle {sel}")


def chevron(text=""):
    """a grey value + › at the right of a row"""
    return f'<span class="chev">{esc(text)} ›</span>'


# ---------------------------------------------------------------- numbers, bars, rings
def hm(m):
    """minutes -> «4 ч 52 мин»"""
    m = int(round(m))
    return f"{m // 60} ч {m % 60:02d} мин"


def mmss(s):
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def thousands(v):
    """12345 -> «12 345» (a thin space)"""
    return f"{int(round(v)):,}".replace(",", " ")


def counter(R, sel, v0, v1, t0, t1, fmt=None, steps=12):
    """a number that rolls from v0 to v1 over [t0, t1] (textContent steps; tabular figures look best)"""
    fmt = fmt or (lambda v: str(int(round(v))))
    for k in range(steps + 1):
        v = v0 + (v1 - v0) * k / steps
        R.st(sel, {"textContent": fmt(v)}, t0 + (t1 - t0) * k / steps)


def bar(bid, frac=0.0, color="%ACC%", h=14, track="rgba(120,120,128,.2)"):
    """a progress bar (html) filled to `frac`; grow / shrink it with fill()"""
    return (f'<div class="kbar" style="height:{h}px;border-radius:{h // 2}px;background:{track}"><i id="{bid}" '
            f'style="background:{color};width:{100 * frac:.1f}%"></i></div>')


def fill(R, sel, f0, f1, t0, t1, ease="power2.out"):
    """grow / shrink a bar() from f0 to f1 (0..1) over [t0, t1]"""
    R.ft(sel, {"width": f"{100 * f0:.1f}%"}, {"width": f"{100 * f1:.1f}%", "duration": r3(max(0.05, t1 - t0)), "ease": ease}, t0)


def slider(sid, frac=0.5, color="#fff", w=150, h=420):
    """a Control Center slider (vertical, html) filled to `frac`; move it with fill_v()"""
    return (f'<div class="ksl" style="width:{w}px;height:{h}px;border-radius:{w // 3}px"><i id="{sid}" '
            f'style="background:{color};height:{100 * frac:.1f}%"></i></div>')


def fill_v(R, sel, f0, f1, t0, t1, ease="power2.inOut"):
    """move a slider() from f0 to f1 (0..1) over [t0, t1]"""
    R.ft(sel, {"height": f"{100 * f0:.1f}%"}, {"height": f"{100 * f1:.1f}%", "duration": r3(max(0.05, t1 - t0)), "ease": ease}, t0)


def rings(rid, colors, size=230, width=24):
    """concentric activity rings (svg), outermost first; close one with ring(R, f"#{rid}-0", t)"""
    c, out = size / 2, []
    for k, col in enumerate(colors):
        r = c - width / 2 - k * (width + 4)
        out.append(f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{col}" stroke-opacity=".25" stroke-width="{width}"/>'
                   f'<circle id="{rid}-{k}" cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{col}" stroke-width="{width}" stroke-linecap="round" '
                   f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" transform="rotate(-90 {c} {c})"/>')
    return f'<svg class="krings" viewBox="0 0 {size} {size}" width="{size}" height="{size}">{"".join(out)}</svg>'


def ring(R, sel, t, to=1.0, dur=0.55, snd="tech-ui-confirm"):
    """close a ring of rings() to `to` (0..1) at t"""
    R.ft(sel, {"strokeDashoffset": 1}, {"strokeDashoffset": round(1 - to, 3), "duration": dur, "ease": "power2.out"}, t)
    if snd:
        R.sound(snd, t + dur - 0.1, f"ring {sel}")


# ---------------------------------------------------------------- gestures, typing, stacks
def tap(R, sel, t, ripple=None, snd="click-1"):
    """a finger tap on an element at t: it presses in and springs back; `ripple` = the selector of a ripple() element"""
    R.tween(sel, {"scale": 1}, {"scale": 0.9, "duration": 0.07, "yoyo": True, "repeat": 1}, t)
    if ripple:
        R.ft(ripple, {"autoAlpha": 0.9, "scale": 0.3}, {"autoAlpha": 0, "scale": 1.9, "duration": 0.45, "ease": "power2.out"}, t)
    if snd:
        R.sound(snd, t, f"tap {sel}")


def ripple(rid, x, y, d=120):
    """a white tap ripple (html) centred at x, y inside its parent"""
    return f'<i id="{rid}" class="krip" style="left:{x - d // 2}px;top:{y - d // 2}px;width:{d}px;height:{d}px"></i>'


def typing(R, sel, text, t0, t1, snd="tech-keyboard-burst"):
    """type `text` into an element over [t0, t1] (one character at a time); put caret() after the element for a caret"""
    n = max(1, len(text))
    for k in range(n + 1):
        R.st(sel, {"textContent": text[:k]}, t0 + (t1 - t0) * k / n)
    if snd:
        R.sound(snd, t0, f"typing {sel}", maxlen=max(0.3, t1 - t0))


def caret(cid="kcar"):
    """a text caret (html) in the accent colour; blink() it"""
    return f'<i id="{cid}" class="kcar"></i>'


def blink(R, sel, t0, t1, period=0.5):
    """blink a caret() on [t0, t1] (seek-safe: one set per half period)"""
    k, t = 0, t0
    while t < t1:
        R.st(sel, {"opacity": 0 if k % 2 else 1}, t)
        k += 1; t += period / 2
    R.st(sel, {"opacity": 0}, t1)


def stack(R, ids, times, dy=18, snds=("tech-notification-2", "ding-1")):
    """notification banners land one by one at `times`; the older ones settle behind the newest (smaller, dimmer)"""
    for k, (i, t) in enumerate(zip(ids, times)):
        R.ft(f"#{i}", {"autoAlpha": 0, "y": -60}, {"autoAlpha": 1, "y": 0, "duration": 0.2, "ease": "back.out(1.5)"}, t)
        for j in range(k):
            d0, d1 = k - j - 1, k - j
            R.tween(f"#{ids[j]}", {"y": dy * d0, "scale": 1 - 0.04 * d0, "opacity": 1 - 0.25 * d0},
                    {"y": dy * d1, "scale": 1 - 0.04 * d1, "opacity": 1 - 0.25 * d1, "duration": 0.2, "ease": "power2.out"}, t)
        if snds:
            R.sound(snds[k % len(snds)], t, f"banner {i}")


def banner(bid, icon_html, app, title, body, when="сейчас", style=""):
    """an iOS notification banner (html): icon, app, time, a bold title and one line"""
    return (f'<div id="{bid}" class="kban" style="{style}">{icon_html}<div class="btx"><div class="bhd"><b>{esc(app)}</b><span>{esc(when)}</span></div>'
            f'<div class="bti">{title}</div><div class="bbo">{body}</div></div></div>')


def alert(title, msg, buttons=("Позже", "Начать"), ids=("ka0", "ka1")):
    """a two-button iOS alert (html); tap a button with press()"""
    bt = "".join(f'<span id="{i}">{esc(b)}</span>' for i, b in zip(ids, buttons))
    return f'<div class="kalert"><div class="t">{title}</div><div class="m">{msg}</div><div class="bt">{bt}</div></div>'


def press(R, sel, t, color="%ACC%"):
    """an alert / sheet button is pressed at t: it fills with the accent and its text turns white"""
    R.tween(sel, {}, {"backgroundColor": color, "color": "#ffffff", "duration": 0.1}, t)
    R.sound("click-1", t, f"press {sel}")


def shake(R, sel, t, n=5, dx=9):
    """a 'no' shake (iOS wrong password) at t"""
    R.tween(sel, {"x": 0}, {"x": dx, "duration": 0.05, "yoyo": True, "repeat": n, "ease": "sine.inOut"}, t)


def highlight(R, sel, t, dur=0.45, color="#FFE58A"):
    """a marker highlight sweeps under a <mark> at t (put the text in <mark class="khl">)"""
    R.ft(sel, {"backgroundSize": "0% 100%"}, {"backgroundSize": "100% 100%", "duration": dur, "ease": "power2.inOut"}, t)


CSS = """
.status { position: absolute; left: 76px; right: 70px; top: 46px; display: flex; justify-content: space-between; align-items: center; font-size: 32px; font-weight: 600; z-index: 5; }
.status .sb { display: flex; gap: 6px; align-items: flex-end; }
.status .sb i { display: block; width: 8px; background: currentColor; border-radius: 2px; } .status .sb i:nth-child(1) { height: 12px; } .status .sb i:nth-child(2) { height: 18px; } .status .sb i:nth-child(3) { height: 24px; }
.status .sb b { display: block; width: 46px; height: 22px; border: 3px solid currentColor; border-radius: 7px; margin-left: 10px; box-sizing: border-box; position: relative; }
.status .sb b::after { content: ""; position: absolute; left: 2px; top: 2px; bottom: 2px; width: 70%; background: currentColor; border-radius: 3px; }
.status.dk { color: #fff; }
.nav { position: absolute; left: 50px; right: 50px; top: 118px; display: flex; justify-content: space-between; font-size: 38px; color: %ACC%; }
.big { position: absolute; left: 60px; right: 60px; font-size: 88px; font-weight: 800; letter-spacing: -0.04em; line-height: 1; }
.big small { display: block; font-size: 34px; font-weight: 500; color: #8E8E93; letter-spacing: 0; margin-top: 16px; }
.lbl { position: absolute; left: 76px; font-size: 28px; color: #8E8E93; letter-spacing: .04em; }
.grp { position: absolute; background: #fff; border-radius: 32px; overflow: hidden; }
.row { display: flex; align-items: center; gap: 28px; padding: 30px 34px; border-bottom: 1px solid #E5E5EA; } .row:last-child { border: 0; }
.nm { flex: 1; min-width: 0; font-size: 48px; font-weight: 600; } .nm .sub, .nm small { display: block; font-size: 30px; font-weight: 400; color: #8E8E93; margin-top: 4px; }
.ric { position: relative; display: flex; align-items: center; justify-content: center; flex: none; }
.chev { font-size: 40px; color: #8E8E93; flex: none; }
.tgl { position: relative; flex: none; display: block; width: 120px; height: 72px; border-radius: 36px; background: #E3E3E8; }
.tgl.on { background: #34C759; }
.tgl i { position: absolute; left: 6px; top: 6px; width: 60px; height: 60px; border-radius: 30px; background: #fff; box-shadow: 0 3px 8px rgba(0,0,0,.2); }
.tgl.on i { transform: translateX(48px); }
.kbar { position: relative; overflow: hidden; } .kbar i { position: absolute; left: 0; top: 0; bottom: 0; display: block; }
.ksl { position: relative; overflow: hidden; background: rgba(120,120,128,.35); } .ksl i { position: absolute; left: 0; right: 0; bottom: 0; display: block; }
.krings { display: block; }
.krip { position: absolute; border-radius: 50%; background: rgba(255,255,255,.75); opacity: 0; pointer-events: none; }
.kcar { display: inline-block; width: 4px; height: 1em; background: %ACC%; margin-left: 2px; vertical-align: -0.12em; }
.kban { display: flex; gap: 22px; align-items: flex-start; padding: 22px 26px; border-radius: 36px; background: rgba(246,246,248,.95); color: #111;
  box-shadow: 0 10px 34px rgba(0,0,0,.28); box-sizing: border-box; }
.kban .appi { position: relative; opacity: 1; box-shadow: none; flex: none; }
.btx { flex: 1; min-width: 0; } .bhd { display: flex; justify-content: space-between; font-size: 26px; color: #6C6C70; } .bhd b { color: #3A3A3C; font-weight: 600; }
.bti { font-size: 32px; font-weight: 700; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bbo { font-size: 30px; color: #3A3A3C; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kalert { background: rgba(246,246,248,.96); color: #111; border-radius: 40px; overflow: hidden; text-align: center; box-shadow: 0 20px 60px rgba(0,0,0,.4); }
.kalert .t { padding: 40px 40px 8px; font-size: 44px; font-weight: 700; } .kalert .m { padding: 0 40px 34px; font-size: 34px; color: #3a3a3c; }
.kalert .bt { display: flex; border-top: 1px solid rgba(60,60,67,.29); } .kalert .bt span { flex: 1; padding: 28px 0; font-size: 42px; color: %ACC%; }
.kalert .bt span:first-child { border-right: 1px solid rgba(60,60,67,.29); } .kalert .bt span:last-child { font-weight: 700; }
mark.khl { color: inherit; background: linear-gradient(#FFE58A, #FFE58A) no-repeat 0 0 / 0% 100%; padding: 2px 6px; border-radius: 6px; }
"""
