// Data Story engine: "a pencil-annotated chart on cream paper", for a 1080x1920 talking-head reel.
// Adapted from lemo-opuscar styles/dataviz/demo/engine.js + core/lib.js (MIT, (c) 2026 LemoLab; LICENSE-lemo-opuscar.txt):
// paper, pencil strokes, handwriting, data dots, ink shapes, dashed cells, the red-blue pencil and the figure caption are
// the source's functions, re-sized for 9:16 and Cyrillic fonts (Caveat, Playfair Display for Newsreader, JetBrains Mono
// for IBM Plex Mono). New here: DS.paint(g, SPEC, t), a stateless painter of the reel's layers (chart pages on paper,
// handwritten notes over the speaker's face) driven by one paused GSAP timeline, so every frame is a pure function of t (seek-safe).
// Plain script (no modules): window.DS.
(function () {
  'use strict';
  // ---------- lib (core/lib.js) ----------
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const ss = t => { t = clamp(t); return t * t * (3 - 2 * t); };
  const eio = t => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
  const eo = t => 1 - Math.pow(1 - clamp(t), 3);
  function mulberry(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const hash = n => { n = Math.sin(n * 127.1 + 311.7) * 43758.5453; return n - Math.floor(n); };
  const vnoise = x => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash(i), hash(i + 1), u); };

  const W = 1080, H = 1920;
  const F = { hand: 'Caveat', serif: '"Playfair Display"', mono: '"JetBrains Mono"' };
  // ---------- palette (source DEMO.md "Palette & props") ----------
  const P = {
    paper: '#F6F3EC', dotgrid: '#E4DDCF', ink: '#2B2723', inkSoft: '#6E665C', rule: '#DDD6C9', zero: '#BDB4A5',
    blue: '#2F5D8A', red: '#A8283A', graphite: '#3A3733', wood: '#E3C79C',
  };
  const hex2 = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const rgb = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;

  // ---------- camera: world -> screen, cam = {x, y, zoom} (x, y = the world point at the frame centre) ----------
  function applyCam(g, c) { g.setTransform(1, 0, 0, 1, 0, 0); g.translate(W / 2, H / 2); g.scale(c.zoom, c.zoom); g.translate(-c.x, -c.y); }
  function w2s(c, x, y) { return [W / 2 + (x - c.x) * c.zoom, H / 2 + (y - c.y) * c.zoom]; }

  // ---------- paper ----------
  let _tile = null, _grain = null;
  function paperTile() {
    if (_tile) return _tile;
    const S = 512, c = new OffscreenCanvas(S, S), g = c.getContext('2d'), R = mulberry(7);
    g.fillStyle = P.paper; g.fillRect(0, 0, S, S);
    const id = g.getImageData(0, 0, S, S), d = id.data;
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      const u = x / S * 8, v = y / S * 8;
      const lo = Math.sin(u * .785 + Math.sin(v * .785) * 1.3) * .5 + Math.sin(v * 1.57 + 1.3) * .3;
      const n = (R() - .5) * 5 + lo * 2.2, i = (y * S + x) * 4;
      d[i] += n; d[i + 1] += n; d[i + 2] += n * .9;
    }
    g.putImageData(id, 0, 0);
    for (let k = 0; k < 900; k++) {
      const x = R() * S, y = R() * S, a = R() * Math.PI * 2, l = 3 + R() * 14;
      g.strokeStyle = R() < .5 ? 'rgba(120,100,70,.07)' : 'rgba(255,255,255,.35)'; g.lineWidth = .6 + R() * .6;
      g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + Math.cos(a + .6) * l * .5, y + Math.sin(a + .6) * l * .5, x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke();
    }
    return (_tile = c);
  }
  function grainTile() {
    if (_grain) return _grain;
    const S = 256, c = new OffscreenCanvas(S, S), g = c.getContext('2d'), R = mulberry(11), id = g.createImageData(S, S);
    for (let i = 0; i < S * S; i++) { const r = R(); id.data[i * 4 + 3] = r < .16 ? 255 * (.35 + R() * .65) : 0; }
    g.putImageData(id, 0, 0); return (_grain = c);
  }
  // paper over the world rect [x0, y0, x1, y1] (default: the whole frame), with the faint dot grid in world space
  function drawPaper(g, c, rect, dots = 1, step = 30) {
    applyCam(g, c);
    const [x0, y0, x1, y1] = rect || [c.x - W / 2 / c.zoom - 40, c.y - H / 2 / c.zoom - 40, c.x + W / 2 / c.zoom + 40, c.y + H / 2 / c.zoom + 40];
    g.fillStyle = P.paper; g.fillRect(x0, y0, x1 - x0, y1 - y0);
    g.fillStyle = g.createPattern(paperTile(), 'repeat'); g.fillRect(x0, y0, x1 - x0, y1 - y0);
    if (dots > 0) {
      g.fillStyle = P.dotgrid; g.globalAlpha = dots; const r = 1.6;
      for (let x = Math.ceil(x0 / step) * step; x < x1; x += step) for (let y = Math.ceil(y0 / step) * step; y < y1; y += step) g.fillRect(x - r, y - r, 2 * r, 2 * r);
      g.globalAlpha = 1;
    }
  }

  // ---------- the pencil stroke: any polyline in pencil, write-on by progress; returns the tip ----------
  function resample(pts, step = 3) {
    const out = [pts[0]], L = [0]; let acc = 0;
    for (let i = 1; i < pts.length; i++) {
      const [ax, ay] = pts[i - 1], [bx, by] = pts[i], d = Math.hypot(bx - ax, by - ay), n = Math.max(1, Math.ceil(d / step));
      for (let k = 1; k <= n; k++) { acc += d / n; out.push([ax + (bx - ax) * k / n, ay + (by - ay) * k / n]); L.push(acc); }
    }
    return { pts: out, len: L, total: acc };
  }
  function pencilStroke(g, pts, o = {}) {
    const { color = P.graphite, width = 3, progress = 1, seed = 1, wobble = .6, passes = 2, alpha = .92, grain = .5, taper = true } = o;
    if (progress <= 0 || pts.length < 2) return pts[0];
    const R = resample(pts, 2.5), n = R.pts.length, end = R.total * clamp(progress);
    const P2 = R.pts.map((p, i) => {
      const a = R.pts[Math.max(0, i - 1)], b = R.pts[Math.min(n - 1, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
      const w = (vnoise(R.len[i] * .02 + seed * 13.1) - .5) * 2 * wobble * width;
      return [p[0] - dy / l * w, p[1] + dx / l * w];
    });
    const a0 = g.globalAlpha;
    g.save(); g.lineCap = 'round'; g.lineJoin = 'round'; g.strokeStyle = color;
    let tip = P2[0];
    for (let pass = 0; pass < passes; pass++) {
      const off = pass ? (hash(seed + pass) - .5) * width * .5 : 0;
      for (let i = 1; i < n; i++) {
        if (R.len[i - 1] > end) break;
        const f = R.len[i] / Math.max(1, R.total);
        const tp = taper ? Math.min(1, f * 8, (1 - f) * 8 + .35) : 1;
        const gr = 1 - grain * hash(i * 1.7 + seed * 31 + pass * 7);
        g.globalAlpha = a0 * alpha * gr * (pass ? .45 : 1);
        g.lineWidth = width * (.75 + .25 * tp) * (pass ? .6 : 1);
        let [bx, by] = P2[i];
        if (R.len[i] > end) { const [ax, ay] = P2[i - 1], k = (end - R.len[i - 1]) / (R.len[i] - R.len[i - 1]); bx = ax + (bx - ax) * k; by = ay + (by - ay) * k; }
        g.beginPath(); g.moveTo(P2[i - 1][0] + off, P2[i - 1][1] + off); g.lineTo(bx + off, by + off); g.stroke();
        tip = [bx, by];
      }
    }
    g.restore(); return tip;
  }
  // annotation geometry (source: quadPath, leader, ringPath, wavePath, heartPath, bracketPath)
  const quadPath = (a, c, b, n = 24) => Array.from({ length: n + 1 }, (_, i) => { const t = i / n, u = 1 - t; return [u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]; });
  function leaderPath(a, b, bend = .22) { const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1]; return quadPath(a, [mx - dy * bend, my + dx * bend], b); }
  function ringPath(x, y, r, seed = 1, turns = 1.12, a0 = -2.2) {
    const n = 48, out = [];
    for (let i = 0; i <= n; i++) { const t = i / n, a = a0 + t * turns * Math.PI * 2, rr = r * (1 + .08 * Math.sin(t * 5 + seed) + t * .06); out.push([x + Math.cos(a) * rr * 1.08, y + Math.sin(a) * rr]); }
    return out;
  }
  function wavePath(x, y, w) {
    const out = [], s = w / 66;
    for (let i = 0; i <= 90; i++) { const t = i / 90, X = x + t * 66 * s, ph = t * Math.PI * 6; out.push([X + Math.sin(ph) * 3 * s, y - Math.abs(Math.sin(ph / 2)) * 9 * s + Math.cos(ph) * 2 * s]); }
    return out;
  }
  function heartPath(x, y, s = 1) {
    const out = [];
    for (let i = 0; i <= 60; i++) { const t = -Math.PI + i / 60 * Math.PI * 2 + .15; out.push([x + 16 * Math.pow(Math.sin(t), 3) * s * .55, y - (13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)) * s * .55]); }
    return out;
  }
  function underPath(x0, x1, y, seed = 1) {           // a quick hand underline, slightly rising
    return Array.from({ length: 21 }, (_, i) => { const t = i / 20; return [x0 + (x1 - x0) * t, y - t * 6 + Math.sin(t * 3 + seed) * 2]; });
  }
  function strikePath(x0, x1, y) { return [[x0 - 6, y + 3], [x1 + 6, y - 5]]; }
  function shapePts(el) {
    const a = el.args || [];
    switch (el.shape) {
      case 'ring': return ringPath(a[0], a[1], a[2], el.seed || 1);
      case 'leader': return leaderPath([a[0], a[1]], [a[2], a[3]], a[4] ?? .22);
      case 'wave': return wavePath(a[0], a[1], a[2]);
      case 'heart': return heartPath(a[0], a[1], a[2]);
      case 'under': return underPath(a[0], a[1], a[2], el.seed || 1);
      case 'strike': return strikePath(a[0], a[1], a[2]);
      default: return el.pts;
    }
  }

  // ---------- handwriting (Caveat) with graphite grain and left->right write-on ----------
  const _txt = new Map();
  function fontsReady() { try { return document.fonts.check(`500 40px ${F.hand}`) && document.fonts.check(`400 40px ${F.serif}`); } catch (e) { return true; } }
  function textImage(text, size, color, weight, font) {
    const key = [text, size, color, weight, font].join('|');
    if (_txt.has(key)) return _txt.get(key);
    const m = new OffscreenCanvas(8, 8).getContext('2d'); m.font = `${weight} ${size}px ${font}`;
    const w = Math.ceil(m.measureText(text).width + size * .6), h = Math.ceil(size * 1.7);
    const c = new OffscreenCanvas(w, h), g = c.getContext('2d');
    g.font = m.font; g.fillStyle = color; g.textBaseline = 'alphabetic';
    let x = size * .3; const R = mulberry(text.length * 97 + size);
    for (const ch of text) {                                         // per-glyph jitter = hand (source: +-1.7 deg, +-2.5 % baseline)
      g.save(); g.translate(x, h * .72 + (R() - .5) * size * .05); g.rotate((R() - .5) * .06); g.fillText(ch, 0, 0); g.restore();
      x += g.measureText(ch).width;
    }
    g.globalCompositeOperation = 'destination-out'; g.fillStyle = g.createPattern(grainTile(), 'repeat'); g.fillRect(0, 0, w, h);
    const r = { c, w, h, pad: size * .3, base: h * .72 };
    if (fontsReady()) { if (_txt.size > 300) _txt.clear(); _txt.set(key, r); }
    return r;
  }
  function handText(g, text, x, y, o = {}) {
    const { size = 64, color = P.blue, progress = 1, weight = 500, align = 'left', font = F.hand, alpha = 1 } = o;
    const im = textImage(text, size, color, weight, font);
    const tw = im.w - im.pad * 2, left = align === 'right' ? x - tw : align === 'center' ? x - tw / 2 : x;
    const X = left - im.pad, Y = y - im.base, pr = clamp(progress);
    if (pr > 0) {
      g.save(); g.globalAlpha *= alpha; g.beginPath(); g.rect(X, Y, im.pad + tw * pr + (pr >= 1 ? im.pad : 0), im.h); g.clip();
      g.drawImage(im.c, X, Y, im.w, im.h); g.restore();
    }
    const f = pr * tw, wig = Math.sin(f * .55 / (size / 30)) * .5 + Math.sin(f * 1.31 / (size / 30) + 1) * .3;
    return [left + f, y - size * (.28 + .22 * wig)];
  }
  // ---------- printed type, letter by letter ----------
  function setType(g, text, x, y, o = {}) {
    const { size = 48, font = F.mono, weight = 400, color = P.inkSoft, align = 'left', progress = 1, alpha = 1, rise = 0 } = o;
    g.save(); g.font = `${weight} ${size}px ${font}`; g.fillStyle = color; g.textBaseline = 'alphabetic';
    const tw = g.measureText(text).width; let cx = align === 'right' ? x - tw : align === 'center' ? x - tw / 2 : x;
    if (progress >= 1) { g.globalAlpha *= alpha; g.fillText(text, cx, y); g.restore(); return tw; }
    const chars = [...text], n = chars.length, a0 = g.globalAlpha;
    for (let i = 0; i < n; i++) {
      const k = clamp(progress * (n + 4) - i, 0, 4) / 4, cw = g.measureText(chars[i]).width;
      if (k > 0) { g.globalAlpha = a0 * alpha * k; g.fillText(chars[i], cx, y + (1 - k) * (rise || size * .25)); }
      cx += cw;
    }
    g.restore(); return tw;
  }
  // ---------- data marks ----------
  function dataDot(g, x, y, r, fill, fresh, o = {}) {
    const { ring = P.ink, ringW = 2.4, alpha = 1, ripple = 1 } = o;
    if (fresh < 0) return;
    const pop = fresh < .25 ? 1 + .55 * Math.sin(clamp(fresh / .25) * Math.PI) * (1 - fresh / .25 * .4) : 1;
    g.save(); g.globalAlpha *= alpha;
    if (ripple && fresh < .6) { const k = fresh / .6, a0 = g.globalAlpha; g.strokeStyle = fill; g.globalAlpha = a0 * (1 - k) * .55; g.lineWidth = 2; g.beginPath(); g.arc(x, y, r * (1.2 + k * 2.4), 0, Math.PI * 2); g.stroke(); g.globalAlpha = a0; }
    g.beginPath(); g.arc(x, y, r * pop, 0, Math.PI * 2); g.fillStyle = fill; g.fill(); g.lineWidth = ringW; g.strokeStyle = ring; g.stroke();
    g.restore();
  }
  // a closed path as a pencil-annotated mark: flat fill + light graphite hatching + hand outline (source inkShape)
  function inkShape(g, path, o = {}) {
    const { fill = null, stroke = P.ink, hatch = .5, progress = 1, seed = 3, width = 2.4, fillAlpha = 1 } = o;
    if (fill && progress > 0) {
      g.save(); g.globalAlpha *= clamp(progress * 1.5) * fillAlpha; g.beginPath(); g.moveTo(...path[0]); for (const p of path.slice(1)) g.lineTo(...p); g.closePath(); g.fillStyle = fill; g.fill();
      if (hatch > 0) {
        g.clip(); const xs = path.map(p => p[0]), ys = path.map(p => p[1]), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), a0 = g.globalAlpha;
        g.strokeStyle = 'rgba(40,30,20,.12)'; g.lineWidth = 1.4;
        for (let x = x0 - (y1 - y0); x < x1; x += 10) { g.globalAlpha = a0 * hatch * (.5 + .5 * hash(x + seed)); g.beginPath(); g.moveTo(x, y1); g.lineTo(x + (y1 - y0), y0); g.stroke(); }
      }
      g.restore();
    }
    return pencilStroke(g, [...path, path[0]], { color: stroke, width, progress, seed, passes: 2, wobble: .35 });
  }
  // the dashed "empty cell", drawn on (source dashedCell)
  function dashedCell(g, x0, y0, x1, y1, o = {}) {
    const { progress = 1, color = P.red, width = 2.6, dash = 14, gap = 10 } = o;
    const R = resample([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]], 1.5), end = R.total * clamp(progress), a0 = g.globalAlpha;
    let tip = [x0, y0];
    g.save(); g.strokeStyle = color; g.lineWidth = width; g.lineCap = 'round';
    for (let i = 1; i < R.pts.length; i++) {
      if (R.len[i] > end) break;
      tip = R.pts[i];
      if ((R.len[i] % (dash + gap)) < dash) { g.globalAlpha = a0 * .85 * (1 - .4 * hash(i)); g.beginPath(); g.moveTo(...R.pts[i - 1]); g.lineTo(...R.pts[i]); g.stroke(); }
    }
    g.restore(); return tip;
  }
  // graphite hatching that fills a cell (the phone's minutes) and can be erased by a sweep
  function hatchRect(g, x0, y0, x1, y1, o = {}) {
    const { progress = 1, erase = 0, color = P.graphite, seed = 5, step = 11 } = o;
    if (progress <= 0 || erase >= 1) return null;
    const w = x1 - x0, h = y1 - y0;
    g.save(); g.beginPath(); g.rect(x0 + w * erase, y0, w * (1 - erase), h); g.clip();
    g.strokeStyle = color; g.lineCap = 'round'; let tip = null;
    const n = Math.ceil((w + h) / step), m = Math.floor(n * clamp(progress)), a0 = g.globalAlpha;
    for (let i = 0; i < m; i++) {
      const s = i * step, ax = x0 + Math.max(0, s - h), ay = y0 + Math.min(h, s), bx = x0 + Math.min(w, s), by = y0 + Math.max(0, s - w);
      g.globalAlpha = a0 * (.45 + .3 * hash(i + seed)); g.lineWidth = 2 + hash(i * 3 + seed);
      g.beginPath(); g.moveTo(ax, ay); g.lineTo(bx, by); g.stroke(); tip = [bx, by];
    }
    g.restore(); return progress < 1 ? tip : null;
  }

  // ---------- the red-blue pencil (screen space; source drawPencil) ----------
  let _pc = null, _pb = null;
  function pencilBody(g, end, axisScale) {
    const Lg = 16, Lw = 58, Wd = 24, len = 1400;
    g.save(); g.scale(axisScale, 1);
    const cA = end === 'red' ? P.red : P.blue, cB = end === 'red' ? P.blue : P.red;
    g.fillStyle = cA; g.fillRect(Lg + Lw - 2, -Wd / 2, len * .5, Wd);
    g.fillStyle = cB; g.fillRect(Lg + Lw - 2 + len * .5, -Wd / 2, len * .5, Wd);
    g.fillStyle = 'rgba(255,255,255,.18)'; g.fillRect(Lg + Lw - 2, -Wd / 2 + 3, len, 5);
    g.fillStyle = 'rgba(0,0,0,.16)'; g.fillRect(Lg + Lw - 2, Wd / 2 - 6, len, 6);
    g.fillStyle = P.wood; g.beginPath(); g.moveTo(Lg * .9, -3.2); g.lineTo(Lg + Lw, -Wd / 2);
    for (let i = 0; i <= 6; i++) g.lineTo(Lg + Lw + (i % 2 ? 5 : 0), -Wd / 2 + Wd * i / 6); g.lineTo(Lg * .9, 3.2); g.closePath(); g.fill();
    g.fillStyle = 'rgba(150,110,60,.25)'; g.beginPath(); g.moveTo(Lg * .9, 1); g.lineTo(Lg + Lw, Wd / 2 - 2); g.lineTo(Lg + Lw, Wd / 2); g.lineTo(Lg * .9, 3.2); g.fill();
    g.fillStyle = end === 'red' ? '#8E2232' : '#274E75'; g.beginPath(); g.moveTo(0, 0); g.lineTo(Lg, -3.6); g.lineTo(Lg, 3.6); g.closePath(); g.fill();
    g.restore();
  }
  function drawPencil(g, o) {
    const { tip, s = 1, lift = 0, flip = 0, ang = 0.62, alpha = 1 } = o;
    if (alpha <= 0 || !tip) return;
    if (!_pc) { _pc = new OffscreenCanvas(W, H); _pb = new OffscreenCanvas(W, H); }
    const axisScale = Math.cos(clamp(flip) * Math.PI), end = axisScale >= 0 ? 'blue' : 'red', as = Math.max(.04, Math.abs(axisScale));
    const lz = 1 + lift * .35;
    const draw = (c, col) => {
      const q = c.getContext('2d'); q.setTransform(1, 0, 0, 1, 0, 0); q.globalCompositeOperation = 'source-over'; q.clearRect(0, 0, W, H);
      q.translate(tip[0], tip[1]); q.rotate(ang); q.scale(s * lz, s * lz); q.translate(180 * (1 - as), 0);
      pencilBody(q, end, as);
      if (col) { q.globalCompositeOperation = 'source-in'; q.setTransform(1, 0, 0, 1, 0, 0); q.fillStyle = col; q.fillRect(0, 0, W, H); q.globalCompositeOperation = 'source-over'; }
    };
    g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = alpha;
    draw(_pb, 'rgba(70,50,30,1)');                                   // shadow: farther and softer with lift
    const sh = 3 + lift * 70 * s, sb = 2 + lift * 16;
    g.filter = `blur(${sb.toFixed(1)}px)`; g.globalAlpha = alpha * (.2 - lift * .08);
    g.drawImage(_pb, sh * .8, sh * 1.1); g.filter = 'none'; g.globalAlpha = alpha;
    draw(_pc, null);
    const b = lift * 2.5;                                             // depth of field: sharp tip, soft body
    g.filter = `blur(${(b + 3).toFixed(1)}px)`; g.drawImage(_pc, 0, 0); g.filter = 'none';
    const q = _pb.getContext('2d'); q.setTransform(1, 0, 0, 1, 0, 0); q.globalCompositeOperation = 'source-over'; q.clearRect(0, 0, W, H);
    q.filter = b > .3 ? `blur(${b.toFixed(1)}px)` : 'none'; q.drawImage(_pc, 0, 0); q.filter = 'none';
    q.globalCompositeOperation = 'destination-in';
    const gr = q.createLinearGradient(tip[0], tip[1], tip[0] + Math.cos(ang) * 320 * s, tip[1] + Math.sin(ang) * 320 * s);
    gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
    q.fillStyle = gr; q.fillRect(0, 0, W, H); q.globalCompositeOperation = 'source-over';
    g.drawImage(_pb, 0, 0);
    g.restore();
  }

  // ---------- figure caption: kicker, hairline rule, words on their times (source caption), on a paper band over the face ----------
  function wrapWords(g, words, maxW) {
    const sp = g.measureText(' ').width, lines = [[]]; let lw = 0;
    for (const wd of words) { const ww = g.measureText(wd.w).width; if (lw + ww > maxW && lines[lines.length - 1].length) { lines.push([]); lw = 0; } lines[lines.length - 1].push({ ...wd, ww }); lw += ww + sp; }
    return { lines, sp };
  }
  function caption(g, C, cap, t, band) {
    if (t < C.t0 - .001 || t > C.t1 + (C.hard ? 0 : .3)) return;
    const out = t > C.t1 && !C.hard ? clamp((t - C.t1) / .3) : 0, inn = C.t0 <= 0 ? 1 : clamp((t - C.t0) / .1);
    g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
    if (band) {                                                       // the paper band (only over the face; pages are paper already)
      g.fillStyle = P.paper; g.fillRect(0, cap.band[0], W, cap.band[1] - cap.band[0]);
      g.fillStyle = g.createPattern(paperTile(), 'repeat'); g.fillRect(0, cap.band[0], W, cap.band[1] - cap.band[0]);
      g.fillStyle = 'rgba(43,39,35,.18)'; g.fillRect(0, cap.band[0] - 2, W, 2);
    }
    g.globalAlpha = (1 - out); g.translate(0, -out * 26);
    let size = cap.size, lines, sp;
    for (; ; size -= 2) {                                             // two lines at most: shrink, never under the 48 px floor
      g.font = `400 ${size}px ${F.serif}`; ({ lines, sp } = wrapWords(g, C.words, cap.maxW));
      if (lines.length <= 2 || size <= 48) break;
    }
    g.textBaseline = 'alphabetic';
    const lh = size * 1.2, base0 = cap.base - (lines.length - 1) * lh;
    const maxLine = Math.max(...lines.map(L => L.reduce((a, b) => a + b.ww + sp, -sp)));
    g.strokeStyle = P.ink; g.lineWidth = 1.6;
    g.beginPath(); g.moveTo(cap.x, cap.rule); g.lineTo(cap.x + Math.max(300, maxLine) * clamp(inn * 1.2), cap.rule); g.stroke();
    if (C.kicker) setType(g, C.kicker, cap.x, cap.rule - 18, { size: cap.kicker, color: P.inkSoft, progress: C.kickerIn === false ? 1 : clamp((t - C.t0) / .5) });
    g.fillStyle = P.ink;
    lines.forEach((L, li) => {
      let cx = cap.x;
      for (const wd of L) {
        const k = clamp((t - wd.t) / .125);
        if (k > 0) { g.save(); g.globalAlpha *= k; g.fillText(wd.w, cx, base0 + li * lh + (1 - k) * 6); g.restore(); }
        cx += wd.ww + sp;
      }
    });
    g.restore();
  }

  // ---------- the painter: SPEC.layers (pages on paper, notes over the face), captions, the pencil ----------
  const imgCache = {};
  function camAt(L, t) {
    const ks = L.cam || [[L.t0, 1, W / 2, H / 2]];
    if (t <= ks[0][0]) return { zoom: ks[0][1], x: ks[0][2], y: ks[0][3] };
    for (let i = 0; i < ks.length - 1; i++) {
      const [a, z0, x0, y0] = ks[i], [b, z1, x1, y1, ez] = ks[i + 1];
      if (t <= b) { const e = ez === 'lin' ? clamp((t - a) / (b - a)) : eio((t - a) / (b - a)); return { zoom: lerp(z0, z1, e), x: lerp(x0, x1, e), y: lerp(y0, y1, e) }; }
    }
    const k = ks[ks.length - 1]; return { zoom: k[1], x: k[2], y: k[3] };
  }
  function prog(el, t) { return el.b > el.a ? clamp((t - el.a) / (el.b - el.a)) : (t >= el.a ? 1 : 0); }
  function fadeOut(el, t) { return el.out ? 1 - clamp((t - el.out) / .2) : 1; }
  // draws one element; returns its pencil tip (world) while the pencil is drawing it
  function drawEl(g, el, t) {
    if (t < el.a - .0001) return null;
    const al = fadeOut(el, t); if (al <= 0) return null;
    const p = prog(el, t), live = p > 0 && p < 1;
    g.save(); g.globalAlpha *= al; let tip = null;
    switch (el.k) {
      case 'hand': tip = handText(g, el.text, el.x, el.y, { size: el.size, color: el.color, progress: p, align: el.align }); break;
      case 'type': setType(g, el.text, el.x, el.y, { size: el.size, font: F[el.font || 'mono'], weight: el.weight || 400, color: el.color || P.inkSoft, align: el.align, progress: p }); break;
      case 'stroke': tip = pencilStroke(g, shapePts(el), { color: el.color, width: el.width || 3, progress: p, seed: el.seed || 1, passes: el.passes ?? 2, wobble: el.wobble ?? .5 }); break;
      case 'rule': { g.strokeStyle = el.color || P.rule; g.lineWidth = el.width || 1.6; g.beginPath(); g.moveTo(el.x0, el.y0); g.lineTo(lerp(el.x0, el.x1, eo(p)), lerp(el.y0, el.y1, eo(p))); g.stroke(); break; }
      case 'bar': {                                                   // a bar grows from its zero line, then gets its pencil outline
        const e = eo(clamp(p / .7)), x1 = lerp(el.x0, el.x1, e);
        if (x1 - el.x0 > 1) {
          const path = [[el.x0, el.y0], [x1, el.y0], [x1, el.y1], [el.x0, el.y1]];
          inkShape(g, path, { fill: el.fill, progress: 1, width: 0.01, hatch: .6, seed: el.seed || 3 });
          if (p > .7) pencilStroke(g, [...path, path[0]], { color: P.ink, width: 2.4, progress: (p - .7) / .3, seed: el.seed || 3, passes: 2, wobble: .3 });
        }
        tip = p < .7 ? [x1, (el.y0 + el.y1) / 2] : [x1, el.y1]; break;
      }
      case 'fill': {                                                  // a cell filled left->right (sleep hours), optional erase
        const e = eo(p), er = el.erase ? eio(clamp((t - el.erase[0]) / (el.erase[1] - el.erase[0]))) : 0, x1 = lerp(el.x0, el.x1, e);
        if (x1 - el.x0 > 1 && er < 1) { const xa = lerp(el.x0, el.x1, er); g.fillStyle = el.fill; g.fillRect(xa, el.y0, Math.max(0, x1 - xa), el.y1 - el.y0); }
        tip = [x1, (el.y0 + el.y1) / 2]; break;
      }
      case 'hatch': {
        const er = el.erase ? eio(clamp((t - el.erase[0]) / (el.erase[1] - el.erase[0]))) : 0;
        tip = hatchRect(g, el.x0, el.y0, el.x1, el.y1, { progress: p, erase: er, color: el.color || P.graphite, seed: el.seed || 5 }); break;
      }
      case 'cell': tip = dashedCell(g, el.x0, el.y0, el.x1, el.y1, { progress: p, color: el.color || P.red, width: el.width || 2.6 }); break;
      case 'slip': {                                                  // a torn paper slip pinned over the footage, under a note
        const k = eo(clamp((t - el.a) / .15)), sc = 1.04 - .04 * k, cx = (el.x0 + el.x1) / 2, cy = (el.y0 + el.y1) / 2, w = el.x1 - el.x0, h = el.y1 - el.y0;
        g.globalAlpha *= clamp(k * 3); g.translate(cx, cy); g.rotate((el.rot || 0) * Math.PI / 180); g.scale(sc, sc);
        g.fillStyle = 'rgba(40,25,10,.28)'; g.fillRect(-w / 2 + 6, -h / 2 + 9, w, h);
        const R = mulberry(el.seed || 9), top = [], bot = [];
        for (let i = 0; i <= 24; i++) { top.push([-w / 2 + w * i / 24, -h / 2 + (R() - .5) * 5]); bot.push([w / 2 - w * i / 24, h / 2 + (R() - .5) * 7]); }
        const path = [...top, ...bot]; g.beginPath(); g.moveTo(...path[0]); for (const q of path.slice(1)) g.lineTo(...q); g.closePath();
        g.fillStyle = P.paper; g.fill(); g.fillStyle = g.createPattern(paperTile(), 'repeat'); g.fill();
        break;
      }
      case 'box': {                                                   // a plain ink cell outline (grid of a unit chart)
        g.strokeStyle = el.color || P.zero; g.lineWidth = el.width || 2; g.globalAlpha *= clamp(p * 1.5);
        g.strokeRect(el.x0, el.y0, el.x1 - el.x0, el.y1 - el.y0); break;
      }
      case 'dot': dataDot(g, el.x, el.y, el.r || 14, el.fill || P.blue, t - el.a); break;
      case 'img': {
        let im = imgCache[el.id]; if (!im) { im = document.getElementById(el.id); if (im) imgCache[el.id] = im; }
        if (im && im.complete && im.naturalWidth) {
          const k = eo(clamp((t - el.a) / .35)), sc = 1.06 - .06 * k;
          g.translate(el.x + el.w / 2, el.y + el.h / 2); g.rotate((el.rot || 0) * Math.PI / 180); g.scale(sc, sc); g.globalAlpha *= clamp(k * 2);
          g.fillStyle = 'rgba(70,50,30,.18)'; g.fillRect(-el.w / 2 + 10, -el.h / 2 + 14, el.w, el.h);   // the print's soft shadow on the paper
          g.drawImage(im, -el.w / 2, -el.h / 2, el.w, el.h);
          g.strokeStyle = 'rgba(43,39,35,.35)'; g.lineWidth = 1.5; g.strokeRect(-el.w / 2, -el.h / 2, el.w, el.h);
        }
        break;
      }
    }
    g.restore();
    return live && el.pen !== false ? tip : null;
  }
  // the pencil of a layer at t: on the element being drawn; between strokes it lifts and travels; it arrives and exits
  function pencilOf(L, t, cam) {
    const acts = L.acts; if (!acts || !acts.length || L.pencil === false) return null;
    const off = L.offscreen || (L.ang < 0 ? [W + 260, -260] : [W + 200, H + 300]);
    const S = p => w2s(cam, p[0], p[1]);
    let cur = null, prev = null, next = null;
    for (const a of acts) { if (t >= a.a && t <= a.b) cur = a; else if (a.b < t) prev = a; else if (!next && a.a > t) next = a; }
    const flipOf = a => (a && a.red ? 1 : 0);
    if (cur) {
      const tip = cur.tipAt(t); return { tip: S(tip), lift: .05 + .08 * Math.abs(Math.sin(t * 19)), flip: flipOf(cur) };
    }
    if (prev && next && next.a - prev.b < 1.6) {                      // hop to the next mark
      const u = (t - prev.b) / (next.a - prev.b), A = S(prev.end), B = S(next.start), e = eio(u);
      return { tip: [lerp(A[0], B[0], e), lerp(A[1], B[1], e)], lift: .1 + Math.sin(u * Math.PI) * .9, flip: lerp(flipOf(prev), flipOf(next), ss((u - .2) / .6)) };
    }
    if (next && (!prev || next.a - t < .45)) {                         // arrive from the edge
      const u = clamp(1 - (next.a - t) / .45); if (u <= 0) return null;
      const B = S(next.start), e = eo(u);
      return { tip: [lerp(off[0], B[0], e), lerp(off[1], B[1], e)], lift: 1 - e * .9, flip: flipOf(next) };
    }
    if (prev) {                                                       // lift, then exit
      const u = clamp((t - prev.b - .25) / .5), A = S(prev.end), e = eio(u);
      if (u >= 1) return null;
      return { tip: [lerp(A[0], off[0], e), lerp(A[1], off[1], e)], lift: .1 + Math.min(1, (t - prev.b) / .25) * .6 + e * .4, flip: flipOf(prev) };
    }
    return null;
  }
  function prepare(SPEC) {
    if (SPEC._ready) return;
    const off = new OffscreenCanvas(8, 8).getContext('2d');
    for (const L of SPEC.layers) {
      L.acts = [];
      for (const el of L.els) {
        if (el.pen === false || !(el.b > el.a) || !['hand', 'stroke', 'bar', 'cell', 'hatch', 'fill'].includes(el.k)) continue;
        const tipAt = tt => { const q = { ...el, out: null }; return drawEl(off, q, Math.min(el.b - 1e-4, Math.max(el.a + 1e-4, tt))) || [el.x || el.x0 || 0, el.y || el.y0 || 0]; };
        L.acts.push({ a: el.a, b: el.b, red: el.color === P.red || el.red, tipAt, start: tipAt(el.a + 1e-3), end: tipAt(el.b - 1e-3) });
      }
      L.acts.sort((p, q) => p.a - q.a);
    }
    SPEC._ready = fontsReady();
  }
  function paint(g, SPEC, t) {
    prepare(SPEC);
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, W, H);
    let onPaper = false; const pens = [];
    for (const L of SPEC.layers) {
      if (t < L.t0 - .0001 || t >= L.t1) continue;
      const cam = camAt(L, t);
      if (L.paper) { drawPaper(g, cam, null, L.dots ?? 1); onPaper = true; }
      applyCam(g, cam);
      for (const el of L.els) drawEl(g, el, t);
      g.setTransform(1, 0, 0, 1, 0, 0);
      const pen = pencilOf(L, t, cam); if (pen) pens.push({ ...pen, ang: L.ang ?? .62, s: L.pencilScale || 1.25 });
    }
    for (const C of SPEC.captions) caption(g, C, SPEC.cap, t, !onPaper);
    for (const p of pens) drawPencil(g, p);
  }
  window.DS = { paint, P, W, H, F, fontsReady, clearCache: () => { _txt.clear(); } };
})();
