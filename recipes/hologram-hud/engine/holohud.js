// Hologram HUD engine for ghost-editor (ghost-editor recipe hologram-hud), 1080x1920, Canvas 2D, deterministic.
// Adapted from Lemo-Opuscar styles/hologram-hud/demo/engine/holo.js + hud.js (MIT, Copyright (c) 2026 LemoLab;
// see ../LICENSE-lemo-opuscar.txt and ../CREDITS.txt). Changes: one classic script (window.HH, no modules), vertical
// frame layout, Cyrillic type (Exo 2 + JetBrains Mono instead of Rajdhani + Share Tech Mono), every word >= 48 px,
// Cyrillic garbage glyphs in rollText, a toggle chip, multi-part target boxes, the phone / book / basics models,
// and a data-driven scene renderer HH.render(ctx, t, SC) that a paused GSAP timeline calls on every seek.
(function () {
'use strict';
const TAU = Math.PI * 2;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const eo = t => 1 - Math.pow(1 - clamp(t), 3);
const eio = t => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const hash = n => { n = Math.sin(n * 127.1 + 311.7) * 43758.5453; return n - Math.floor(n); };
const FONT = { ui: '"Exo 2"', mono: '"JetBrains Mono"' };
const W = 1080, H = 1920, FPS = 30;

// ===================================================================== wireframe engine (holo.js)
function prepModel(j) {
  let ymin = 1e9, ymax = -1e9;
  for (const P of j.parts) for (const C of P.pieces) {
    C.v = Float32Array.from(C.v); C.e = Uint32Array.from(C.e); C.q = Uint32Array.from(C.q || []);
    C.part = P.id; C.n = C.v.length / 3; C.explode = C.explode || [0, 0, 0];
    for (let i = 1; i < C.v.length; i += 3) { ymin = Math.min(ymin, C.v[i]); ymax = Math.max(ymax, C.v[i]); }
  }
  j.ymin = ymin; j.ymax = ymax;
  j.byId = Object.fromEntries(j.parts.map(P => [P.id, P]));
  return j;
}
function normalizeModel(m, diag = 2.3117) {
  let mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
  for (const P of m.parts) for (const C of P.pieces) for (let i = 0; i < C.v.length; i += 3) for (let k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], C.v[i + k]); mx[k] = Math.max(mx[k], C.v[i + k]); }
  const s = diag / Math.hypot(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]);
  const o = [(mn[0] + mx[0]) / 2, mn[1], (mn[2] + mx[2]) / 2];
  const T = p => [(p[0] - o[0]) * s, (p[1] - o[1]) * s, (p[2] - o[2]) * s];
  for (const P of m.parts) {
    P.anchor = T(P.anchor); if (P.center) P.center = T(P.center);
    for (const C of P.pieces) {
      for (let i = 0; i < C.v.length; i += 3) { C.v[i] = (C.v[i] - o[0]) * s; C.v[i + 1] = (C.v[i + 1] - o[1]) * s; C.v[i + 2] = (C.v[i + 2] - o[2]) * s; }
      C.explode = C.explode.map(x => x * s);
      if (C.axis) C.axis = { c: T(C.axis.c), d: C.axis.d };
      if (C.face) C.face = C.face.map(T);
    }
  }
  m.ymin = 0; m.ymax = (mx[1] - mn[1]) * s; m.scale = s;
  return m;
}
function makeCamera(cam) {
  const T = cam.target, yaw = cam.yaw, pitch = cam.pitch, dist = cam.dist;
  const cp = Math.cos(pitch), sp = Math.sin(pitch), cy = Math.cos(yaw), sy = Math.sin(yaw);
  const eye = [T[0] + dist * sy * cp, T[1] + dist * sp, T[2] + dist * cy * cp];
  let f = [T[0] - eye[0], T[1] - eye[1], T[2] - eye[2]]; const fl = Math.hypot(...f); f = f.map(x => x / fl);
  let r = [-f[2], 0, f[0]]; const rl = Math.hypot(...r); r = r.map(x => x / rl);
  const u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]];
  const foc = (W / 2) / Math.tan((cam.fov || 0.6) / 2);      // vertical frame: the fov spans the WIDTH
  const cx = cam.cx ?? W / 2, cyy = cam.cy ?? H / 2;
  const project = (x, y, z, out) => {
    const dx = x - eye[0], dy = y - eye[1], dz = z - eye[2];
    const zc = dx * f[0] + dy * f[1] + dz * f[2];
    const xc = dx * r[0] + dy * r[1] + dz * r[2], yc = dx * u[0] + dy * u[1] + dz * u[2];
    const k = foc / Math.max(zc, 0.02);
    out[0] = cx + xc * k; out[1] = cyy - yc * k; out[2] = zc;
    return out;
  };
  return { project, eye, f, dist, foc };
}
function mk(w, h) { const c = document.createElement('canvas'); c.width = Math.round(w); c.height = Math.round(h); return c; }

class Holo {
  constructor() {
    this.L = mk(W, H); this.G1 = mk(W / 4, H / 4); this.G2 = mk(W / 8, H / 8); this.F = mk(W, H);
    const pc = mk(1, 4), pg = pc.getContext('2d');
    pg.fillStyle = 'rgba(0,0,0,1)'; pg.fillRect(0, 0, 1, 2); pg.fillStyle = 'rgba(0,0,0,0.38)'; pg.fillRect(0, 2, 1, 2);
    this.scanPat = this.F.getContext('2d').createPattern(pc, 'repeat');
    this.tmp = new Float32Array(3);
  }
  // opts: hue, spin, scan {y, band}, scanDown {y}, explode {id: 0-1}, solid 0-1, focus + dim, flash {part: 0-1},
  // wave {y, w}, lineWidth, gain, glow, alpha, dimParts {part: mul}
  draw(ctx, model, cam, o = {}) {
    const L = this.L, g = L.getContext('2d');
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, W, H);
    const C = makeCamera(cam), P = C.project, t3 = this.tmp;
    const hue = o.hue ?? 190, gain = o.gain ?? 1, solid = o.solid || 0;
    const spin = o.spin || 0, cs = Math.cos(spin), sn = Math.sin(spin);
    const scan = o.scan, sy = scan ? scan.y : Infinity, band = scan?.band ?? 0.06;
    const down = o.scanDown, wave = o.wave;
    const info = { bbox: {}, anchor: {}, project: P, cam: C, spin };
    const dN = C.dist - 1.1, dF = C.dist + 1.1, LV = 7;
    const paths = [], hot = [], fills = [];
    for (let i = 0; i < LV; i++) { paths.push(new Path2D()); hot.push(new Path2D()); fills.push(new Path2D()); }
    const dots = new Path2D();
    const tr = (x, y, z, out) => { out[0] = x * cs + z * sn; out[1] = y; out[2] = -x * sn + z * cs; return out; };
    info.tr = tr;
    for (const Pt of model.parts) {
      if (o.only && !o.only.includes(Pt.id)) continue;
      let focusMul = o.focus && !o.focus.includes(Pt.id) ? (o.dim ?? 0.25) : 1;
      if (o.dimParts && o.dimParts[Pt.id] !== undefined) focusMul *= o.dimParts[Pt.id];
      let bx0 = 1e9, by0 = 1e9, bx1 = -1e9, by1 = -1e9;
      for (const Pc of Pt.pieces) {
        const k = o.explode ? (o.explode[Pc.id] ?? o.explode[Pt.id] ?? 0) : 0;
        const vis = Pc.internal ? clamp(k * 3) : 1;
        if (vis <= 0.001) continue;
        const ex = Pc.explode[0] * k, ey = Pc.explode[1] * k, ez = Pc.explode[2] * k;
        const n = Pc.n, V = Pc.v;
        const S = new Float32Array(n * 3), Y = new Float32Array(n);
        for (let i = 0; i < n; i++) {
          const x = V[i * 3] + ex, y = V[i * 3 + 1] + ey, z = V[i * 3 + 2] + ez;
          Y[i] = y;
          tr(x, y, z, t3); P(t3[0], t3[1], t3[2], t3);
          S[i * 3] = t3[0]; S[i * 3 + 1] = t3[1]; S[i * 3 + 2] = t3[2];
          if (y <= sy && !Pc.internal && Pc.box !== false) {
            let bx = t3[0], by = t3[1];
            if (k && !o.boxExploded) { tr(x - ex, y - ey, z - ez, t3); P(t3[0], t3[1], t3[2], t3); bx = t3[0]; by = t3[1]; }
            if (bx < bx0) bx0 = bx; if (bx > bx1) bx1 = bx; if (by < by0) by0 = by; if (by > by1) by1 = by;
          }
        }
        if (Pc.face) {   // projected face corners (TL, TR, BR, BL) for a texture (the single-colour exception)
          info.faces = info.faces || {};
          info.faces[Pc.id] = Pc.face.map(p => { tr(p[0] + ex, p[1] + ey, p[2] + ez, t3); P(t3[0], t3[1], t3[2], t3); return [t3[0], t3[1]]; });
        }
        const E = Pc.e, mulA = focusMul * vis * gain;
        for (let j = 0; j < E.length; j += 2) {
          const a = E[j], b = E[j + 1];
          let ya = Y[a], yb = Y[b];
          let x0 = S[a * 3], y0 = S[a * 3 + 1], x1 = S[b * 3], y1 = S[b * 3 + 1];
          const zm = (S[a * 3 + 2] + S[b * 3 + 2]) / 2;
          if (scan) {
            if (ya > sy && yb > sy) continue;
            if (ya > sy || yb > sy) {
              const tc = (sy - ya) / (yb - ya), xi = x0 + (x1 - x0) * tc, yi = y0 + (y1 - y0) * tc;
              if (ya > sy) { x0 = xi; y0 = yi; ya = sy; } else { x1 = xi; y1 = yi; yb = sy; }
              dots.rect(xi - 2, yi - 2, 4, 4);
            }
          }
          if (down) {
            if (ya > down.y && yb > down.y) continue;
            if (ya > down.y || yb > down.y) {
              const tc = (down.y - ya) / (yb - ya), xi = x0 + (x1 - x0) * tc, yi = y0 + (y1 - y0) * tc;
              if (ya > down.y) { x0 = xi; y0 = yi; ya = down.y; } else { x1 = xi; y1 = yi; yb = down.y; }
              dots.rect(xi - 2, yi - 2, 4, 4);
            }
          }
          const fog = clamp(1 - (zm - dN) / (dF - dN) * 0.75, 0.22, 1);
          const lv = Math.min(LV - 1, Math.floor(fog * mulA * LV));
          if (lv < 0 || fog * mulA < 0.03) continue;
          const ymid = (ya + yb) / 2;
          const isHot = (scan && Math.max(ya, yb) > sy - band) || (down && Math.max(ya, yb) > down.y - 0.05) || (Pc.hot && k > 0.02) ||
            (wave && Math.abs(ymid - wave.y) < wave.w) || (o.flash && o.flash[Pt.id] > 0.5);
          const tg = isHot ? hot[lv] : paths[lv];
          tg.moveTo(x0, y0); tg.lineTo(x1, y1);
        }
        if (solid > 0) {
          const Q = Pc.q;
          for (let j = 0; j < Q.length; j += 4) {
            const a = Q[j], b = Q[j + 1], c = Q[j + 2], d = Q[j + 3];
            if (scan && Math.max(Y[a], Y[b], Y[c], Y[d]) > sy) continue;
            if (down && Math.max(Y[a], Y[b], Y[c], Y[d]) > down.y) continue;
            const ax_ = S[a * 3], ay_ = S[a * 3 + 1], bx_ = S[b * 3], by_ = S[b * 3 + 1], cx_ = S[c * 3], cy_ = S[c * 3 + 1], dx_ = S[d * 3], dy_ = S[d * 3 + 1];
            const area = Math.abs((cx_ - ax_) * (dy_ - by_) - (dx_ - bx_) * (cy_ - ay_)) / 2;
            const e1 = Math.hypot(bx_ - ax_, by_ - ay_), e2 = Math.hypot(dx_ - ax_, dy_ - ay_);
            const facing = clamp(area / Math.max(1e-3, e1 * e2));
            let fr = 0.3 + 0.7 * Math.pow(1 - facing, 1.6);
            if (wave) { const ym = (Y[a] + Y[c]) / 2, dw = Math.abs(ym - wave.y); if (dw < wave.w * 2) fr += (1 - dw / (wave.w * 2)) * 0.9; }
            const lv = Math.min(LV - 1, Math.floor(fr * solid * focusMul * vis * gain * LV));
            if (lv < 1) continue;
            const Tq = fills[lv];
            Tq.moveTo(ax_, ay_); Tq.lineTo(bx_, by_); Tq.lineTo(cx_, cy_); Tq.lineTo(dx_, dy_); Tq.closePath();
          }
        }
      }
      if (bx1 > bx0) info.bbox[Pt.id] = [bx0, by0, bx1, by1];
      const an = Pt.anchor; tr(an[0], an[1], an[2], t3); P(t3[0], t3[1], t3[2], t3); info.anchor[Pt.id] = [t3[0], t3[1], t3[2]];
    }
    g.globalCompositeOperation = 'lighter'; g.lineCap = 'round';
    if (solid > 0) {
      const F = this.F, f = F.getContext('2d');
      f.globalCompositeOperation = 'source-over'; f.clearRect(0, 0, W, H);
      f.globalCompositeOperation = 'lighter';
      for (let i = 1; i < LV; i++) { f.fillStyle = `hsla(${hue},90%,${55 + i * 5}%,${0.1 + (i / LV) * 0.6})`; f.fill(fills[i]); }
      f.globalCompositeOperation = 'destination-in'; f.setTransform(1, 0, 0, 1, 0, (o.scanOffset || 0) % 4); f.fillStyle = this.scanPat; f.fillRect(0, -8, W, H + 16); f.setTransform(1, 0, 0, 1, 0, 0);
      f.globalCompositeOperation = 'source-over';
      g.drawImage(F, 0, 0);
    }
    const lw = o.lineWidth || 1.8;
    for (let i = 0; i < LV; i++) {
      const a = (i + 1) / LV;
      g.strokeStyle = `hsla(${hue},100%,${50 + a * 30}%,${0.06 + a * 0.84})`; g.lineWidth = lw * (0.7 + a * 0.5);
      g.stroke(paths[i]);
    }
    for (let i = 0; i < LV; i++) { const a = (i + 1) / LV; g.strokeStyle = `hsla(${hue},70%,92%,${0.35 + a * 0.65})`; g.lineWidth = lw * 1.3; g.stroke(hot[i]); }
    if ((scan && sy < 1e8) || down) { g.fillStyle = `hsla(${hue},60%,96%,1)`; g.fill(dots); }
    g.globalCompositeOperation = 'source-over';
    this.composite(ctx, o.glow ?? 1, o.alpha ?? 1);
    return info;
  }
  composite(ctx, glow = 1, alpha = 1) {
    const { L, G1, G2 } = this;
    const g1 = G1.getContext('2d'), g2 = G2.getContext('2d');
    g1.clearRect(0, 0, G1.width, G1.height); g1.filter = 'blur(3px)'; g1.drawImage(L, 0, 0, G1.width, G1.height); g1.filter = 'none';
    g2.clearRect(0, 0, G2.width, G2.height); g2.filter = 'blur(4px)'; g2.drawImage(L, 0, 0, G2.width, G2.height); g2.filter = 'none';
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = 0.85 * glow * alpha; ctx.drawImage(G1, 0, 0, W, H);
    ctx.globalAlpha = 0.7 * glow * alpha; ctx.drawImage(G2, 0, 0, W, H);
    ctx.globalAlpha = alpha; ctx.drawImage(L, 0, 0);
    ctx.restore();
  }
}

function drawScanPlane(ctx, cam, y, o = {}) {
  const C = makeCamera(cam), P = C.project, t = new Float32Array(3);
  const hue = o.hue ?? 190, R = o.r ?? 0.95, a = o.alpha ?? 1;
  const pts = [];
  for (let i = 0; i <= 96; i++) { const th = i / 96 * TAU; P(Math.cos(th) * R, y, Math.sin(th) * R, t); pts.push([t[0], t[1]]); }
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.closePath();
  ctx.fillStyle = `hsla(${hue},90%,60%,${0.07 * a})`; ctx.fill();
  ctx.strokeStyle = `hsla(${hue},80%,85%,${0.75 * a})`; ctx.lineWidth = 2; ctx.stroke();
  ctx.beginPath();
  for (let i = 0; i < 72; i++) {
    const th = i / 72 * TAU + (o.rot || 0), r2 = R * (i % 6 ? 1.03 : 1.07);
    P(Math.cos(th) * R, y, Math.sin(th) * R, t); ctx.moveTo(t[0], t[1]);
    P(Math.cos(th) * r2, y, Math.sin(th) * r2, t); ctx.lineTo(t[0], t[1]);
  }
  ctx.strokeStyle = `hsla(${hue},80%,80%,${0.5 * a})`; ctx.lineWidth = 1.2; ctx.stroke();
  P(0, y, 0, t); const yy = t[1];
  const gr = ctx.createLinearGradient(0, yy - 80, 0, yy + 80);
  gr.addColorStop(0, `hsla(${hue},90%,60%,0)`); gr.addColorStop(0.5, `hsla(${hue},90%,70%,${0.10 * a})`); gr.addColorStop(1, `hsla(${hue},90%,60%,0)`);
  ctx.fillStyle = gr; ctx.fillRect(0, yy - 80, W, 160);
  const gl = ctx.createLinearGradient(0, 0, W, 0);
  gl.addColorStop(0, `hsla(${hue},90%,80%,0)`); gl.addColorStop(0.5, `hsla(${hue},90%,85%,${0.55 * a})`); gl.addColorStop(1, `hsla(${hue},90%,80%,0)`);
  ctx.fillStyle = gl; ctx.fillRect(0, yy - 1, W, 2);
  ctx.restore();
}

function drawPad(ctx, cam, o = {}) {
  const C = makeCamera(cam), P = C.project, t = new Float32Array(3);
  const hue = o.hue ?? 190, a = o.alpha ?? 1, rot = o.rot || 0, s = o.scale || 1;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const ring = (R, al, w = 1, dash = 0) => {
    ctx.beginPath();
    for (let i = 0; i <= 128; i++) { const th = i / 128 * TAU; P(Math.cos(th) * R * s, 0, Math.sin(th) * R * s, t); i ? ctx.lineTo(t[0], t[1]) : ctx.moveTo(t[0], t[1]); }
    ctx.setLineDash(dash ? [dash, dash * 1.6] : []);
    ctx.strokeStyle = `hsla(${hue},80%,70%,${al * a})`; ctx.lineWidth = w; ctx.stroke();
  };
  ring(1.05, 0.55, 1.8); ring(1.12, 0.3, 1.2, 8); ring(0.7, 0.18, 1.2); ring(1.45, 0.14, 1.2); ring(2.1, 0.07, 1.2);
  ctx.setLineDash([]);
  ctx.beginPath();
  for (let i = 0; i < 120; i++) {
    const th = i / 120 * TAU + rot, big = i % 10 === 0, r0 = 1.05 * s, r1 = (big ? 1.2 : 1.1) * s;
    P(Math.cos(th) * r0, 0, Math.sin(th) * r0, t); ctx.moveTo(t[0], t[1]);
    P(Math.cos(th) * r1, 0, Math.sin(th) * r1, t); ctx.lineTo(t[0], t[1]);
  }
  ctx.strokeStyle = `hsla(${hue},80%,78%,${0.5 * a})`; ctx.lineWidth = 1.2; ctx.stroke();
  for (let i = 0; i < 24; i++) {
    const th = i / 24 * TAU + rot * 0.25;
    ctx.beginPath();
    P(Math.cos(th) * 1.2 * s, 0, Math.sin(th) * 1.2 * s, t); ctx.moveTo(t[0], t[1]);
    P(Math.cos(th) * 2.4 * s, 0, Math.sin(th) * 2.4 * s, t); ctx.lineTo(t[0], t[1]);
    ctx.strokeStyle = `hsla(${hue},70%,60%,${0.08 * a})`; ctx.stroke();
  }
  ctx.restore();
}

// ===================================================================== model primitives (after mkmodel.mjs, rewritten)
// rounded rectangle path centred at (cx, cy), counter-clockwise
function rr(w, h, r, cx = 0, cy = 0, n = 5) {
  const pts = [], c = [[w / 2 - r, h / 2 - r, 0], [-w / 2 + r, h / 2 - r, 1], [-w / 2 + r, -h / 2 + r, 2], [w / 2 - r, -h / 2 + r, 3]];
  for (const [x, y, q] of c) for (let i = 0; i <= n; i++) { const a = (q + i / n) * Math.PI / 2; pts.push([cx + x + Math.cos(a) * r, cy + y + Math.sin(a) * r]); }
  return pts;
}
// a closed 2D path (x, y) extruded along z from z0 - d/2 to z0 + d/2 (slices >= 2), or a flat loop (slices 1)
function piece(id, pts, o = {}) {
  const d = o.depth ?? 0.05, z0 = o.z ?? 0, sl = o.slices ?? 2, n = pts.length, v = [], e = [], q = [];
  for (let k = 0; k < sl; k++) {
    const z = sl === 1 ? z0 : z0 - d / 2 + d * k / (sl - 1);
    for (const [x, y] of pts) v.push(x, y, z);
    for (let i = 0; i < n; i++) e.push(k * n + i, k * n + (i + 1) % n);
  }
  for (let k = 0; k < sl - 1; k++) for (let i = 0; i < n; i++) {
    if (i % (o.ribEvery || 1) === 0) e.push(k * n + i, (k + 1) * n + i);
    q.push(k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i);
  }
  return Object.assign({ id, v, e, q, explode: o.explode || [0, 0, 0] }, o.flags || {});
}
// add more loops / segments to a piece (same transform)
function addLoop(p, pts, z) { const b = p.v.length / 3; for (const [x, y] of pts) p.v.push(x, y, z); for (let i = 0; i < pts.length; i++) p.e.push(b + i, b + (i + 1) % pts.length); return p; }
function addSeg(p, a, b) { const k = p.v.length / 3; p.v.push(...a, ...b); p.e.push(k, k + 1); return p; }
// cylinder along x: rings in the y-z plane
function cylX(id, x0, x1, cy, cz, r, o = {}) {
  const n = o.n || 20, v = [], e = [], q = [], rings = o.rings || 2;
  for (let k = 0; k < rings; k++) {
    const x = x0 + (x1 - x0) * k / (rings - 1);
    for (let i = 0; i < n; i++) { const a = i / n * TAU; v.push(x, cy + Math.cos(a) * r, cz + Math.sin(a) * r); e.push(k * n + i, k * n + (i + 1) % n); }
  }
  for (let k = 0; k < rings - 1; k++) for (let i = 0; i < n; i++) {
    if (i % 2 === 0) e.push(k * n + i, (k + 1) * n + i);
    q.push(k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i);
  }
  if (o.spokes) for (const k of [0, rings - 1]) { const c = v.length / 3; v.push(x0 + (x1 - x0) * k / (rings - 1), cy, cz); for (let i = 0; i < n; i += n / o.spokes) e.push(c, k * n + i); }
  return Object.assign({ id, v, e, q, explode: o.explode || [0, 0, 0] }, o.flags || {});
}
// rotate a piece about y by th, then move it by (dx, dz)
function place(p, th, dx, dz) {
  const c = Math.cos(th), s = Math.sin(th);
  for (let i = 0; i < p.v.length; i += 3) { const x = p.v[i], z = p.v[i + 2]; p.v[i] = x * c + z * s + dx; p.v[i + 2] = -x * s + z * c + dz; }
  const ex = p.explode; p.explode = [ex[0] * c + ex[2] * s, ex[1], -ex[0] * s + ex[2] * c];
  if (p.face) p.face = p.face.map(([x, y, z]) => [x * c + z * s + dx, y, -x * s + z * c + dz]);
  return p;
}
function placeAnchor(a, th, dx, dz) { const c = Math.cos(th), s = Math.sin(th); return [a[0] * c + a[2] * s + dx, a[1], -a[0] * s + a[2] * c + dz]; }

// ---- the phone: body, screen, three notifications (pull out of the screen along z), app grid, camera, button
function phoneModel() {
  const parts = [];
  const body = piece('body', rr(0.75, 1.55, 0.12, 0, 0.775), { depth: 0.09, slices: 3, ribEvery: 2 });
  addSeg(body, [0.375, 1.02, 0.02], [0.375, 1.24, 0.02]);                         // side button line
  addSeg(body, [0.375, 1.02, -0.02], [0.375, 1.24, -0.02]);
  parts.push({ id: 'body', anchor: [0.3, 0.42, 0.046], pieces: [body] });
  const scr = piece('screen', rr(0.69, 1.47, 0.09, 0, 0.775), { slices: 1, z: 0.047 });
  addSeg(scr, [-0.3, 1.43, 0.047], [0.3, 1.43, 0.047]);                            // status bar
  addLoop(scr, rr(0.16, 0.035, 0.017, 0, 1.47, 3), 0.047);                         // the pill
  addSeg(scr, [-0.12, 0.07, 0.047], [0.12, 0.07, 0.047]);                          // home bar
  for (let i = 1; i < 6; i++) addSeg(scr, [-0.33, 0.04 + i * 0.245, 0.047], [0.33, 0.04 + i * 0.245, 0.047]);   // faint scanlines
  parts.push({ id: 'screen', anchor: [0, 0.6, 0.047], pieces: [scr] });
  const ny = [1.27, 1.09, 0.91];
  ny.forEach((y, i) => {
    const p = piece('n' + (i + 1), rr(0.6, 0.15, 0.035, 0, y), { depth: 0.014, z: 0.056, explode: [0.03 * (i - 1), 0.02, 0.2 + 0.13 * i], flags: { hot: true } });
    addLoop(p, rr(0.085, 0.085, 0.02, -0.22, y), 0.063);                            // app icon
    addSeg(p, [-0.14, y + 0.025, 0.063], [0.23, y + 0.025, 0.063]);                  // two text lines
    addSeg(p, [-0.14, y - 0.025, 0.063], [0.12, y - 0.025, 0.063]);
    parts.push({ id: 'n' + (i + 1), anchor: [0.3, y, 0.063], center: [0, y, 0.06], pieces: [p] });
  });
  const apps = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) apps.push(piece('app' + r + c, rr(0.12, 0.12, 0.03, -0.24 + c * 0.16, 0.62 - r * 0.18), { depth: 0.012, z: 0.054, explode: [0, 0, 0.05] }));
  parts.push({ id: 'apps', anchor: [0, 0.44, 0.06], pieces: apps });
  const cam = piece('camera', rr(0.24, 0.38, 0.07, -0.19, 1.3), { depth: 0.02, z: -0.055 });
  for (const yy of [1.39, 1.21]) { const ring = []; for (let i = 0; i < 16; i++) { const a = i / 16 * TAU; ring.push([-0.19 + Math.cos(a) * 0.055, yy + Math.sin(a) * 0.055]); } addLoop(cam, ring, -0.066); }
  parts.push({ id: 'camera', anchor: [-0.19, 1.3, -0.066], pieces: [cam] });
  return normalizeModel(prepModel({ name: 'PHONE', parts }), 2.0);
}

// ---- the book: a closed hardback, its front face carries the real cover (the single-colour exception, keep)
function bookModel() {
  const w = 0.666, h = 1.0, d = 0.07;
  const p = piece('book', rr(w, h, 0.008, 0, h / 2, 1), { depth: d, slices: 2 });
  for (let i = 1; i < 6; i++) addSeg(p, [w / 2 - 0.004, 0.02, -d / 2 + i * d / 6], [w / 2 - 0.004, h - 0.02, -d / 2 + i * d / 6]);   // page edges
  p.face = [[-w / 2, h, d / 2], [w / 2, h, d / 2], [w / 2, 0, d / 2], [-w / 2, 0, d / 2]];
  return normalizeModel(prepModel({ name: 'BOOK', parts: [{ id: 'book', anchor: [w / 2, h * 0.62, d / 2], pieces: [p] }] }), 1.9);
}

// ---- the basics: four icons on one pad, 90 degrees apart (sleep, move, people, a challenge)
function basicsModel() {
  const R = 0.78, parts = [];
  const S = 1.45;                                   // icons big against the ring: the front one carries the frame
  const add = (id, pieces, anchor, k) => {
    const th = k * Math.PI / 2;
    pieces.forEach(p => { for (let i = 0; i < p.v.length; i++) p.v[i] *= S; p.explode = p.explode.map(x => x * S); });
    anchor = anchor.map(x => x * S);
    pieces.forEach(p => place(p, th, Math.sin(th) * R, Math.cos(th) * R));
    parts.push({ id, anchor: placeAnchor(anchor, th, Math.sin(th) * R, Math.cos(th) * R), pieces });
  };
  // moon: outer arc 60 -> 300 deg (r .24), inner arc back through the left (centre .12, r .2078)
  const moon = [], r = 0.27, cy = 0.29;
  for (let i = 0; i <= 24; i++) { const a = (60 + 240 * i / 24) * Math.PI / 180; moon.push([Math.cos(a) * r, cy + Math.sin(a) * r]); }
  const c2 = r * 0.5, r2 = Math.hypot(r * 0.5 - c2, r * Math.sin(Math.PI / 3));
  for (let i = 1; i < 24; i++) { const a = (270 - 180 * i / 24) * Math.PI / 180; moon.push([c2 + Math.cos(a) * r2, cy + Math.sin(a) * r2]); }
  add('sleep', [piece('moon', moon, { depth: 0.09, slices: 3, ribEvery: 2, explode: [0, 0.06, 0] })], [0, 0.29, 0.05], 0);
  // dumbbell: bar + two plates + two outer plates (cylinders along x)
  add('move', [cylX('bar', -0.27, 0.27, 0.15, 0, 0.028, { n: 12 }), cylX('plateL', -0.24, -0.17, 0.15, 0, 0.15, { n: 24, spokes: 6 }),
    cylX('plateR', 0.17, 0.24, 0.15, 0, 0.15, { n: 24, spokes: 6 }), cylX('capL', -0.31, -0.24, 0.15, 0, 0.1, { n: 20 }),
    cylX('capR', 0.24, 0.31, 0.15, 0, 0.1, { n: 20 })], [0, 0.15, 0.03], 1);
  // heart (parametric)
  const heart = [];
  for (let i = 0; i < 48; i++) { const t = i / 48 * TAU; heart.push([0.0165 * 16 * Math.pow(Math.sin(t), 3), 0.285 + 0.0165 * (13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t))]); }
  add('people', [piece('heart', heart, { depth: 0.09, slices: 3, ribEvery: 3 })], [0, 0.3, 0.05], 2);
  // a peak with a flag (a hard task you can climb)
  const peak = [[-0.32, 0], [-0.1, 0.34], [-0.02, 0.25], [0.09, 0.46], [0.32, 0]];
  const flag = piece('flag', [[0.09, 0.62], [0.09, 0.53], [0.23, 0.575]], { depth: 0.02 });
  addSeg(flag, [0.09, 0.46, 0], [0.09, 0.62, 0]);
  add('challenge', [piece('peak', peak, { depth: 0.1, slices: 3 }), flag], [0.09, 0.36, 0.05], 3);
  return normalizeModel(prepModel({ name: 'BASICS', parts }), 2.3);
}
const MODELS = { phone: phoneModel, book: bookModel, basics: basicsModel };

// ===================================================================== HUD layer (hud.js)
function theme(hue = 188, accent = 38) {
  return {
    hue, accentHue: accent,
    line: a => `hsla(${hue},100%,72%,${a})`, hi: a => `hsla(${hue},60%,93%,${a})`, dim: a => `hsla(${hue},70%,52%,${a})`,
    acc: a => `hsla(${accent},100%,64%,${a})`,
    bg0: `hsl(${hue + 12},70%,2.4%)`, bg1: `hsl(${hue + 6},65%,7%)`,
  };
}
function background(ctx, T, o = {}) {
  ctx.fillStyle = T.bg0; ctx.fillRect(0, 0, W, H);
  const cx = o.cx ?? W * 0.5, cy = o.cy ?? H * 0.45;
  const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, H * 0.55);
  g.addColorStop(0, T.bg1); g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  const step = 48, ox = (((o.px || 0) % step) + step) % step, oy = (((o.py || 0) % step) + step) % step;
  ctx.fillStyle = T.dim(0.16);
  for (let y = -step + oy; y < H + step; y += step) for (let x = -step + ox; x < W + step; x += step) {
    const d = Math.hypot(x - cx, (y - cy) * 0.7) / (W * 0.75);
    if (d > 1) continue;
    const s = (1 - d) * 1.8 + 0.5;
    ctx.fillRect(x - s / 2, y - s / 2, s, s);
  }
}
function vignette(ctx, k = 0.55) {
  const g = ctx.createRadialGradient(W / 2, H / 2, H * 0.25, W / 2, H / 2, H * 0.62);
  g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, `rgba(0,0,0,${k})`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
}
function corners(ctx, x0, y0, x1, y1, L) {
  ctx.beginPath();
  ctx.moveTo(x0, y0 + L); ctx.lineTo(x0, y0); ctx.lineTo(x0 + L, y0);
  ctx.moveTo(x1 - L, y0); ctx.lineTo(x1, y0); ctx.lineTo(x1, y0 + L);
  ctx.moveTo(x1, y1 - L); ctx.lineTo(x1, y1); ctx.lineTo(x1 - L, y1);
  ctx.moveTo(x0 + L, y1); ctx.lineTo(x0, y1); ctx.lineTo(x0, y1 - L);
  ctx.stroke();
}
function plate(ctx, T, x, y, w, h, a = 1, o = {}) {
  if (a <= 0 || w <= 0 || h <= 0) return;
  ctx.save(); ctx.globalCompositeOperation = 'source-over';
  ctx.fillStyle = `rgba(1,8,12,${(o.op ?? 0.74) * a})`; ctx.fillRect(x, y, w, h);
  ctx.globalCompositeOperation = 'lighter';
  ctx.strokeStyle = T.line(0.28 * a); ctx.lineWidth = 1.2; ctx.strokeRect(x + .5, y + .5, w - 1, h - 1);
  ctx.strokeStyle = T.line(0.7 * a); ctx.lineWidth = 1.8; corners(ctx, x, y, x + w, y + h, 14);
  ctx.restore();
}
// viewfinder: corner brackets, side rulers (foreground parallax), subject // mode top left, live status top right.
// Text is 48 px (the floor) and stays under the 120 px top band; the rulers stop above the bottom UI band.
function chrome(ctx, T, o = {}) {
  const a = o.alpha ?? 1, m = 40, L = 60, px = o.px || 0;
  ctx.save(); ctx.globalCompositeOperation = o.over ? 'source-over' : 'lighter';
  ctx.strokeStyle = T.line(0.6 * a); ctx.lineWidth = 2;
  corners(ctx, m, m + 90, W - m, H - m - 160, L);
  ctx.strokeStyle = T.dim(0.5 * a); ctx.lineWidth = 1.3;
  ctx.beginPath();
  const off = ((px * 1.4) % 24 + 24) % 24;
  for (let y = 260 + off; y < H - 300; y += 24) {
    const big = Math.round((y - off) / 24) % 5 === 0;
    ctx.moveTo(m + 10, y); ctx.lineTo(m + 10 + (big ? 18 : 9), y);
    ctx.moveTo(W - m - 10, y); ctx.lineTo(W - m - 10 - (big ? 18 : 9), y);
  }
  ctx.stroke();
  ctx.font = `500 48px ${FONT.mono}`; ctx.textBaseline = 'alphabetic';
  if (o.shadow) { ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = 14; }
  ctx.fillStyle = T.line(0.9 * a);
  if (o.tl) { ctx.textAlign = 'left'; ctx.fillText(o.tl, m + 30, 196); }
  if (o.tr) { ctx.textAlign = 'right'; ctx.fillStyle = T.hi(0.95 * a); ctx.fillText(o.tr, W - 110, 196); }
  ctx.restore();
}
// target box: k 0 = 1.9x and rotated 45 deg, k 1 = locked; flash = the white 3-frame flash on the lock
function targetBox(ctx, T, bb, k, o = {}) {
  if (!bb || k <= 0) return;
  const pad = o.pad ?? 30;
  let [x0, y0, x1, y1] = bb; x0 -= pad; y0 -= pad; x1 += pad; y1 += pad;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, e = eo(k);
  const s = lerp(1.9, 1, e), rot = lerp(Math.PI / 4, 0, e);
  const hw = (x1 - x0) / 2 * s, hh = (y1 - y0) / 2 * s, a = (o.alpha ?? 1) * clamp(k * 4);
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(rot); ctx.globalCompositeOperation = 'lighter';
  const L = Math.min(hw, hh) * 0.38 + 10;
  ctx.strokeStyle = o.flash ? T.hi(a) : T.line(0.9 * a); ctx.lineWidth = o.flash ? 4 : 2.6;
  corners(ctx, -hw, -hh, hw, hh, L);
  ctx.lineWidth = 1.4; ctx.strokeStyle = T.line(0.5 * a);
  ctx.beginPath();
  ctx.moveTo(-14, 0); ctx.lineTo(14, 0); ctx.moveTo(0, -14); ctx.lineTo(0, 14);
  ctx.moveTo(-hw, 0); ctx.lineTo(-hw + 14, 0); ctx.moveTo(hw, 0); ctx.lineTo(hw - 14, 0);
  ctx.moveTo(0, -hh); ctx.lineTo(0, -hh + 14); ctx.moveTo(0, hh); ctx.lineTo(0, hh - 14);
  ctx.stroke(); ctx.restore();
  if (o.tag && e > 0.8) {                      // the lock tag: a filled hue chip, dark 48 px text
    const ta = a * clamp((e - 0.8) * 5);
    ctx.save(); ctx.font = `700 48px ${FONT.ui}`; ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
    const w = ctx.measureText(o.tag).width + 28;
    let tx = clamp(cx - hw, 70, W - 100 - w), ty = cy - hh - 12;
    if (ty - 60 < 230) ty = cy + hh + 72;       // no room above: under the box
    ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = o.flash ? T.hi(0.95 * ta) : T.line(0.92 * ta);
    ctx.fillRect(tx, ty - 58, w, 62);
    ctx.globalCompositeOperation = 'source-over'; ctx.fillStyle = T.bg0; ctx.globalAlpha = ta;
    ctx.fillText(o.tag, tx + 14, ty - 10);
    ctx.restore();
  }
}
function leader(ctx, T, from, elbow, to, prog, o = {}) {
  if (prog <= 0) return;
  const a = o.alpha ?? 1;
  const d1 = Math.hypot(elbow[0] - from[0], elbow[1] - from[1]), d2 = Math.hypot(to[0] - elbow[0], to[1] - elbow[1]);
  let L = (d1 + d2) * clamp(prog);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  ctx.strokeStyle = T.line(0.85 * a); ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(from[0], from[1]);
  if (L <= d1) ctx.lineTo(lerp(from[0], elbow[0], L / d1), lerp(from[1], elbow[1], L / d1));
  else { ctx.lineTo(elbow[0], elbow[1]); L -= d1; ctx.lineTo(lerp(elbow[0], to[0], L / d2), lerp(elbow[1], to[1], L / d2)); }
  ctx.stroke();
  const ra = clamp(prog * 5);
  ctx.beginPath(); ctx.arc(from[0], from[1], 12 * ra, 0, TAU); ctx.stroke();
  ctx.fillStyle = T.hi(a); ctx.beginPath(); ctx.arc(from[0], from[1], 4, 0, TAU); ctx.fill();
  if (o.pulse) { ctx.strokeStyle = T.line(a * (1 - o.pulse)); ctx.beginPath(); ctx.arc(from[0], from[1], 12 + 34 * o.pulse, 0, TAU); ctx.stroke(); }
  ctx.restore();
}
// rolling text: characters lock right to left; garbage glyphs from the same script (Cyrillic for Cyrillic)
const GLY_D = '0123456789', GLY_A = 'ABCDEFGHJKLMNPRSTUVWXYZ#%/<>=', GLY_C = 'БГДЖЗИЙЛПФЦЧШЩЪЫЭЮЯ#%/<>=';
function rollText(str, k, frame, seed = 0) {
  if (k >= 1) return str;
  const n = str.length; let out = '';
  for (let i = 0; i < n; i++) {
    const ch = str[i], order = (n - 1 - i) / Math.max(1, n), lockAt = 0.25 + order * 0.7;
    if (k >= lockAt || ' .,·:/'.includes(ch)) { out += ch; continue; }
    if (k <= 0) { out += ' '; continue; }
    const set = /\d/.test(ch) ? GLY_D : /[Ѐ-ӿ]/.test(ch) ? GLY_C : GLY_A;
    out += set[Math.floor(hash(frame * 13.7 + i * 7.1 + seed) * set.length)];
  }
  return out;
}
function monoText(ctx, s, x, y, adv) {   // fixed advance so rolls never jitter; '.' drawn as a square dot
  let cx = x;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i], w = ctx.measureText(ch).width, narrow = '., :'.includes(ch), a = narrow ? w * 1.1 : adv;
    if (ch === '.') { const d = Math.max(4, ctx.measureText('0').width * 0.13); ctx.fillRect(cx + (a - d) / 2, y - d, d, d); }
    else ctx.fillText(ch, cx + (a - w) / 2, y);
    cx += a;
  }
  return cx - x;
}
function fitFont(ctx, text, weight, size, family, maxW, minSize = 48) {
  let s = size; ctx.font = `${weight} ${s}px ${family}`;
  while (ctx.measureText(text).width > maxW && s > minSize) { s -= 1; ctx.font = `${weight} ${s}px ${family}`; }
  return s;
}
function wrap(ctx, text, maxW) {
  const words = text.split(' '), lines = []; let cur = '';
  for (const w of words) { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; }
  if (cur) lines.push(cur);
  return lines;
}
// spec card: index + label (rolls in), big value (rolls from glyphs, turns accent on the lock), progress bar, detail
function specCard(ctx, T, x, y, c, st, o = {}) {
  const w = o.w ?? 820, a = o.alpha ?? 1, big = c.big ?? 150;
  if (st.reveal <= 0) return 0;
  const r = eo(st.reveal);
  ctx.save(); ctx.font = `500 48px ${FONT.ui}`;
  const dl = c.detail ? wrap(ctx, c.detail, w).length : 0; ctx.restore();
  ctx.save(); ctx.letterSpacing = '4px';
  const vs = fitFont(ctx, String(c.value), 300, big, FONT.ui, w - (c.unit ? 150 : 20), 48); ctx.restore();
  const hh = 84 + vs * 0.95 + 18 + (dl ? 18 + dl * 58 : 0) + 14;
  plate(ctx, T, x - 30, y - 30, (w + 60) * r, hh + 30, a * clamp(st.reveal * 2));
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  ctx.strokeStyle = T.line(0.9 * a); ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + w * r, y); ctx.stroke();
  ctx.fillStyle = T.line(0.9 * a); ctx.fillRect(x, y - 4, 44 * r, 8);
  ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
  ctx.font = `500 48px ${FONT.mono}`; ctx.fillStyle = T.dim(0.95 * a * r);
  ctx.fillText(c.index || '', x, y + 70);
  const lab = (c.label || '').toUpperCase();
  ctx.letterSpacing = '3px';
  fitFont(ctx, lab, 600, 52, FONT.ui, w - 90, 48);
  ctx.fillStyle = T.hi(0.95 * a * clamp(r * 2 - 0.6));
  ctx.fillText(rollText(lab, clamp(st.reveal * 1.6 - 0.2), st.frame, 3), x + (c.index ? 86 : 0), y + 70);
  ctx.letterSpacing = '0px';
  let h = 84;
  if (st.roll > 0) {
    const val = String(c.value), unit = c.unit || '', locked = st.roll >= 1;
    ctx.font = `300 ${vs}px ${FONT.ui}`; ctx.letterSpacing = '4px';
    const adv = ctx.measureText('Ж').width * 1.0;
    ctx.fillStyle = locked ? (st.flash ? T.hi(a) : T.acc(a)) : T.line(0.85 * a);
    const s = rollText(val, st.roll, st.frame, 11);
    const vw = /^[\d.,\s]+$/.test(val) ? monoText(ctx, s, x - 4, y + h + vs * 0.8, ctx.measureText('0').width * 1.02) : (ctx.fillText(s, x - 4, y + h + vs * 0.8), ctx.measureText(val).width);
    ctx.letterSpacing = '0px';
    if (unit) { ctx.font = `500 ${Math.max(48, Math.round(vs * 0.34))}px ${FONT.ui}`; ctx.fillStyle = locked ? T.acc(0.9 * a) : T.line(0.6 * a); ctx.fillText(unit, x + vw + 14, y + h + vs * 0.8); }
    h += vs * 0.95;
    ctx.fillStyle = T.dim(0.35 * a); ctx.fillRect(x, y + h + 10, w, 3);
    ctx.fillStyle = locked ? T.acc(0.9 * a) : T.line(0.9 * a); ctx.fillRect(x, y + h + 10, w * clamp(st.roll), 3);
    h += 18;
  }
  if (c.detail && st.detail > 0) {
    ctx.font = `500 48px ${FONT.ui}`; ctx.fillStyle = T.line(0.85 * a * clamp(st.detail * 2));
    wrap(ctx, c.detail, w).forEach((ln, i) => ctx.fillText(rollText(ln, clamp(st.detail * 1.5 - i * 0.2), st.frame, 21 + i), x, y + h + 62 + i * 58));
  }
  ctx.restore();
  return hh;
}
// rail chip: label + a drawn toggle (on = accent knob right, off = accent ring left); stays to the end
function chip(ctx, T, x, y, c, a = 1, o = {}) {
  if (a <= 0) return;
  const w = o.w ?? 440, h = 84, tw = 62, th = 34;
  plate(ctx, T, x, y, w, h, a);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  ctx.fillStyle = T.line(0.9 * a); ctx.fillRect(x, y - 2, 18, 4);
  ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left'; ctx.letterSpacing = '0px';
  ctx.font = `600 48px ${FONT.ui}`;
  if (ctx.measureText(c.label.toUpperCase()).width > w - tw - 52) ctx.font = `500 48px ${FONT.ui}`;
  ctx.fillStyle = T.hi(0.95 * a); ctx.fillText(c.label.toUpperCase(), x + 16, y + h / 2 + 17);
  const tx = x + w - tw - 14, ty = y + (h - th) / 2, on = !!c.on;
  ctx.lineWidth = 2.4; ctx.strokeStyle = T.acc(0.95 * a);
  ctx.beginPath(); ctx.roundRect(tx, ty, tw, th, th / 2); ctx.stroke();
  if (on) { ctx.fillStyle = T.acc(0.35 * a); ctx.fill(); }
  ctx.beginPath(); ctx.arc(on ? tx + tw - th / 2 : tx + th / 2, ty + th / 2, th / 2 - 6, 0, TAU);
  if (on) { ctx.fillStyle = T.acc(a); ctx.fill(); } else { ctx.stroke(); }
  ctx.restore();
}
function marker(ctx, T, p, label, a = 1, pulse = 0, dir = 1, o = {}) {
  if (!p || a <= 0) return;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const r = 20;
  ctx.strokeStyle = T.hi(0.95 * a); ctx.lineWidth = 2.4;
  ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, TAU); ctx.stroke();
  ctx.lineWidth = 1.6; ctx.beginPath();
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { ctx.moveTo(p[0] + dx * (r - 7), p[1] + dy * (r - 7)); ctx.lineTo(p[0] + dx * (r + 7), p[1] + dy * (r + 7)); }
  ctx.stroke();
  ctx.fillStyle = T.hi(a); ctx.beginPath(); ctx.arc(p[0], p[1], 5, 0, TAU); ctx.fill();
  if (pulse > 0) { ctx.strokeStyle = T.line(0.8 * a * (1 - pulse)); ctx.beginPath(); ctx.arc(p[0], p[1], r + 44 * pulse, 0, TAU); ctx.stroke(); }
  ctx.font = `600 48px ${FONT.ui}`; ctx.textBaseline = 'alphabetic'; ctx.letterSpacing = '1px';
  const txt = rollText(label, o.roll ?? 1, o.frame || 0, 5);
  const tw = ctx.measureText(label).width + 28, gap = (o.gap ?? 34);
  let bx = dir > 0 ? p[0] + r + gap : p[0] - r - gap - tw; bx = clamp(bx, 70, W - 100 - tw);
  const by = p[1] + (o.dy || 0);
  ctx.strokeStyle = T.hi(0.9 * a); ctx.beginPath(); ctx.moveTo(p[0] + dir * (r + 7), p[1]); ctx.lineTo(dir > 0 ? bx : bx + tw, by); ctx.stroke();
  ctx.globalCompositeOperation = 'source-over';
  ctx.fillStyle = `rgba(1,8,12,${0.9 * a})`; ctx.fillRect(bx, by - 36, tw, 72);
  ctx.globalCompositeOperation = 'lighter';
  ctx.strokeStyle = (o.acc ? T.acc : T.line)(0.95 * a); ctx.lineWidth = 1.6; ctx.strokeRect(bx, by - 36, tw, 72);
  ctx.fillStyle = (o.acc ? T.acc : T.hi)(a); ctx.textAlign = 'left'; ctx.fillText(txt, bx + 14, by + 17);
  ctx.restore();
}
function beam(ctx, T, project, a, t, o = {}) {
  if (a <= 0) return;
  const r0 = o.r0 ?? 1.05, r1 = o.r1 ?? 0.9, y1 = o.y1 ?? 1.25, p = new Float32Array(3), bot = [], top = [];
  for (let i = 0; i < 96; i++) {
    const th = i / 96 * TAU;
    project(Math.cos(th) * r0, 0, Math.sin(th) * r0, p); bot.push([p[0], p[1]]);
    project(Math.cos(th) * r1, y1, Math.sin(th) * r1, p); top.push([p[0], p[1]]);
  }
  const ext = arr => { let l = 0, r = 0; arr.forEach((q, i) => { if (q[0] < arr[l][0]) l = i; if (q[0] > arr[r][0]) r = i; }); return [l, r]; };
  const [bl, br] = ext(bot), [tl, tr] = ext(top);
  const L0 = bot[bl][0], R0 = bot[br][0], L1 = top[tl][0], R1 = top[tr][0];
  const yb = Math.max(...bot.map(q => q[1])), yt = Math.min(...top.map(q => q[1]));
  project(0, 0, 0, p); const ym = p[1]; project(0, y1, 0, p); const yT = p[1];
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const g = ctx.createLinearGradient(0, yb, 0, yt);
  g.addColorStop(0, T.line(0.10 * a)); g.addColorStop(0.45, T.line(0.04 * a)); g.addColorStop(1, T.line(0));
  ctx.fillStyle = g; ctx.beginPath();
  const poly = arr => { arr.forEach((q, i) => i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1])); ctx.closePath(); };
  const cw = arr => { let s = 0; for (let i = 0; i < arr.length; i++) { const p0 = arr[i], p1 = arr[(i + 1) % arr.length]; s += p0[0] * p1[1] - p1[0] * p0[1]; } return s > 0 ? arr : arr.slice().reverse(); };
  poly(cw(bot)); poly(cw(top)); poly(cw([[L0, bot[bl][1]], [L1, top[tl][1]], [R1, top[tr][1]], [R0, bot[br][1]]]));
  ctx.fill('nonzero');
  ctx.lineWidth = 1.2;
  for (let i = 0; i < 26; i++) {
    const u = (i + 0.5) / 26, w = 0.5 + 0.5 * Math.sin(i * 12.9898 + t * 1.3);
    ctx.strokeStyle = T.line(0.05 * a * w);
    ctx.beginPath(); ctx.moveTo(L0 + (R0 - L0) * u, ym + (yb - ym) * Math.sin(u * Math.PI)); ctx.lineTo(L1 + (R1 - L1) * u, yT); ctx.stroke();
  }
  for (let i = 0; i < 70; i++) {
    const h1 = hash(i * 3.7), h2 = hash(i * 9.1), h3 = hash(i * 1.3), life = (t * (0.12 + 0.1 * h3) + h1) % 1;
    const th = h2 * TAU, rr_ = r0 * (0.3 + 0.7 * hash(i * 5.3)) * (1 - life * 0.15);
    project(Math.cos(th) * rr_, life * y1, Math.sin(th) * rr_, p);
    ctx.fillStyle = T.hi(Math.sin(life * Math.PI) * a * 0.8); ctx.fillRect(p[0] - 1.5, p[1] - 1.5, 3, 3);
  }
  ctx.restore();
}
// subtitles as HUD: a dark plate, two diagonal brackets, voiceprint bars moving with the speech; Exo 2 Medium 70 px
// (cap height 0.69 em = 48 px: the floor measured cap-to-baseline), at most two lines, the plate centred between x 100
// and 980 with its bottom at y 1690 (220 px clear of the Instagram UI). The speaker's words never roll: readable on the frame.
function subtitle(ctx, T, text, a, o = {}) {
  if (!text || a <= 0) return;
  ctx.save();
  const yb = o.y ?? 1660, maxW = o.maxW ?? 770, size = o.size ?? 70, lh = Math.round(size * 1.18);
  ctx.font = `500 ${size}px ${FONT.ui}`;
  const lines = wrap(ctx, text, maxW);
  const tw = Math.max(...lines.map(l => ctx.measureText(l).width));
  const pw = tw + 110, px0 = 540 - pw / 2, x = px0 + 74, h = lines.length * lh;
  const py0 = yb - h - 22, ph = h + 40;
  ctx.fillStyle = `rgba(1,8,12,${0.66 * a})`; ctx.fillRect(px0, py0, pw, ph);
  ctx.globalCompositeOperation = 'lighter';
  ctx.strokeStyle = T.line(0.6 * a); ctx.lineWidth = 1.8;
  ctx.beginPath();
  ctx.moveTo(px0, py0 + 16); ctx.lineTo(px0, py0); ctx.lineTo(px0 + 16, py0);
  ctx.moveTo(px0 + pw - 16, py0 + ph); ctx.lineTo(px0 + pw, py0 + ph); ctx.lineTo(px0 + pw, py0 + ph - 16);
  ctx.stroke();
  ctx.fillStyle = T.line(0.9 * a);
  const amp = o.speaking ? 1 : 0.25;
  for (let i = 0; i < 4; i++) { const hh = 8 + 20 * amp * Math.abs(Math.sin((o.t || 0) * 9 + i * 1.7)); ctx.fillRect(x - 56 + i * 9, py0 + ph / 2 - hh / 2, 4, hh); }
  ctx.globalCompositeOperation = 'source-over';
  ctx.fillStyle = T.hi(0.97 * a); ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  lines.forEach((l, i) => ctx.fillText(l, x, py0 + 20 + (i + 1) * lh - lh * 0.22));
  ctx.restore();
}
function glitch(ctx, amt, seed) {
  if (amt <= 0) return;
  const src = ctx.canvas;
  const tmp = glitch.tmp || (glitch.tmp = Object.assign(document.createElement('canvas'), { width: W, height: H }));
  const g = tmp.getContext('2d'); g.clearRect(0, 0, W, H); g.drawImage(src, 0, 0);
  for (let i = 0; i < 11; i++) {
    const y = Math.floor(hash(seed + i * 3.1) * H), h = 8 + Math.floor(hash(seed + i * 5.7) * 90), dx = (hash(seed + i * 9.3) - 0.5) * 140 * amt;
    ctx.drawImage(tmp, 0, y, W, h, dx, y, W, h);
  }
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.35 * amt; ctx.drawImage(tmp, 10 * amt, 0); ctx.restore();
}

// ===================================================================== the scene renderer (data from hologramhud.py)
const cache = {};
const model = id => cache[id] || (cache[id] = MODELS[id]());
const holo = () => cache.__holo || (cache.__holo = new Holo());
// keys: [[t, value or {k: v}], ...] -> value at t (cubic in-out between keys)
function keyed(keys, t, def) {
  if (!keys || !keys.length) return def;
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, a] = keys[i], [t1, b] = keys[i + 1];
    if (t < t1) {
      const u = eio((t - t0) / Math.max(1e-6, t1 - t0));
      if (typeof a === 'number') return lerp(a, b, u);
      const o = {}; for (const k in b) o[k] = Array.isArray(b[k]) ? b[k].map((x, j) => lerp((a[k] ?? b[k])[j], x, u)) : lerp(a[k] ?? b[k], b[k], u);
      for (const k in a) if (!(k in o)) o[k] = a[k];
      return o;
    }
  }
  return keys[keys.length - 1][1];
}
const frameOf = t => Math.floor(t * FPS + 1e-6);
const between = (t, a, b) => t >= a && t < b;

function drawObj(ctx, T, sc, ob, cam, t) {
  const m = model(ob.model);
  const o = { hue: T.hue, explode: {}, gain: ob.gain ?? 1 };
  if (ob.scan) {                                  // scan growth: the model grows up to the plane
    const u = (t - ob.scan[0]) / (ob.scan[1] - ob.scan[0]);
    if (u < 0) return null;
    if (u < 1) o.scan = { y: lerp(-0.03, m.ymax + 0.04, eio(u)), band: 0.07 };
  }
  if (ob.erase) {                                 // scan-erase top-down
    const u = (t - ob.erase[0]) / (ob.erase[1] - ob.erase[0]);
    if (u >= 1) return null;
    if (u > 0) o.scanDown = { y: lerp(m.ymax + 0.04, -0.03, eio(u)) };
  }
  for (const ex of ob.explode || []) {           // {id, t0, t1, to} chains: open over a beat, close fast
    const u = clamp((t - ex.t0) / (ex.t1 - ex.t0));
    if (t >= ex.t0) o.explode[ex.id] = lerp(ex.from ?? 0, ex.to, eio(u));
  }
  o.spin = keyed(ob.spin, t, 0);
  if (ob.dims) { o.dimParts = {}; for (const d of ob.dims) if (t >= d.t) o.dimParts[d.id] = lerp(1, d.to, clamp((t - d.t) / (d.dur || 0.3))); }
  if (ob.focus) for (const f of ob.focus) if (between(t, f.t0, f.t1)) { o.focus = f.parts; o.dim = f.dim ?? 0.3; }
  if (ob.solid) { const u = clamp((t - ob.solid[0]) / (ob.solid[1] - ob.solid[0])); if (u > 0) { o.solid = u; o.lineWidth = 1.8 * lerp(1.5, 1.12, u); o.scanOffset = frameOf(t); o.wave = { y: lerp(0, m.ymax * 1.2, u), w: 0.07 }; } }
  if (ob.flash) { o.flash = {}; for (const f of ob.flash) if (between(t, f.t, f.t + 3 / FPS)) o.flash[f.id] = 1; }
  if (ob.alpha) o.alpha = keyed(ob.alpha, t, 1);
  o.boxExploded = ob.boxExploded;
  const info = holo().draw(ctx, m, cam, o);
  if (o.scan) drawScanPlane(ctx, cam, o.scan.y, { hue: T.hue, r: ob.planeR ?? 0.95, rot: t * 0.3 });
  if (o.scanDown) drawScanPlane(ctx, cam, o.scanDown.y, { hue: T.hue, r: ob.planeR ?? 0.95, rot: -t * 0.3, alpha: 0.8 });
  if (ob.cover && info.faces && info.faces.book) {            // the real cover on the front face, its own colour
    const ca = ob.cover.t ? clamp((t - ob.cover.t) / 0.25) : 1;
    const img = document.getElementById(ob.cover.img);
    if (ca > 0 && img && img.complete && img.naturalWidth) {
      const [tl, trr, , bl] = info.faces.book, iw = img.naturalWidth, ih = img.naturalHeight;
      ctx.save(); ctx.globalAlpha = 0.92 * ca;
      ctx.setTransform((trr[0] - tl[0]) / iw, (trr[1] - tl[1]) / iw, (bl[0] - tl[0]) / ih, (bl[1] - tl[1]) / ih, tl[0], tl[1]);
      ctx.drawImage(img, 0, 0); ctx.restore();
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.18 * ca;   // interlace on the cover
      ctx.fillStyle = T.line(1);
      const yb = Math.min(tl[1], trr[1]), ye = Math.max(bl[1], info.faces.book[2][1]);
      for (let y = yb + (frameOf(t) % 4); y < ye; y += 4) ctx.fillRect(Math.min(tl[0], bl[0]), y, Math.abs(trr[0] - tl[0]) + 4, 1);
      ctx.restore();
    }
  }
  return info;
}

function drawHolo(ctx, T, sc, t) {
  const f = frameOf(t), lt = t - sc.t0;
  const cam0 = keyed(sc.cam, t, {});
  const cam = { target: [cam0.tx ?? 0, cam0.ty ?? 0.6, cam0.tz ?? 0], yaw: cam0.yaw ?? 0.5, pitch: cam0.pitch ?? 0.2, dist: cam0.dist ?? 3, fov: cam0.fov ?? 0.75, cx: cam0.cx ?? 540, cy: cam0.cy ?? 860 };
  background(ctx, T, { px: -cam.yaw * 220, py: cam.pitch * 160, cy: cam.cy });
  drawPad(ctx, cam, { hue: T.hue, rot: t * 0.12 + keyed(sc.padSpin, t, 0), alpha: sc.padAlpha ?? 1, scale: sc.padScale || 1 });
  const infos = [];
  for (const ob of sc.objs || []) infos.push(drawObj(ctx, T, sc, ob, cam, t));
  for (const b of sc.beam ? [sc.beam] : []) { const u = clamp((t - b[0]) / 0.5); if (u > 0) beam(ctx, T, makeCamera(cam).project, u, t, { y1: b[2] ?? 1.3 }); }
  vignette(ctx, 0.5);
  // target locks: oversized and rotated, snap in 0.22 s, a 3-frame white flash on the lock
  for (const L of sc.locks || []) {
    if (!between(t, L.t, L.t1)) continue;
    const info = infos[L.obj || 0]; if (!info) continue;
    let bb = null;
    for (const p of L.parts) { const b = info.bbox[p]; if (!b) continue; bb = bb ? [Math.min(bb[0], b[0]), Math.min(bb[1], b[1]), Math.max(bb[2], b[2]), Math.max(bb[3], b[3])] : b.slice(); }
    const k = clamp((t - L.t) / 0.22), out = L.t1 - t < 0.12 ? (L.t1 - t) / 0.12 : 1;
    targetBox(ctx, T, bb, k, { tag: L.tag, flash: between(t, L.t + 0.22, L.t + 0.22 + 3 / FPS), alpha: out, pad: L.pad });
  }
  // leaders + cards
  for (const c of sc.cards || []) {
    if (!between(t, c.t, c.t1)) continue;
    const ct = t - c.t, dock = c.dock != null ? clamp((t - c.dock) / 0.35) : 0, a = 1 - dock;
    if (c.from) {
      const info = infos[c.from.obj || 0], an = info && info.anchor[c.from.part];
      if (an) {
        const to = [c.x - 30, c.y - 30 + 2], el = [lerp(an[0], to[0], 0.35), to[1]];
        leader(ctx, T, an, el, to, clamp(ct / 0.5), { alpha: a, pulse: clamp((ct - 0.5) / 0.6) % 1 });
      }
    }
    const roll = c.roll ? clamp((t - c.roll[0]) / (c.roll[1] - c.roll[0])) : 1;
    specCard(ctx, T, c.x ?? 130, c.y, c, { reveal: clamp(ct / 0.35), roll, detail: c.detail ? clamp((t - (c.roll ? c.roll[1] : c.t)) / 0.4) : 0, frame: f,
      flash: c.roll && between(t, c.roll[1], c.roll[1] + 1 / FPS) }, { alpha: a, w: c.w });
  }
  // markers on parts
  for (const mk_ of sc.markers || []) {
    if (!between(t, mk_.t, mk_.t1)) continue;
    const info = infos[mk_.obj || 0], an = info && info.anchor[mk_.part];
    const mt = t - mk_.t, out = mk_.t1 - t < 0.15 ? (mk_.t1 - t) / 0.15 : 1;
    marker(ctx, T, an, mk_.label, clamp(mt / 0.12) * out, clamp(mt / 0.6), mk_.dir || 1, { roll: clamp(mt / 0.35), frame: f, dy: mk_.dy, acc: mk_.acc && mt > 0.35, gap: mk_.gap });
  }
  // the title rolls in like a value
  if (sc.title && t >= sc.title.t) {
    const k = clamp((t - sc.title.t) / 0.4), ti = sc.title;
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    ctx.letterSpacing = (ti.track ?? 18) + 'px'; ctx.font = `300 ${ti.size || 140}px ${FONT.ui}`;
    ctx.fillStyle = T.hi(0.95 * clamp(k * 3)); ctx.fillText(rollText(ti.text, k, f, 7), ti.x ?? 96, ti.y ?? 400);
    ctx.letterSpacing = '0px';
    ctx.strokeStyle = T.line(0.6); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(ti.x ?? 96, (ti.y ?? 400) + 30); ctx.lineTo((ti.x ?? 96) + 520 * eo(k), (ti.y ?? 400) + 30); ctx.stroke();
    if (ti.sub) { ctx.font = `500 48px ${FONT.mono}`; ctx.fillStyle = T.line(0.9 * clamp(k * 2 - 0.6)); ctx.fillText(rollText(ti.sub, clamp(k * 1.4 - 0.3), f, 9), ti.x ?? 96, (ti.y ?? 400) + 100); }
    ctx.restore();
  }
  return infos;
}

function statusAt(sc, t) {
  let s = null;
  for (const e of sc.status || []) if (t >= e[0]) s = e;
  if (!s) return '';
  if (s.length > 2) { const p = Math.round(100 * clamp((t - s[2]) / (s[3] - s[2]))); return s[1].replace('{pct}', String(p).padStart(3, '0')); }
  return s[1];
}

function render(ctx, t, SC) {
  const T = theme(SC.hue, SC.accent), f = frameOf(t);
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; ctx.filter = 'none';
  ctx.clearRect(0, 0, W, H);
  const sc = SC.scenes.find(s => t >= s.t0 && t < s.t1) || SC.scenes[SC.scenes.length - 1];
  const isHolo = sc.kind === 'holo';
  if (isHolo) {
    drawHolo(ctx, T, sc, t);
    // the rail: finished values docked as chips (two columns from y 236), slide in, stay to the end
    const done = (SC.chips || []).filter(c => t >= c.t);
    done.forEach((c, i) => {
      const k = eo((t - c.t) / 0.3), col = i % 2, row = Math.floor(i / 2);
      chip(ctx, T, 76 + col * 468 + (1 - k) * 40, 236 + row * 104, c, k, { w: 452 });
    });
  }
  chrome(ctx, T, { tl: SC.subject, tr: isHolo ? statusAt(sc, t) : (sc.status ? statusAt(sc, t) : ''), px: isHolo ? (keyed(sc.cam, t, {}).yaw || 0) * 200 : 0, alpha: isHolo ? 1 : 0.9, over: !isHolo, shadow: !isHolo });
  for (const s of SC.subs || []) {
    if (!between(t, s.t0 - 0.1, s.t1 - 0.12)) continue;
    const speaking = (SC.words || []).some(w => between(t, w[0], w[1]));
    subtitle(ctx, T, s.text, 1, { t, speaking });
  }
  for (const g of SC.glitch || []) if (between(t, g, g + 3 / FPS)) glitch(ctx, 1 - (t - g) * FPS / 3 * 0.5, f * 7.1);
  if (isHolo && t - sc.t0 < 0.1 && !sc.noBoot) {   // HUD power-on: a bright line opens to the full frame in 3 frames
    const k = eo((t - sc.t0) / 0.1), hh = H * k / 2;
    ctx.save(); ctx.globalCompositeOperation = 'destination-in'; ctx.fillStyle = '#000'; ctx.fillRect(0, H / 2 - hh - 2, W, hh * 2 + 4);
    ctx.globalCompositeOperation = 'destination-over'; ctx.fillStyle = T.bg0; ctx.fillRect(0, 0, W, H); ctx.restore();
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = T.hi(0.9 * (1 - k)); ctx.fillRect(0, H / 2 - hh - 2, W, 4); ctx.fillRect(0, H / 2 + hh - 2, W, 4); ctx.restore();
  }
  return { holo: isHolo };
}

window.HH = { render, theme, MODELS, model, makeCamera, rollText, FONT, W, H, FPS };
})();
