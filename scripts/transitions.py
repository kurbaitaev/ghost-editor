#!/usr/bin/env python3
"""Eased transitions for talking-head reels on stock ffmpeg 8 (no custom build).

Built on xfade-easing (scriptituk, MIT): its standard easings and its ~70 transitions (xfade's own plus
GLSL gl-transitions ported to ffmpeg expressions) are read from scripts/vendor/xfade-easing/*.txt.
Added here: CSS ease / cubic-bezier() easings in expression form (upstream has them only in its patched
ffmpeg), a per-frame easing cache, two own transitions (zoomblur, whip) that take overshoot, frame-exact
centred timing with handles, audio as a hard cut or a short crossfade, and three render engines:
  native  xfade's built-in C transitions (fade, fadeblack, smoothleft, ...) eased by warping the
          transition frames' timestamps: as fast as a plain xfade.
  numpy   own zoomblur / whip with OpenCV remaps on the YUV planes.
  expr    xfade custom expressions (the gl_* ports), rendered in parallel chunks across CPU cores
          (expressions need -filter_complex_threads 1, so one process is one core).
Every junction is rendered as a short window clip; one concat pass then assembles the edit.

  transitions.py list [--all]
  transitions.py join  A.mp4@5.0-6.25 B.mp4@15.7-16.95 -t crosswarp -o out.mp4 [--size 540x960]
  transitions.py join  --edl edl.json -o out.mp4                  # many cuts, a transition per junction
  transitions.py junction A.mp4@6.25 B.mp4@15.7 -t dissolve -o tx.mp4   # only the overlay clip
  transitions.py reel  <project>                                   # reel.json "transitions" -> assets/tx/
  transitions.py expr  -t gl_crosswarp -e 'cubic-bezier(.2,.8,.2,1)'   # print the xfade expr

Timing: a transition of duration d is centred on the cut. The outgoing clip plays d/2 past its out
point and the incoming clip starts d/2 before its in point (handles), so the edit keeps its length
and every word stays where it was. The voice stays a hard cut (10 ms declick) unless --audio xfade.
"""
import argparse
import concurrent.futures as cf
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from x264 import THREADS as X264_THREADS  # noqa: E402  (scripts/X264_THREADS)
XE = HERE / "vendor" / "xfade-easing"   # MIT, scriptituk/xfade-easing v3.6.6 (expression files, verbatim)
TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
# The expr engine splits a window into this many chunks (parallel ffmpeg processes). Fixed, not the core count: each
# chunk evaluates the expression on its own remapped progress, so other chunk bounds give slightly different pixels
# (7 chunks on an 8-core Mac and 9 on a 10-core one made different files).
EXPR_CHUNKS = 8

# ---------------------------------------------------------------- curated set for talking heads
# name -> base transition, default easing, default duration (s), kind, one-line description
CURATED = {
    # subtle: hide a jump cut or a take change without calling attention to it
    "dissolve":      dict(t="fade", e="ease-in-out", d=0.40, kind="subtle",
                          what="Eased cross-dissolve; the default for hiding a jump cut."),
    "zoom_blur":     dict(t="zoomblur", e="cubic-bezier(0.7,0,0.3,1)", d=0.50, kind="subtle",
                          what="Push into the face with a radial blur, the next shot settles out of the blur."),
    "soft_wipe":     dict(t="softwipe", e="cubic-bezier(0.65,0,0.35,1)", d=0.50, kind="subtle",
                          what="Feathered directional wipe (right to left) with a slight parallax push."),
    "crosswarp":     dict(t="gl_crosswarp", e="cubic-in-out", d=0.60, kind="subtle",
                          what="Morph-like warp: both shots stretch toward each other while blending."),
    "warp_wipe":     dict(t="gl_directionalwarp", e="quadratic-in-out", d=0.60, kind="subtle",
                          what="Diagonal wipe whose edge warps the image as it passes."),
    "dip_black":     dict(t="fadeblack", e="sinusoidal-in-out", d=0.50, kind="subtle",
                          what="Dip to black between sections, a breath."),
    # punchy: section changes, hooks, a beat drop
    "whip":          dict(t="whip", e="cubic-bezier(0.55,0,0.25,1.12)", d=0.35, kind="punchy",
                          what="Whip-pan push with motion blur and a small spring overshoot."),
    "scaled_push":   dict(t="gl_DirectionalScaled", e="quartic-in-out", d=0.55, kind="punchy",
                          what="Shot shrinks and slides up as the next one pushes in (card-swipe feel)."),
    "flash":         dict(t="fadewhite", e="exponential-in-out", d=0.30, kind="punchy",
                          what="White exposure flash through the cut."),
    "static_wipe":   dict(t="gl_static_wipe", e="linear", d=0.50, kind="punchy",
                          what="A band of TV static sweeps down and leaves the new shot behind it."),
}
ALIASES = {"cut": "cut", "none": "cut"}
# names that would otherwise be shadowed by a curated preset ("dissolve" = eased fade)
RENAMES = {"pixel_dissolve": "DISSOLVE"}  # ffmpeg's pixel dissolve, via the expression port

# ---------------------------------------------------------------- easing
CSS = {"linear": (0, 0, 1, 1), "ease": (0.25, 0.1, 0.25, 1.0), "ease-in": (0.42, 0, 1, 1),
       "ease-out": (0, 0, 0.58, 1), "ease-in-out": (0.42, 0, 0.58, 1)}


def _read_blocks(path):
    """xfade-easing expr files: NAME line, expression lines, blank line."""
    out, name, buf = {}, None, []
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            continue
        if not line.strip():
            if name:
                out[name] = "\n".join(buf).strip()
            name, buf = None, []
            continue
        if name is None and re.fullmatch(r"[A-Z0-9_\-]+", line.strip()):
            name = line.strip().lower()
        else:
            buf.append(line)
    if name:
        out[name] = "\n".join(buf).strip()
    return out


_EASE = _TRANS = None


def library():
    global _EASE, _TRANS
    if _EASE is None:
        _EASE = _read_blocks(XE / "xfade-easings-script.txt")
        _TRANS = {k: v for k, v in _read_blocks(XE / "eased-transitions-yuv420p-script.txt").items()
                  if v != "NATIVE"}
    return _EASE, _TRANS


def bezier_expr(x1, y1, x2, y2, clip=True):
    """CSS cubic-bezier() as an ffmpeg expression. xfade's P runs 1 -> 0, so forward t = 1-P; solve
    x(s) = t by bisection (24 steps, ~6e-8), output 1 - y(s) into ld(0) like xfade-easing does."""
    bx = lambda s: f"(3*(1-{s})^2*{s}*{x1}+3*(1-{s})*{s}^2*{x2}+{s}^3)"
    by = lambda s: f"(3*(1-{s})^2*{s}*{y1}+3*(1-{s})*{s}^2*{y2}+{s}^3)"
    e = (f"st(1,1-P);st(2,0);st(3,1);st(4,0);"
         f"while(lt(ld(4),24),st(5,(ld(2)+ld(3))/2);if(lt({bx('ld(5)')},ld(1)),st(2,ld(5)),st(3,ld(5)));st(4,ld(4)+1));"
         f"st(5,(ld(2)+ld(3))/2);st(0,1-{by('ld(5)')})")
    if clip:
        e += ";st(0,clip(ld(0),0,1))"
    return e


def easing_expr(name, allow_overshoot=False):
    """Expression leaving eased (reversed) progress in ld(0)."""
    ease, _ = library()
    n = (name or "linear").strip().lower()
    m = re.fullmatch(r"cubic-bezier\(([^)]*)\)", n.replace(" ", ""))
    if m:
        x1, y1, x2, y2 = (float(v) for v in m.group(1).split(","))
        if not (0 <= x1 <= 1 and 0 <= x2 <= 1):
            sys.exit("cubic-bezier x1/x2 must be in [0,1]")
        return bezier_expr(x1, y1, x2, y2, clip=not allow_overshoot)
    if n in CSS and n != "linear":
        return bezier_expr(*CSS[n])
    if n in ("back", "elastic", "bounce") or n in ("quadratic", "cubic", "quartic", "quintic", "sinusoidal",
                                                    "exponential", "circular", "squareroot", "cuberoot",
                                                    "flipback", "flipelastic"):
        n += "-in-out"
    if n not in ease:
        sys.exit(f"unknown easing '{name}'. CSS: {', '.join(CSS)}, cubic-bezier(x1,y1,x2,y2); "
                 f"standard: {', '.join(sorted(ease))}")
    e = re.sub(r"\s+", " ", ease[n])
    if allow_overshoot and n.startswith(("back", "elastic")):
        e = e.replace(";\nst(0, clip(ld(0), 0, 1))", "").replace("; st(0, clip(ld(0), 0, 1))", "")
    return e


# ---------------------------------------------------------------- own transitions
def _pix(side, xr, yr):
    """Sample plane PLANE of input a/b at (ld(xr), ld(yr)) pixel coordinates (yuv420p: 3 planes)."""
    return (f"ifnot(PLANE,{side}0(ld({xr}),ld({yr})),ifnot(1-PLANE,{side}1(ld({xr}),ld({yr})),"
            f"{side}2(ld({xr}),ld({yr}))))")


def own_zoomblur(cx=0.5, cy=0.42, zoom=0.45, blur=0.18, taps=6):
    """Zoom-in blur (own code). Outgoing shot pushes into (cx,cy) with a radial blur growing with the
    push; incoming shot starts pushed-in and blurred and settles. Registers 0..8 (9 = easing cache)."""
    n1 = taps - 1
    side = lambda s, zexpr: (
        f"st(4,0);while(lt(ld(4),{taps}),"
        f"st(7,{zexpr}*(1+{blur}*ld(8)*ld(4)/{n1}));"
        f"st(5,({cx}+(X/W-{cx})/ld(7))*W);st(6,({cy}+(Y/H-{cy})/ld(7))*H);"
        f"st(3,ld(3)+{_pix(s, 5, 6)});st(4,ld(4)+1));")
    return (
        "st(1,1-ld(0));"                                   # forward eased progress f
        "st(2,clip((ld(1)-0.3)/0.4,0,1));st(2,ld(2)*ld(2)*(3-2*ld(2)));"   # blend m
        "st(0,0);"                                         # accumulated result
        # outgoing (a): zoom 1 -> 1+zoom, blur grows with f
        f"if(lt(ld(2),1),st(3,0);st(8,ld(1));{side('a', f'(1+{zoom}*ld(1))')}st(0,ld(3)/{taps}*(1-ld(2))));"
        # incoming (b): zoom 1+zoom -> 1, blur fades
        f"if(gt(ld(2),0),st(3,0);st(8,1-ld(1));{side('b', f'(1+{zoom}*(1-ld(1)))')}st(0,ld(0)+ld(3)/{taps}*ld(2)));"
        "ld(0)"
    )


def own_whip(direction=0, blur=0.35, taps=7):
    """Whip-pan push (own code): both shots slide as one strip, a box motion blur along the move
    scaled by a bell of linear progress. Overshoot-safe: coordinates past the far edge mirror back.
    direction 0: content moves left (next shot from the right), 1: right, 2: up, 3: down."""
    horiz = direction in (0, 1)
    sgn = 1 if direction in (0, 2) else -1
    n1 = taps - 1
    pos = "X/W" if horiz else "Y/H"
    if horiz:
        a_s = f"st(5,ld(6)*W);st(6,Y);"
    else:
        a_s = f"st(5,X);st(6,ld(6)*H);"
    return (
        "st(1,1-ld(0));"                                   # forward eased offset (can exceed 1)
        f"st(2,{blur}*sin(PI*clip(1-P,0,1)));"             # blur length (fraction of frame), bell on time
        "st(3,0);st(4,0);"
        f"while(lt(ld(4),{taps}),"
        f"st(7,{pos}+{sgn}*ld(1)+ld(2)*(ld(4)/{n1}-0.5));"  # strip coordinate of this tap
        + ("" if sgn == 1 else "st(7,ld(7)+1);")           # moving right/down: strip = [b | a]
        + "st(8,gte(ld(7),1));"                             # 1 = sample b
        "st(6,ld(7)-ld(8));"                                # local coordinate
        "st(6,if(gt(ld(6),1),2-ld(6),if(lt(ld(6),0),-ld(6),ld(6))));"   # mirror overshoot
        "st(6,clip(ld(6),0,1));"
        + (f"st(8,1-ld(8));" if sgn == -1 else "")
        + a_s
        + f"st(3,ld(3)+if(ld(8),{_pix('b', 5, 6)},{_pix('a', 5, 6)}));"
        "st(4,ld(4)+1));"
        f"ld(3)/{taps}"
    )


def own_softwipe(direction=0, feather=0.22, push=0.05):
    """Feathered directional wipe with a small parallax push (own code). direction 0: the edge travels
    right to left, 1: left to right, 2: bottom to top, 3: top to bottom. feather = edge width (frame
    fraction), push = how far both shots drift with the edge."""
    c = {0: "(1-X/W)", 1: "(X/W)", 2: "(1-Y/H)", 3: "(Y/H)"}[int(direction)]
    sgn = {0: 1, 1: -1, 2: 1, 3: -1}[int(direction)]
    horiz = int(direction) in (0, 1)
    ax, size = ("X", "W") if horiz else ("Y", "H")
    def at(side, off):
        if horiz:
            return f"st(5,clip(X+{off}*W,0,W-1));st(6,Y);{_pix(side, 5, 6)}"
        return f"st(5,X);st(6,clip(Y+{off}*H,0,H-1));{_pix(side, 5, 6)}"
    return (
        "st(1,1-ld(0));"
        f"st(2,clip((ld(1)*(1+{feather})-{c})/{feather},0,1));st(2,ld(2)*ld(2)*(3-2*ld(2)));"
        f"st(3,if(lt(ld(2),1),{at('a', f'({sgn}*{push}*ld(1))')},0));"
        f"st(4,if(gt(ld(2),0),{at('b', f'(-{sgn}*{push}*(1-ld(1)))')},0));"
        "ld(3)*(1-ld(2))+ld(4)*ld(2)"
    )


OWN = {"zoomblur": (own_zoomblur, True), "whip": (own_whip, True),
       "softwipe": (own_softwipe, True)}  # name -> (expression builder, overshoot ok)


def parse_call(spec):
    m = re.fullmatch(r"([A-Za-z0-9_\-]+)(?:\((.*)\))?", spec.strip())
    if not m:
        sys.exit(f"bad transition '{spec}'")
    args = [a.strip() for a in m.group(2).split(",")] if m.group(2) else []
    return m.group(1), args


def transition_expr(spec, allow_overshoot):
    """Return (expr_using_ld0, overshoot_ok)."""
    name, args = parse_call(spec)
    if name in OWN:
        fn, ok = OWN[name]
        import inspect
        params = list(inspect.signature(fn).parameters)
        kw = {params[i]: float(a) for i, a in enumerate(args) if a != ""}
        if "direction" in kw:
            kw["direction"] = int(kw["direction"])
        return fn(**kw), ok
    _, trans = library()
    key = name.lower()
    if key not in trans:
        sys.exit(f"unknown transition '{name}' (or native-build only). See: transitions.py list --all")
    e = trans[key]
    if args:  # GL params are the leading st(k, default) lines, in order (xfade-easing convention)
        lines = e.split("\n")
        for i, a in enumerate(args):
            if a == "":
                continue
            if i >= len(lines) or not re.fullmatch(rf"st\({i + 1}, [^;]+\);", lines[i].strip()):
                sys.exit(f"{name}: no parameter #{i + 1}")
            lines[i] = f"st({i + 1}, {float(a)});"
        e = "\n".join(lines)
    return e, False


def full_expr(spec, easing, allow_overshoot=True):
    t, ok = transition_expr(spec, allow_overshoot)
    ez = easing_expr(easing, allow_overshoot=allow_overshoot and ok)
    t1 = re.sub(r"\s*\n\s*", " ", t)
    if re.search(r"(st|ld)\(\s*9\s*[,)]", t1):  # transition uses register 9: no cache
        return f"{ez};\n{t1}"
    # easing depends on P only: compute it once per frame (first pixel of plane 0), cache in ld(9)
    return f"if(not(X+Y+PLANE),{ez};st(9,ld(0)));st(0,ld(9));\n{t1}"


def resolve(name, easing=None, dur=None):
    """Curated name or raw xfade-easing name -> (transition spec, easing, duration)."""
    if name in ALIASES:
        return "cut", None, 0.0
    base, args = parse_call(name)
    if base in RENAMES:
        return RENAMES[base] + (f"({','.join(args)})" if args else ""), easing or "cubic-in-out", dur if dur is not None else 0.5
    if base in CURATED:
        c = CURATED[base]
        t = c["t"] + (f"({','.join(args)})" if args else "")
        return t, easing or c["e"], dur if dur is not None else c["d"]
    return name, easing or "cubic-in-out", dur if dur is not None else 0.5


# ---------------------------------------------------------------- easing in Python (same numbers as the exprs)
class _Expr:
    """Minimal ffmpeg-expression evaluator, enough for the xfade-easing easing expressions
    (numbers, P, PI, + - * / ^, ;, st/ld/if/ifnot/lt/lte/gt/gte/eq/between/clip/sqrt/sin/cos/pow/
    abs/not/while). Lazy if(), like ffmpeg, because the expressions store values inside branches."""

    def __init__(self, text):
        self.toks = re.findall(r"\d+\.\d*|\.\d+|\d+|[A-Za-z_]\w*|[-+*/^(),;]", text)
        self.i = 0
        self.tree = self.seq()

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, t=None):
        tok = self.peek()
        if t is not None and tok != t:
            raise ValueError(f"expected {t}, got {tok}")
        self.i += 1
        return tok

    def seq(self):
        n = [self.add()]
        while self.peek() == ";":
            self.take()
            n.append(self.add())
        return ("seq", n) if len(n) > 1 else n[0]

    def add(self):
        n = self.mul()
        while self.peek() in ("+", "-"):
            op = self.take()
            n = (op, n, self.mul())
        return n

    def mul(self):
        n = self.unary()
        while self.peek() in ("*", "/"):
            op = self.take()
            n = (op, n, self.unary())
        return n

    def unary(self):
        if self.peek() in ("-", "+"):
            op = self.take()
            n = self.unary()
            return ("neg", n) if op == "-" else n
        return self.pow()

    def pow(self):
        n = self.atom()
        if self.peek() == "^":
            self.take()
            n = ("^", n, self.unary())
        return n

    def atom(self):
        t = self.take()
        if t == "(":
            n = self.seq()
            self.take(")")
            return n
        if re.fullmatch(r"\d+\.?\d*|\.\d+", t):
            return ("num", float(t))
        if self.peek() == "(":
            self.take("(")
            args = [self.seq()]
            while self.peek() == ",":
                self.take()
                args.append(self.seq())
            self.take(")")
            return ("fn", t, args)
        return ("var", t)

    def eval(self, P):
        reg = [0.0] * 10
        V = {"P": P, "PI": math.pi, "E": math.e}

        def ev(n):
            k = n[0]
            if k == "num":
                return n[1]
            if k == "var":
                return V[n[1]]
            if k == "seq":
                r = 0.0
                for c in n[1]:
                    r = ev(c)
                return r
            if k == "neg":
                return -ev(n[1])
            if k in "+-*/^":
                a, b = ev(n[1]), ev(n[2])
                return {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else math.inf,
                        "^": (a ** b) if a >= 0 or float(b).is_integer() else math.nan}[k]
            f, args = n[1], n[2]
            if f == "if":
                return ev(args[1]) if ev(args[0]) else (ev(args[2]) if len(args) > 2 else 0.0)
            if f == "ifnot":
                c = ev(args[0])
                return ev(args[1]) if not c else (ev(args[2]) if len(args) > 2 else 0.0)
            if f == "while":
                r = math.nan
                while ev(args[0]):
                    r = ev(args[1])
                return r
            v = [ev(a) for a in args]
            if f == "st":
                reg[int(v[0])] = v[1]
                return v[1]
            if f == "ld":
                return reg[int(v[0])]
            return {"lt": lambda a, b: float(a < b), "lte": lambda a, b: float(a <= b),
                    "gt": lambda a, b: float(a > b), "gte": lambda a, b: float(a >= b),
                    "eq": lambda a, b: float(a == b), "between": lambda x, a, b: float(a <= x <= b),
                    "clip": lambda x, a, b: min(max(x, a), b), "sqrt": math.sqrt, "sin": math.sin,
                    "cos": math.cos, "pow": math.pow, "abs": abs, "not": lambda a: float(not a),
                    "min": min, "max": max}[f](*v)

        return ev(self.tree)


def easing_fn(name, allow_overshoot=False):
    """Forward easing e(t), t in [0,1] -> progress (0 at the start, 1 at the end)."""
    ez = _Expr(easing_expr(name, allow_overshoot))
    return lambda t: 1.0 - ez.eval(1.0 - t)


# ---------------------------------------------------------------- media helpers
def probe(path):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,width,height,r_frame_rate:format=duration",
                                   "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    n, d = v["r_frame_rate"].split("/")
    return dict(w=v["width"], h=v["height"], fps=float(n) / float(d), dur=float(j["format"]["duration"]),
                audio=any(s["codec_type"] == "audio" for s in j["streams"]))


def parse_seg(s):
    """path@a-b (seconds) -> dict; path@t -> point (for junction)."""
    m = re.fullmatch(r"(.+)@([0-9.]+)(?:-([0-9.]+))?", s)
    if not m:
        sys.exit(f"bad segment '{s}', use path@a-b")
    return dict(src=m.group(1), a=float(m.group(2)), b=float(m.group(3)) if m.group(3) else None)


def fr(t, fps):
    return round(t * fps) / fps


def vprep(fps, W, H):
    return (f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
            f"setsar=1,format=yuv420p")


def ff(cmd, **kw):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *cmd], **kw)
    if r.returncode:
        sys.exit(f"ffmpeg failed: {' '.join(map(str, cmd))[:600]}")
    return r


# ---------------------------------------------------------------- window renderers
NATIVE = set("fade wipeleft wiperight wipeup wipedown slideleft slideright slideup slidedown circlecrop rectcrop "
             "distance fadeblack fadewhite radial smoothleft smoothright smoothup smoothdown circleopen "
             "circleclose vertopen vertclose horzopen horzclose dissolve pixelize diagtl diagtr diagbl diagbr "
             "hlslice hrslice vuslice vdslice hblur fadegrays wipetl wipetr wipebl wipebr squeezeh squeezev "
             "zoomin fadefast fadeslow hlwind hrwind vuwind vdwind coverleft coverright coverup coverdown "
             "revealleft revealright revealup revealdown".split())


def pick_engine(spec, ease, force=None):
    name, args = parse_call(spec)
    if force:
        return force
    if name in OWN:
        return "numpy"
    if name in NATIVE and not args:
        f = easing_fn(ease)
        v = [f(i / 200) for i in range(201)]
        if all(0 <= x <= 1 for x in v) and all(b >= a for a, b in zip(v, v[1:])):
            return "native"
    return "expr"


def _win_inputs(A, a0, B, b0, nf, fps):
    t = nf / fps + 0.25
    return ["-ss", f"{a0:.6f}", "-t", f"{t:.6f}", "-i", str(A), "-ss", f"{b0:.6f}", "-t", f"{t:.6f}", "-i", str(B)]


def win_native(A, a0, B, b0, nf, fps, W, H, spec, ease, out):
    """Built-in xfade, eased by giving the outgoing frames warped timestamps: frame i gets pts
    D*e(i/nf), so xfade's linear progress becomes eased progress. Then timestamps are restored."""
    f = easing_fn(ease)
    D = nf / fps
    vals = [D * f(i / nf) + i * 1e-5 for i in range(nf)]  # strictly increasing
    look = "0"
    for i in reversed(range(nf)):
        look = f"if(eq(N,{i}),{vals[i]:.6f},{look})"
    g = (f"[0:v]{vprep(fps, W, H)},trim=end_frame={nf},settb=1/30000,setpts='({look})/TB'[a];"
         f"[1:v]{vprep(fps, W, H)},trim=end_frame={nf},settb=1/30000[b];"
         f"[a][b]xfade=transition={parse_call(spec)[0]}:duration={D:.6f}:offset=0,setpts='N/{fps}/TB'[v]")
    ff([*_win_inputs(A, a0, B, b0, nf, fps), "-filter_complex", g, "-map", "[v]", "-frames:v", str(nf),
        "-c:v", "ffv1", "-r", str(fps), str(out)])


def _remap_p(k0, m, nf):
    """Global progress for chunk-local P (xfade P runs 1 -> 0 over the chunk's m frames)."""
    return f"(1-({k0}+(1-P)*{m})/{nf})"


def win_expr(A, a0, B, b0, nf, fps, W, H, spec, ease, out, jobs=None):
    """xfade custom expression, split into frame chunks rendered by parallel ffmpeg processes."""
    ex = full_expr(spec, ease)
    jobs = jobs or EXPR_CHUNKS
    n_chunks = max(1, min(jobs, nf))
    bounds = [round(i * nf / n_chunks) for i in range(n_chunks + 1)]
    tmp = Path(tempfile.mkdtemp(prefix="tx-"))
    # decode each side once into an intra-only file, so the chunks seek instantly
    wa, wb = tmp / "a.mkv", tmp / "b.mkv"
    for src, t0, o in ((A, a0, wa), (B, b0, wb)):
        ff(["-ss", f"{t0:.6f}", "-t", f"{nf / fps + 0.25:.6f}", "-i", str(src), "-vf", vprep(fps, W, H),
            "-frames:v", str(nf), "-c:v", "ffv1", "-r", str(fps), str(o)])

    def chunk(k):
        k0, k1 = bounds[k], bounds[k + 1]
        m = k1 - k0
        e = re.sub(r"\bP\b", _remap_p(k0, m, nf), ex)
        fg = tmp / f"c{k}.fg"
        fg.write_text(f"[0:v]trim=start_frame={k0}:end_frame={k1},setpts=PTS-STARTPTS[a];"
                      f"[1:v]trim=start_frame={k0}:end_frame={k1},setpts=PTS-STARTPTS[b];"
                      f"[a][b]xfade=transition=custom:duration={m / fps:.6f}:offset=0:expr='{e}'[v]")
        o = tmp / f"c{k}.mkv"
        ff(["-filter_complex_threads", "1", "-i", str(wa), "-i", str(wb),
            "-/filter_complex", str(fg), "-map", "[v]", "-frames:v", str(m), "-c:v", "ffv1", "-r", str(fps), str(o)])
        return o

    with cf.ThreadPoolExecutor(n_chunks) as ex_:
        parts = list(ex_.map(chunk, range(n_chunks)))
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()


def _read_yuv(src, t0, nf, fps, W, H):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.6f}", "-t", f"{nf / fps + 0.25:.6f}", "-i", str(src),
                          "-vf", vprep(fps, W, H), "-frames:v", str(nf), "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
                         capture_output=True, check=True).stdout
    fs = W * H * 3 // 2
    if len(raw) < fs * nf:
        sys.exit(f"{src}: got {len(raw) // fs} of {nf} frames at {t0:.3f}s (not enough handle?)")
    out = []
    for i in range(nf):
        b = np.frombuffer(raw, np.uint8, fs, i * fs)
        y = b[:W * H].reshape(H, W)
        u = b[W * H:W * H + W * H // 4].reshape(H // 2, W // 2)
        v = b[W * H + W * H // 4:].reshape(H // 2, W // 2)
        out.append((y, u, v))
    return out


def win_numpy(A, a0, B, b0, nf, fps, W, H, spec, ease, out):
    """Own transitions on the Y, U, V planes with OpenCV remaps (geometry in normalised coords, so the
    chroma planes line up). Same look as the own_* expressions, ~100x faster."""
    import cv2
    import numpy as np
    name, args = parse_call(spec)
    fn, _ = OWN[name]
    import inspect
    params = list(inspect.signature(fn).parameters)
    kw = {params[i]: float(a) for i, a in enumerate(args) if a != ""}
    defaults = {k: v.default for k, v in inspect.signature(fn).parameters.items()}
    P_ = {**defaults, **kw}
    f = easing_fn(ease, allow_overshoot=True)
    fa, fb = _read_yuv(A, a0, nf, fps, W, H), _read_yuv(B, b0, nf, fps, W, H)
    grids = {}

    def grid(h, w):
        if (h, w) not in grids:
            xs = (np.arange(w, dtype=np.float32) + 0.5) / w
            ys = (np.arange(h, dtype=np.float32) + 0.5) / h
            grids[(h, w)] = np.meshgrid(xs, ys)
        return grids[(h, w)]

    def sample(plane, u, v):
        h, w = plane.shape
        return cv2.remap(plane, u * w - 0.5, v * h - 0.5, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

    def mirror(x):
        x = np.where(x > 1, 2 - x, x)
        return np.clip(np.where(x < 0, -x, x), 0, 1)

    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{W}x{H}",
                            "-r", str(fps), "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-i", "-", "-c:v", "ffv1", *TAGS, str(out)], stdin=subprocess.PIPE)
    taps = int(P_.get("taps", 6))
    for i in range(nf):
        t = i / nf
        e = f(t)
        planes = []
        for pi in range(3):
            pa, pb = fa[i][pi], fb[i][pi]
            X, Y = grid(*pa.shape)
            if name == "zoomblur":
                cx, cy, zoom, blur = P_["cx"], P_["cy"], P_["zoom"], P_["blur"]
                ec = min(max(e, 0.0), 1.0)
                m = min(max((ec - 0.3) / 0.4, 0.0), 1.0)
                m = m * m * (3 - 2 * m)
                acc = np.zeros(pa.shape, np.float32)
                for side, img, z, amt, wgt in (("a", pa, 1 + zoom * e, ec, 1 - m), ("b", pb, 1 + zoom * (1 - e), 1 - ec, m)):
                    if wgt <= 0:
                        continue
                    s_acc = np.zeros(pa.shape, np.float32)
                    for j in range(taps):
                        s = z * (1 + blur * amt * j / (taps - 1))
                        s_acc += sample(img, cx + (X - cx) / s, cy + (Y - cy) / s)
                    acc += s_acc / taps * wgt
            elif name == "softwipe":
                d = int(P_["direction"]); fe, push = P_["feather"], P_["push"]
                horiz = d in (0, 1)
                c = {0: 1 - X, 1: X, 2: 1 - Y, 3: Y}[d]
                sgn = 1 if d in (0, 2) else -1
                m = np.clip((e * (1 + fe) - c) / fe, 0, 1)
                m = m * m * (3 - 2 * m)
                if horiz:
                    sa = sample(pa, np.clip(X + sgn * push * e, 0, 1), Y)
                    sb = sample(pb, np.clip(X - sgn * push * (1 - e), 0, 1), Y)
                else:
                    sa = sample(pa, X, np.clip(Y + sgn * push * e, 0, 1))
                    sb = sample(pb, X, np.clip(Y - sgn * push * (1 - e), 0, 1))
                acc = sa * (1 - m) + sb * m
            else:  # whip: the two shots as one strip at offset e, then a box blur along the move
                d = int(P_["direction"])
                L = P_["blur"] * math.sin(math.pi * t)
                horiz = d in (0, 1)
                pos = X if horiz else Y
                u = pos + (e if d in (0, 2) else 1 - e)
                sel_b = (u >= 1) if d in (0, 2) else (u < 1)
                loc = mirror(u - (u >= 1))
                sa = sample(pa, loc, Y) if horiz else sample(pa, X, loc)
                sb = sample(pb, loc, Y) if horiz else sample(pb, X, loc)
                acc = np.where(sel_b, sb, sa)
                k = int(L * (pa.shape[1] if horiz else pa.shape[0])) | 1
                if k > 1:
                    acc = cv2.blur(acc, (k, 1) if horiz else (1, k))
            planes.append(np.clip(acc + 0.5, 0, 255).astype(np.uint8))
        enc.stdin.write(b"".join(p.tobytes() for p in planes))
    enc.stdin.close()
    if enc.wait():
        sys.exit("ffmpeg encode failed")


def render_window(A, a0, B, b0, nf, fps, W, H, spec, ease, out, engine=None, jobs=None):
    """Exactly nf frames: A from a0, B from b0, the transition across all of them. Lossless FFV1 .mkv."""
    eng = pick_engine(spec, ease, engine)
    t = time.time()
    c0 = os.times()
    if eng == "native":
        win_native(A, a0, B, b0, nf, fps, W, H, spec, ease, out)
    elif eng == "numpy":
        win_numpy(A, a0, B, b0, nf, fps, W, H, spec, ease, out)
    else:
        win_expr(A, a0, B, b0, nf, fps, W, H, spec, ease, out, jobs)
    c1 = os.times()
    cpu = (c1.children_user - c0.children_user) + (c1.children_system - c0.children_system) + \
          (c1.user - c0.user) + (c1.system - c0.system)
    return eng, time.time() - t, cpu


# ---------------------------------------------------------------- join
def plan(segs, trans, fps):
    """Frame-exact plan: each junction gets L (frames before the cut) + R (after) = d, within handles."""
    for s in segs:
        s["a"], s["b"] = fr(s["a"], fps), fr(s["b"], fps)
        s["srcdur"] = probe(s["src"])["dur"]
        s["n"] = int(round((s["b"] - s["a"]) * fps))
        if s["n"] < 1:
            sys.exit(f"segment {s} has b <= a")
    out, t = [], 0
    for i, s in enumerate(segs):
        t += s["n"]
        if i == len(segs) - 1:
            break
        spec, ease, d = trans[i]
        nf = int(round(d * fps))
        if spec == "cut" or nf < 2:
            out.append(dict(spec="cut", ease=None, Lf=0, Rf=0, J=t))
            continue
        Lf, Rf = nf // 2, nf - nf // 2
        maxR = int(math.floor((s["srcdur"] - s["b"]) * fps + 1e-6)) - 2   # outgoing tail handle
        maxL = int(math.floor(segs[i + 1]["a"] * fps + 1e-6))             # incoming head handle
        if Rf > maxR:
            Lf += Rf - max(maxR, 0); Rf = max(maxR, 0)
        Lf = min(Lf, maxL)
        Lf, Rf = min(Lf, s["n"] - 1), min(Rf, segs[i + 1]["n"] - 1)
        if Lf + Rf < nf:
            print(f"  junction {i}: only {Lf + Rf} of {nf} frames of handle", file=sys.stderr)
        out.append(dict(spec=spec, ease=ease, Lf=Lf, Rf=Rf, J=t))
    for i in range(1, len(segs) - 1):  # transitions on both ends of a short segment must not overlap
        if out[i - 1]["Rf"] + out[i]["Lf"] > segs[i]["n"]:
            out[i]["Lf"] = max(0, segs[i]["n"] - out[i - 1]["Rf"])
            print(f"  junction {i}: shortened (segment {i} is short)", file=sys.stderr)
    for j in out:
        if j["spec"] != "cut" and j["Lf"] + j["Rf"] < 2:
            j.update(spec="cut", Lf=0, Rf=0)
    return out


def assemble(segs, juncs, fps, W, H, out, audio_mode="cut", audio_from=None, crf=18, engine=None, jobs=None,
             keep=None):
    tmp = Path(tempfile.mkdtemp(prefix="txjoin-"))
    log = []
    wins = {}
    for i, j in enumerate(juncs):
        if j["spec"] == "cut":
            continue
        nf = j["Lf"] + j["Rf"]
        A, B = segs[i], segs[i + 1]
        w = tmp / f"w{i}.mkv"
        eng, secs, cpu = render_window(A["src"], A["b"] - j["Lf"] / fps, B["src"], B["a"] - j["Lf"] / fps, nf, fps,
                                       W, H, j["spec"], j["ease"], w, engine, jobs)
        wins[i] = w
        log.append(dict(junction=i, at=round(j["J"] / fps, 3), spec=j["spec"], ease=j["ease"], frames=nf,
                        engine=eng, seconds=round(secs, 1), cpu=round(cpu, 1)))
    # body pieces between windows, then concat everything
    inputs, fc, labels = [], [], []
    nin = 0
    for i, s in enumerate(segs):
        rin = juncs[i - 1]["Rf"] if i > 0 else 0
        lout = juncs[i]["Lf"] if i < len(segs) - 1 else 0
        n = s["n"] - rin - lout
        if n > 0:
            t0 = s["a"] + rin / fps
            inputs += ["-ss", f"{t0:.6f}", "-t", f"{n / fps + 0.25:.6f}", "-i", str(s["src"])]
            fc.append(f"[{nin}:v]{vprep(fps, W, H)},trim=end_frame={n},setpts=PTS-STARTPTS[p{len(labels)}]")
            labels.append(f"p{len(labels)}")
            nin += 1
        if i in wins:
            inputs += ["-i", str(wins[i])]
            fc.append(f"[{nin}:v]setpts=PTS-STARTPTS,format=yuv420p[p{len(labels)}]")
            labels.append(f"p{len(labels)}")
            nin += 1
    fc.append("".join(f"[{l}]" for l in labels) + f"concat=n={len(labels)}:v=1:a=0[vout]")
    # audio
    xa = float(audio_mode.split(":")[1]) if audio_mode.startswith("xfade") and ":" in audio_mode else (
        0.08 if audio_mode.startswith("xfade") else 0.0)
    has_audio = audio_mode != "none" and (bool(audio_from) or all(probe(s["src"])["audio"] for s in segs))
    if has_audio:
        al = []
        for i, s in enumerate(segs):
            ha = xa / 2 if (xa and i > 0) else 0.0
            hb = xa / 2 if (xa and i < len(segs) - 1) else 0.0
            aa, ab = max(0.0, s["a"] - ha), s["b"] + hb
            inputs += ["-vn", "-ss", f"{aa:.6f}", "-t", f"{ab - aa + 0.2:.6f}", "-i", str(audio_from or s["src"])]
            dec = "" if xa else f",afade=t=in:d=0.01,afade=t=out:st={ab - aa - 0.01:.6f}:d=0.01"
            fc.append(f"[{nin}:a]atrim=duration={ab - aa:.6f},asetpts=PTS-STARTPTS,"
                      f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo{dec}[a{i}]")
            al.append(f"a{i}")
            nin += 1
        if xa:
            cur = al[0]
            for i in range(1, len(al)):
                fc.append(f"[{cur}][{al[i]}]acrossfade=d={xa}:c1=qsin:c2=qsin[ax{i}]")
                cur = f"ax{i}"
            fc.append(f"[{cur}]anull[aout]")
        else:
            fc.append("".join(f"[{l}]" for l in al) + f"concat=n={len(al)}:v=0:a=1[aout]")
    fgp = tmp / "join.fg"
    fgp.write_text(";\n".join(fc))
    total = sum(s["n"] for s in segs)
    cmd = [*inputs, "-/filter_complex", str(fgp), "-map", "[vout]"]
    cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"] if has_audio else ["-an"]
    cmd += ["-frames:v", str(total), "-c:v", "libx264", "-threads", X264_THREADS, "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
            *TAGS, "-r", str(fps), "-g", str(max(1, round(fps))), "-movflags", "+faststart", str(out)]
    t = time.time()
    ff(cmd)
    log.append(dict(assemble_seconds=round(time.time() - t, 1)))
    if keep:
        Path(keep).mkdir(parents=True, exist_ok=True)
        for i, w in wins.items():
            w.replace(Path(keep) / w.name)
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()
    return log, has_audio


def cmd_join(a):
    if a.edl:
        e = json.loads(Path(a.edl).read_text())
        segs = [dict(src=s["src"], a=s["a"], b=s["b"]) for s in e["segments"]]
        trans = [resolve(t.get("type", "cut"), t.get("ease"), t.get("dur")) if isinstance(t, dict) else resolve(t)
                 for t in e.get("transitions", [])]
        size, audio = e.get("size", a.size), e.get("audio", a.audio)
    else:
        segs = [parse_seg(s) for s in a.segments]
        names = a.t or ["dissolve"]
        trans = [resolve(names[min(i, len(names) - 1)], a.e, a.d) for i in range(len(segs) - 1)]
        size, audio = a.size, a.audio
    if len(segs) < 2:
        sys.exit("need at least two segments")
    while len(trans) < len(segs) - 1:
        trans.append(trans[-1] if trans else resolve("cut"))
    p0 = probe(segs[0]["src"])
    fps = a.fps or p0["fps"]
    W, H = (int(v) for v in size.split("x")) if size else (p0["w"], p0["h"])
    t = time.time()
    juncs = plan(segs, trans, fps)
    log, has_audio = assemble(segs, juncs, fps, W, H, a.o, audio, a.audio_from, a.crf, a.engine, a.jobs)
    total = sum(s["n"] for s in segs) / fps
    print(f"{a.o}: {len(segs)} segments, {total:.3f}s, {W}x{H}@{fps:g}, audio={audio if has_audio else 'none'}, "
          f"{time.time() - t:.1f}s")
    for j, l in zip([j for j in juncs if j["spec"] != "cut"], [l for l in log if "junction" in l]):
        print(f"  cut at {l['at']:.3f}s: {l['spec']} {l['ease']} {l['frames']} frames "
              f"(L={j['Lf']} R={j['Rf']}) engine={l['engine']} {l['seconds']}s wall / {l['cpu']}s cpu")


# ---------------------------------------------------------------- junction (overlay clip for HyperFrames)
def render_junction(A, tout, B, tin, name, easing=None, dur=None, out="tx.mp4", size=None, fps=None, crf=14,
                    engine=None, jobs=None):
    spec, ease, d = resolve(name, easing, dur)
    pa = probe(A)
    fps = fps or pa["fps"]
    W, H = size or (pa["w"], pa["h"])
    # HyperFrames (a browser <video>) shows at media time x the frame whose interval contains x, i.e. frame
    # floor(x*fps). Snap the same way so the window's first and last frames continue the takes exactly
    # (verified on test-reel: nearest-rounding gave a skipped frame before and a repeated frame after).
    tout = math.floor(tout * fps + 1e-4) / fps
    tin = math.floor(tin * fps + 1e-4) / fps
    nf = int(round(d * fps))
    Lf, Rf = nf // 2, nf - nf // 2
    Rf = min(Rf, int((pa["dur"] - tout) * fps) - 2)
    Lf = min(Lf, int(tin * fps + 1e-6))
    tmp = Path(tempfile.mkdtemp(prefix="txj-")) / "w.mkv"
    eng, secs, cpu = render_window(A, tout - Lf / fps, B, tin - Lf / fps, Lf + Rf, fps, W, H, spec, ease, tmp,
                                   engine, jobs)
    ff(["-i", str(tmp), "-c:v", "libx264", "-threads", X264_THREADS, "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", *TAGS,
        "-g", str(max(1, round(fps))), "-movflags", "+faststart", "-an", str(out)])
    tmp.unlink()
    tmp.parent.rmdir()
    return dict(out=str(out), L=Lf / fps, R=Rf / fps, d=(Lf + Rf) / fps, secs=round(secs, 1), cpu=round(cpu, 1),
                spec=spec, ease=ease, engine=eng)


def cmd_junction(a):
    A, B = parse_seg(a.a), parse_seg(a.b)
    size = tuple(int(v) for v in a.size.split("x")) if a.size else None
    r = render_junction(A["src"], A["a"], B["src"], B["a"], a.t[0] if a.t else "dissolve", a.e, a.d, a.o, size,
                        a.fps, engine=a.engine, jobs=a.jobs)
    print(f"{r['out']}: {r['spec']} {r['ease']} d={r['d']:.3f}s engine={r['engine']} ({r['secs']}s wall, {r['cpu']}s cpu); place it at "
          f"cut-{r['L']:.3f}s: it covers the last {r['L']:.3f}s of A and the first {r['R']:.3f}s of B")


# ---------------------------------------------------------------- reel.json integration
def cmd_reel(a):
    """reel.json "transitions": [{"after": <take index>, "type": "dissolve", "dur": 0.3, "ease": "..."}]
    or {"default": "dissolve", "dur": 0.2, "skip": [3]} for every take change. Writes assets/tx/tx-<i>.mp4
    and build/transitions.json (edit-time placement) for build.mjs to add as <video> overlays."""
    P = Path(a.project).resolve()
    spec = json.loads((P / "reel.json").read_text())
    fps = spec.get("fps", 30)
    takes = spec["takes"]
    look = spec.get("look") or {}
    rel = spec["source"]
    if look.get("film"):  # a graded plate (film_look.py) is what the reel shows, so cut the windows from it
        rel = look.get("plate", "assets/talk.film.mp4")
        if not (P / rel).exists():
            sys.exit(f"look.film is set but {rel} is missing: run film_look.py apply first")
    if look.get("cutout"):  # a cutout_fx.py plate (selective / spotlight / bg-blur) is made from the film plate when both are set
        lc = look["cutout"] if isinstance(look["cutout"], dict) else {"fx": look["cutout"]}
        rel = lc.get("plate") or f"assets/talk.{lc.get('fx')}.mp4"
        if not (P / rel).exists():
            sys.exit(f"look.cutout is set but {rel} is missing: run node build.mjs once, it prints the cutout_fx.py command")
    src = str(P / rel)
    T = spec.get("transitions")
    if not T:
        sys.exit('reel.json has no "transitions"')
    if isinstance(T, dict):
        skip = set(T.get("skip", []))
        T = [dict(after=i, type=T.get("default", "dissolve"), dur=T.get("dur"), ease=T.get("ease"))
             for i in range(len(takes) - 1) if i not in skip]
    acc, starts = 0, []  # the same frame math as build.mjs
    for t in takes:
        starts.append(acc / fps)
        acc += round((t["b"] - t["a"]) * fps) + round(t.get("hold", 0) * fps)
    (P / "assets" / "tx").mkdir(parents=True, exist_ok=True)
    out = []
    for tr in T:
        i = tr["after"]
        if i >= len(takes) - 1:
            continue
        if takes[i].get("hold"):
            print(f"  skip after take {i}: it ends on a hold (frozen frame)")
            continue
        k, n = takes[i], takes[i + 1]
        tout = k["a"] + round((k["b"] - k["a"]) * fps) / fps
        f = P / "assets" / "tx" / f"tx-{i}.mp4"
        r = render_junction(src, tout, src, n["a"], tr.get("type", "dissolve"), tr.get("ease"), tr.get("dur"), f,
                            fps=fps, engine=a.engine, jobs=a.jobs)
        J = starts[i + 1]
        out.append(dict(id=f"tx-{i}", src=f"assets/tx/tx-{i}.mp4", start=round(J - r["L"], 3),
                        duration=round(r["d"], 3), frames=int(round(r["d"] * fps)), after=i,
                        type=tr.get("type", "dissolve"), engine=r["engine"], cpu=r["cpu"],
                        # what the clip was cut from: build.mjs re-checks these so a re-cut can't reuse stale clips
                        source=rel, out_point=k["b"], in_point=n["a"]))
        print(f"  tx-{i}: {r['spec']} at {J - r['L']:.3f}s for {r['d']:.3f}s, {r['engine']} {r['secs']}s")
    (P / "build").mkdir(exist_ok=True)
    (P / "build" / "transitions.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {P / 'build' / 'transitions.json'} ({len(out)} transitions)")


def cmd_list(a):
    print("curated for talking heads (name: kind, base, easing, duration, engine):")
    for k, c in CURATED.items():
        print(f"  {k:12s} {c['kind']:6s} {c['t']:22s} {c['e']:31s} {c['d']:.2f}s {pick_engine(c['t'], c['e']):6s} {c['what']}")
    print("\neasings: CSS " + ", ".join(CSS) + ", cubic-bezier(x1,y1,x2,y2) (y may overshoot for zoomblur/whip); "
          "standard: quadratic cubic quartic quintic sinusoidal exponential circular elastic back bounce squareroot "
          "cuberoot flipelastic flipback, each -in / -out / -in-out")
    if a.all:
        _, trans = library()
        print("\nall expression transitions (xfade-easing; native-build-only ones excluded):\n  "
              + " ".join(sorted(trans)) + "\n  own: zoomblur(cx,cy,zoom,blur,taps) whip(direction,blur,taps) softwipe(direction,feather,push)")


def cmd_expr(a):
    spec, ease, _ = resolve(a.t[0] if a.t else "dissolve", a.e, None)
    print(full_expr(spec, ease))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--all", action="store_true")
    for name in ("join", "junction", "expr", "reel"):
        s = sub.add_parser(name)
        if name == "reel":
            s.add_argument("project")
        if name == "join":
            s.add_argument("segments", nargs="*", help="path@a-b ...")
            s.add_argument("--edl")
            s.add_argument("--audio", default="cut", help="cut | xfade[:seconds] | none")
            s.add_argument("--audio-from", help="take audio from this file at the same times (e.g. voice.wav)")
        if name == "junction":
            s.add_argument("a", help="outgoing: path@out_point")
            s.add_argument("b", help="incoming: path@in_point")
        if name != "reel":
            s.add_argument("-t", action="append", help="transition: curated name, xfade-easing name or own; repeatable")
            s.add_argument("-e", help="easing (overrides the curated default)")
            s.add_argument("-d", type=float, help="duration in seconds")
            s.add_argument("-o", default="out.mp4")
            s.add_argument("--size", help="WxH, e.g. 540x960")
            s.add_argument("--fps", type=float)
            s.add_argument("--crf", type=int, default=18)
        s.add_argument("--engine", choices=["native", "numpy", "expr"], help="force a render engine")
        s.add_argument("--jobs", type=int, help=f"parallel ffmpeg processes for the expr engine (default {EXPR_CHUNKS}; another "
                       "count changes the pixels slightly, so leave it unset for the same file on every Mac)")
    a = ap.parse_args()
    {"list": cmd_list, "join": cmd_join, "junction": cmd_junction, "reel": cmd_reel, "expr": cmd_expr}[a.cmd](a)


if __name__ == "__main__":
    main()
