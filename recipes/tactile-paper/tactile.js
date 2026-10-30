/* Tactile paper runtime (recipes/tactile-paper/tactile.js). tactile.py inlines it into index.html after `const D = {...}`.
   Seek-safe: every visual is a pure function of composition time t (render(t) on a paused GSAP proxy and on hf-seek).
   Designed motion is stepped (12 fps = twos; 8 fps = threes on the payoff); the plate, the caption swaps and the
   whole-frame reveal timing stay on the 30 fps clock.
   The page fold, unfurl, brush, marker, gobo and caption code is the replica of @chrismoran__'s reel
   (a frame-by-frame replica) as the founding reel used it; the scene loop under it is
   data-driven: D.scenes (sheets, marks, labels, titles, rises, arrows, gobo, blur, reveal), D.cams, D.comps, D.bakes. */
const PI = Math.PI, FPS = D.fps, RP = D.R, H = D.house;
const $ = (id) => document.getElementById(id);
const st = (t, f, t0 = 0) => Math.floor((t - t0) * f + 1e-6);         // step index on an f-fps clock from t0
const I = [1, 0, 0, 0, 1, 0];
function mul(A, B) { return [A[0]*B[0]+A[1]*B[3], A[0]*B[1]+A[1]*B[4], A[0]*B[2]+A[1]*B[5]+A[2], A[3]*B[0]+A[4]*B[3], A[3]*B[1]+A[4]*B[4], A[3]*B[2]+A[4]*B[5]+A[5]]; }
const chain = (...M) => M.reduce((a, b) => mul(a, b));
const Tm = (x, y) => [1, 0, x, 0, 1, y];
const Sm = (s) => [s, 0, 0, 0, s, 0];
const Rm = (d) => { const c = Math.cos(d * PI / 180), s = Math.sin(d * PI / 180); return [c, -s, 0, s, c, 0]; };
function M3([s, r, tx, ty]) { const c = s * Math.cos(r * PI / 180), sn = s * Math.sin(r * PI / 180); return [c, -sn, tx, sn, c, ty]; }
const cssM = (A) => `matrix(${A[0]},${A[3]},${A[1]},${A[4]},${A[2]},${A[5]})`;
const setT = (ctx, A) => ctx.setTransform(A[0], A[3], A[1], A[4], A[2], A[5]);
function lerpTab(tab, F) {
  if (F <= tab[0][0]) return tab[0].slice(1);
  for (let i = 1; i < tab.length; i++) if (F <= tab[i][0]) { const a = tab[i - 1], b = tab[i], u = (F - a[0]) / (b[0] - a[0]); return a.slice(1).map((v, k) => v + (b[k + 1] - v) * u); }
  return tab[tab.length - 1].slice(1);
}
const stepTab = (tab, F) => { let r = null; for (const row of tab) if (row[0] <= F) r = row; return r; };
const PAGE = D.page;                                                   // replica page space: every sheet's rect [35, 522, 1013, 1478]

/* ---------------- replica: unfurl (C2) ---------------- */
const unfC = (F) => (F >= 24 ? I : M3(lerpTab(RP.unfurl, F)));
function unfFold(F) {
  if (F > 12) return null;
  const r = lerpTab(RP.unfurlFold, F), n = [Math.cos(r[0] * PI / 180), Math.sin(r[0] * PI / 180)];
  return { phi: r[0], c: n[0] * PAGE[0] + n[1] * PAGE[1] - r[1], R: r[2] };
}

/* ---------------- replica: WebGL cylinder-fold paper renderer (makePaper, unchanged from the replica) ---------------- */
function makePaper(canvas) {
  const gl = canvas.getContext('webgl2', { antialias: true, alpha: true, premultipliedAlpha: true, preserveDrawingBuffer: true });
  const VS = `#version 300 es
  in vec2 a_uv;
  uniform vec4 u_rect; uniform vec3 u_fold; uniform float u_R; uniform mat3 u_C; uniform float u_z;
  out vec2 v_uv; out float v_th;
  void main() {
    vec2 p = u_rect.xy + a_uv * u_rect.zw; vec2 n = u_fold.xy;
    float d = dot(p, n) - u_fold.z; float R = max(u_R, 0.25);
    vec2 q = p; float z = 0.0; float th = 0.0;
    if (d > 0.0) {
      if (d < 3.14159265 * R) { th = d / R; q = p - d * n + R * sin(th) * n; z = R * (1.0 - cos(th)); }
      else { th = 3.14159265; q = p - (2.0 * d - 3.14159265 * R) * n; z = 2.0 * R; }
    }
    vec3 s = u_C * vec3(q, 1.0);
    v_uv = a_uv; v_th = th;
    gl_Position = vec4(s.x / 540.0 - 1.0, 1.0 - s.y / 960.0, 0.5 - (z + u_z) * 0.0002, 1.0);
  }`;
  const FS = `#version 300 es
  precision highp float;
  in vec2 v_uv; in float v_th;
  uniform sampler2D u_tex; uniform float u_backOp; uniform vec3 u_paper; uniform float u_shade; uniform float u_flipFace;
  out vec4 o;
  void main() {
    vec4 c = texture(u_tex, v_uv);
    if (c.a < 0.5) discard;
    c.rgb /= max(c.a, 0.001);
    bool front = gl_FrontFacing == (u_flipFace < 0.5);
    float nz = front ? cos(v_th) : -cos(v_th);
    if (!front) c.rgb = mix(u_paper, c.rgb, u_backOp);
    float lit = mix(1.0 - u_shade, 1.0, clamp(nz, 0.0, 1.0));
    float rim = (v_th > 0.0 && v_th < 3.14159265) ? 0.10 * pow(sin(v_th), 6.0) * (front ? 0.0 : 1.0) : 0.0;
    o = vec4(min(c.rgb * lit + rim, 1.0), 1.0);
  }`;
  const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
  const prog = gl.createProgram(); gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog);
  const NX = 180, NY = 260, uv = [], idx = [];
  for (let j = 0; j <= NY; j++) for (let i = 0; i <= NX; i++) uv.push(i / NX, j / NY);
  for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) { const a = j * (NX + 1) + i, b = a + 1, c = a + NX + 1, d = c + 1; idx.push(a, b, c, b, d, c); }
  const vao = gl.createVertexArray(); gl.bindVertexArray(vao);
  const vb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vb); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(uv), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'a_uv'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(idx), gl.STATIC_DRAW);
  const U = {}; for (const k of ['u_rect', 'u_fold', 'u_R', 'u_C', 'u_z', 'u_tex', 'u_backOp', 'u_paper', 'u_shade', 'u_flipFace']) U[k] = gl.getUniformLocation(prog, k);
  const texOf = (img) => { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img); gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return t; };
  return {
    gl, texOf,
    begin() { gl.viewport(0, 0, 1080, 1920); gl.clearColor(0, 0, 0, 0); gl.clearDepth(1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.useProgram(prog); gl.bindVertexArray(vao); },
    draw(o) {
      const f = o.fold; let n = [1, 0], L = 1e7, R = 1;
      if (f) { n = [Math.cos(f.phi * PI / 180), Math.sin(f.phi * PI / 180)]; R = Math.max(f.R, 0.25); L = f.c - PI * R / 2; }
      const C = o.C;
      gl.uniform4f(U.u_rect, ...o.rect); gl.uniform3f(U.u_fold, n[0], n[1], L); gl.uniform1f(U.u_R, R);
      gl.uniformMatrix3fv(U.u_C, false, [C[0], C[3], 0, C[1], C[4], 0, C[2], C[5], 1]);
      gl.uniform1f(U.u_z, o.z || 0); gl.uniform1f(U.u_backOp, o.backOp ?? 0.85); gl.uniform3f(U.u_paper, ...(o.paper || [0.93, 0.93, 0.92]));
      gl.uniform1f(U.u_shade, o.shade ?? 0.35); gl.uniform1f(U.u_flipFace, 1);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, o.tex); gl.uniform1i(U.u_tex, 0);
      gl.drawElements(gl.TRIANGLES, idx.length, gl.UNSIGNED_INT, 0);
    },
  };
}

/* ---------------- replica: tapered brush + arrows ---------------- */
function resample(pts, step) {
  const out = [pts[0]]; let acc = 0;
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i]; const seg = Math.hypot(x1 - x0, y1 - y0); if (seg < 1e-6) continue;
    let d = step - acc;
    while (d <= seg) { out.push([x0 + (x1 - x0) * d / seg, y0 + (y1 - y0) * d / seg]); d += step; }
    acc = seg - (d - step);
  }
  out.push(pts[pts.length - 1]); return out;
}
function smooth(p, k) { if (p.length < 5) return p; const o = p.map((q) => q.slice());
  for (let i = 1; i < p.length - 1; i++) { let sx = 0, sy = 0, c = 0; for (let j = -k; j <= k; j++) { const q = p[Math.min(p.length - 1, Math.max(0, i + j))]; sx += q[0]; sy += q[1]; c++; } o[i] = [sx / c, sy / c]; }
  return o; }
function brush(pts, prog, wmax, startTaper = 18, endTaper = 18) {
  if (prog <= 0) return '';
  const p = smooth(resample(pts, 2), 3); const L = (p.length - 1) * 2; const upto = Math.max(2, Math.round(prog * (p.length - 1)));
  const left = [], right = [];
  for (let i = 0; i <= upto && i < p.length; i++) {
    const a = p[Math.max(0, i - 1)], b = p[Math.min(p.length - 1, i + 1)]; let tx = b[0] - a[0], ty = b[1] - a[1]; const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
    const s = i * 2; const w = wmax * Math.min(1, Math.pow(Math.min(s / startTaper, 1), 0.6)) * Math.min(1, Math.pow(Math.min((L - s) / endTaper, 1), 0.7)) * 0.5 + 0.5;
    left.push([p[i][0] - ty * w, p[i][1] + tx * w]); right.push([p[i][0] + ty * w, p[i][1] - tx * w]);
  }
  const all = left.concat(right.reverse());
  return 'M' + all.map((q) => q[0].toFixed(1) + ' ' + q[1].toFixed(1)).join('L') + 'Z';
}
function arrowPath(a, shaftProg, armProg, w, armW) {
  let d = brush(a.shaft, shaftProg, w);
  if (armProg > 0) for (const arm of a.arms) d += brush(arm, armProg, armW, 4, 12);
  return d;
}

/* ---------------- hand marks: crimson marker (C6) + hand ellipse (Dc1 C6) ---------------- */
const INK = H.marker;
function ellPts(cx, cy, rx, ry, tilt, seed) {
  const pts = [], N = 140, ct = Math.cos(tilt * PI / 180), stl = Math.sin(tilt * PI / 180);
  for (let i = 0; i <= N; i++) { const u = i / N, th = -2.3 + u * 1.6 * 2 * PI;
    const j = 1 + 0.05 * Math.sin(3 * th + seed) + 0.07 * u + 0.025 * Math.sin(7 * th + 2 * seed);
    const x = rx * j * Math.cos(th), y = ry * j * Math.sin(th); pts.push([cx + x * ct - y * stl, cy + x * stl + y * ct]); }
  return pts;
}
const polyD = (pts, prog) => { const n = Math.max(2, Math.round(prog * (pts.length - 1)) + 1); return 'M' + pts.slice(0, n).map((p) => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('L'); };
function ulPts(rows) {   // marker underline strokes under word boxes (page px) -> page space
  return rows.map(([x0, y0, x1, y1]) => { const pts = []; for (let k = 0; k <= 24; k++) { const u = k / 24;
    pts.push([PAGE[0] + x0 - 8 + (x1 - x0 + 16) * u, PAGE[1] + y1 + 9 - 3 * u + 2.2 * Math.sin(u * 9.3)]); } return pts; });
}
function ulD(strokes, prog) {   // progress over the strokes' total length
  const L = strokes.map((s) => s.length - 1), tot = L.reduce((a, b) => a + b, 0); let left = prog * tot, d = '';
  strokes.forEach((s, i) => { if (left <= 0) return; const p = Math.min(1, left / L[i]); d += polyD(s, p); left -= L[i]; });
  return d;
}
const ELL_STEPS = [[0, 0.09], [1, 0.3], [3, 0.6], [6, 0.94], [10, 1.0]];  // Dc1: drawings held 1,2,3,4 f, head last
function ellProg(t, t0) { const f = Math.round((t - t0) * FPS); if (f < 0) return [0, 0]; const r = stepTab(ELL_STEPS, f); return [r ? r[1] : 0, f >= 10 ? 1 + Math.floor((f - 10) / 3) % 3 : 0]; }
const UL_STEPS = [0.8, 0.93, 1.0];                                     // C6: 80 % of the ink on the first drawing
const ulProg = (t, t0) => (t < t0 ? 0 : UL_STEPS[Math.min(2, st(t, 12, t0))]);

/* ---------------- replica: gobo shadow (C8) ---------------- */
function gobo(t, t0, k0) {
  const F = 89 + 3 * st(t, 12, t0); const [ang, c, w, k1] = lerpTab(RP.gobo, F); const k = k1 * k0;
  const n = [Math.cos(ang * PI / 180), Math.sin(ang * PI / 180)];
  const beta = Math.atan2(n[0], -n[1]); const len = Math.abs(1080 * Math.sin(beta)) + Math.abs(1920 * Math.cos(beta));
  const nc = n[0] * 540 + n[1] * 960; const stops = [];
  for (let u = -5 * w; u <= 5 * w; u += w / 2) { const tt = (u + c - nc) / len + 0.5; const a = k / (1 + Math.exp(-u / w)); stops.push(`rgba(0,0,0,${a.toFixed(4)}) ${(tt * 100).toFixed(3)}%`); }
  $('gobo').style.background = `linear-gradient(${(beta * 180 / PI).toFixed(3)}deg, ${stops.join(', ')})`; $('gobo').style.display = 'block';
}

/* ---------------- cameras + matrix expressions (tactile.py writes them as op lists) ---------------- */
// camera: T(a) R(rot) S(s * (1 + rate * k)) T(-p); k = steps on its fps clock from t0 (the slow push on twos). Before
// `jump` it is the identity (a zoom-blur push lands its scale jump there); `upto` freezes it (the reveal's painted sheet).
function camM(c, t) {
  if (c.jump !== null && t < c.jump) return I;
  const k = st(c.upto !== null ? Math.min(t, c.upto) : t, c.fps, c.t0);
  const M = [Tm(c.a[0], c.a[1])];
  if (c.rot) M.push(Rm(c.rot));
  M.push(Sm(c.s * (1 + c.rate * k)), Tm(-c.p[0], -c.p[1]));
  return chain(...M);
}
function opM(op, t) {
  if (op[0] === 'T') return Tm(op[1], op[2]);
  if (op[0] === 'R') return Rm(op[1]);
  if (op[0] === 'S') return Sm(op[1]);
  if (op[0] === 'cam') return camM(D.cams[op[1]], op.length > 2 ? op[2] : t);
  return I;
}
function mx(ops, t) { let A = null; for (const op of ops) { const B = opM(op, t); A = A ? mul(A, B) : B; } return A || I; }   // left fold = chain()

/* ---------------- static setup ---------------- */
const ctx2 = document.createElement('canvas').getContext('2d');
const textW = (txt, size, ls = 0) => { ctx2.font = `700 ${size}px "Inter Tight"`; ctx2.letterSpacing = ls + 'px'; return ctx2.measureText(txt).width; };
let paper = null, TX = {}, IMG = {};
const SVG = 'http://www.w3.org/2000/svg';
const svgText = (cls, x, y, size, fill, txt) => { const e = document.createElementNS(SVG, 'text'); e.setAttribute('class', cls); e.setAttribute('x', x);
  e.setAttribute('y', y); e.setAttribute('font-size', size); e.setAttribute('fill', fill); e.textContent = txt; return e; };
function setupStatic() {
  for (const S of D.scenes) {
    for (const T of S.titles) {            // hook title words: whole, opaque, rising on twos (ref C3); x from the words before
      const g = document.createElementNS(SVG, 'g'); g.setAttribute('id', T.id); g.style.display = 'none'; $('titleG').appendChild(g);
      T.words.forEach((w, i) => { const x = w.prefix ? w.x + textW(w.prefix, T.size, T.ls) : w.x;
        const e = svgText('t', x, w.y, T.size, T.fill, w.w); e.setAttribute('id', `${T.id}w${i}`); e.setAttribute('letter-spacing', T.ls); g.appendChild(e); });
    }
    for (const W of S.rises) {             // a word whose letters rise from behind a page edge (ref C10)
      const g = document.createElementNS(SVG, 'g'); g.setAttribute('id', W.id); g.style.display = 'none'; $('underG').appendChild(g);
      const tot = textW(W.text, W.size, W.ls); let x = W.cx - tot / 2;
      for (const ch of W.text) { g.appendChild(svgText('t', x.toFixed(1), W.y, W.size, W.fill, ch)); x += textW(ch, W.size, W.ls); }
    }
    for (const L of S.labels) { const e = document.createElement("div"); e.className = "label"; e.id = L.id; e.textContent = L.text; $("world").insertBefore(e, $("titleSvg")); }
    for (const A of S.arrows) { const e = document.createElementNS(SVG, 'path'); e.setAttribute('id', A.id); e.setAttribute('fill', A.fill); e.setAttribute('d', ''); $('overSvg').appendChild(e); }
  }
}

/* whole-frame sheets for the reveals (the page under the page is the speaker's face): painted once, flat, at the turn's state */
function comp(fn) { const cv = document.createElement('canvas'); cv.width = 1080; cv.height = 1920; const c = cv.getContext('2d'); fn(c); return cv; }
function paintGround(c, CW) { setT(c, chain(CW, Tm(-100, -100))); c.drawImage(IMG.ground, 0, 0); }
function paintSheet(c, A, img, k) { c.save(); c.shadowColor = H.sheetShadow; c.shadowBlur = 16; c.shadowOffsetY = 10; setT(c, chain(A, Sm(k))); c.drawImage(img, 0, 0); c.restore(); }
function strokeInk(c, A, d, w) { c.save(); setT(c, A); c.globalCompositeOperation = 'multiply'; c.strokeStyle = INK; c.globalAlpha = 0.9; c.lineWidth = w; c.lineCap = 'round'; c.lineJoin = 'round'; c.stroke(new Path2D(d)); c.restore(); }
function markD(m, prog, ev = 0) { return m.kind === 'ul' ? ulD(m.pts || ulPts(m.rows), prog) : polyD(ellPts(m.cx, m.cy, m.rx, m.ry, m.tilt, m.seed + ev), prog); }

/* ---------------- per-frame render ---------------- */
const showMarks = (A, html) => { $('mkG').setAttribute('transform', cssM(A)); $('mkG').innerHTML = html; };
const inkPath = (d, w) => `<path d="${d}" fill="none" stroke="${INK}" stroke-opacity="0.9" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
function turnFrac(t, t0, f, fr) { if (t < t0) return -1; const k = st(t, f, t0); return k < fr.length ? fr[k] : 9; }
function markHTML(m, t) {
  if (m.kind === 'ul') { const d = ulD(m.pts, ulProg(t, m.t0)); return d ? inkPath(d, m.w) : ''; }
  const [ep, ev] = ellProg(t, m.t0); return ep > 0 ? inkPath(polyD(ellPts(m.cx, m.cy, m.rx, m.ry, m.tilt, m.seed + ev), ep), m.w) : '';
}
function sheetState(sp, t) {               // null (not on screen) or { C, fold, shade }
  if (sp.kind === 'slide') {               // a print / card curling in from the right edge, settling tilted (ref C11 photo)
    if (t < sp.t0) return null; const S = sp.steps[Math.min(sp.steps.length - 1, st(t, sp.fps, sp.t0))];
    return { C: chain(Tm(S[0], sp.cy), Rm(S[1]), Sm(sp.s), Tm(-sp.rect[2] / 2, -sp.rect[3] / 2)), fold: S[2] !== null ? { phi: 0, c: S[2], R: sp.R } : null, shade: sp.shade };
  }
  const B = mx(sp.M, t);
  if (sp.kind === 'unfurl') {              // CC Page Turn run backwards: enters from the bottom-right corner (ref C2)
    if (t < sp.t0) return null; const F = Math.min(24, sp.F0 + sp.step * st(t, sp.fps, sp.t0));
    return { C: mul(B, unfC(F)), fold: unfFold(F), shade: F <= 14 ? sp.curlShade : sp.shade };
  }
  if (sp.kind === 'turn') {                // a page that turns away right to left, linear, on its clock (ref C7b)
    const k = t >= sp.t0 ? st(t, sp.fps, sp.t0) : -1; if (k >= sp.n) return null;
    return { C: B, fold: k < 0 ? null : { phi: sp.phi, c: sp.c0 - (k + 1) * (sp.span / sp.n), R: sp.R }, shade: sp.shade };
  }
  return { C: B, fold: null, shade: sp.shade };
}
function drawScene(S, t) {
  if (S.reveal) {                          // the whole frame turns like a page and the speaker's face is under it (ref C7a / C7d)
    const R = S.reveal, fr = turnFrac(t, R.t0, R.fps, R.fr);
    if (fr >= 0) {
      if (fr < 2) { $('gl').style.filter = 'none';
        paper.draw({ tex: TX[R.comp], rect: [0, 0, 1080, 1920], C: I, fold: { phi: 8, c: 1340 - fr * 1360, R: 10 }, backOp: 0.18, paper: R.back, shade: 0.4 }); }
      return;
    }
  }
  if (S.ground) {
    if (S.ground.flat) $('flatground').style.display = 'block';
    else { $('ground').style.display = 'block'; $('ground').style.transform = cssM(mul(mx(S.ground.M, t), Tm(-100, -100))); }
  }
  const Cs = [];
  for (const sp of S.sheets) { const s = sheetState(sp, t); Cs.push(s ? s.C : null); if (!s) continue;
    paper.draw({ tex: TX[sp.tex], rect: sp.rect, C: s.C, fold: s.fold, z: sp.z, backOp: sp.backOp, paper: sp.paper, shade: s.shade }); }
  if (S.marks && Cs[S.marks.on]) { let html = ''; for (const m of S.marks.items) html += markHTML(m, t); if (html) showMarks(Cs[S.marks.on], html); }
  for (const L of S.labels) {             // a charcoal word label, glued to its page, boiling at 8 fps
    const C = Cs[L.on]; if (!C || t < L.t0) continue;
    const b = st(t, 8, L.t0), jx = [0, 2, -1, 1, -2][b % 5], jy = [0, -1, 2, -2, 1][b % 5], jr = [0, 0.4, -0.3, 0.2, -0.4][b % 5];
    const e = $(L.id); e.style.display = 'block'; e.style.transform = cssM(chain(C, Tm(L.x + jx, L.y + jy), Rm(L.rot + jr)));
  }
  for (const T of S.titles) {
    if (t < T.t0 || (T.until !== null && t >= T.until)) continue;
    $('titleSvg').style.display = 'block'; $(T.id).style.display = 'inline'; const k = st(t, T.fps, T.t0);
    T.words.forEach((w, i) => { const r = stepTab(w.rise, k); $(`${T.id}w${i}`).setAttribute('transform', `translate(0 ${r[1]})`); });
  }
  for (const W of S.rises) {
    $('underSvg').style.display = 'block'; $(W.id).style.display = 'inline'; const ls = $(W.id).children;
    for (let i = 0; i < ls.length; i++) { const t0 = W.t0 + i / W.per; const e = ls[i];
      if (t < t0) { e.style.display = 'none'; continue; } e.style.display = 'inline';
      e.setAttribute('transform', `translate(0 ${W.tab[Math.min(W.tab.length - 1, st(t, W.fps, t0))]})`); }
  }
  for (const A of S.arrows) {             // white / black brush arrows drawing on, head last (ref C4 / C9 / C10)
    if (t < A.t0 || (A.until !== null && t >= A.until)) continue;
    const r = A.steps[Math.min(A.steps.length - 1, st(t, A.fps, A.t0))]; $(A.id).setAttribute('d', arrowPath(A, r[0], r[1], A.w, A.armW));
  }
  if (S.gobo && t >= S.gobo.t0) { const g = S.gobo;
    gobo(t, g.t0, g.fadeEnd !== null ? Math.max(0, Math.min(1, (g.fadeEnd - (st(t, 12) / 12)) / 0.5)) * g.k : g.k); }
  if (S.blur) { const r = t < S.blur.t ? null : stepTab(S.blur.tab, t - S.blur.t); const bl = r ? r[1] : 0; if (bl > 0) $('world').style.filter = `blur(${bl}px)`; }
}
function render(t) {
  if (!paper) return;
  const N = Math.round(t * FPS + 1e-6);
  $('ground').style.display = 'none'; $('flatground').style.display = 'none'; $('gobo').style.display = 'none';
  $('titleSvg').style.display = 'none'; $('underSvg').style.display = 'none';
  $('world').style.filter = 'none'; $('gl').style.filter = H.glShadow;
  for (const e of document.querySelectorAll('.label')) e.style.display = 'none';
  for (const e of $('titleG').children) e.style.display = 'none';
  for (const e of $('underG').children) e.style.display = 'none';
  for (const e of document.querySelectorAll('#overSvg path')) e.setAttribute('d', '');
  showMarks(I, '');
  paper.begin();
  const S = D.scenes.find((s) => N >= Math.round(s.t0 * FPS) && N < Math.round(s.t1 * FPS));
  if (S) drawScene(S, t);
  // captions: hard swaps on the words (ref C5), 1-3 words, a condensed pill
  const cp = D.caps.find((c) => t >= c[0] && t < c[1]); const txt = cp ? cp[2] : '';
  $('cap').style.display = txt ? 'flex' : 'none';
  if (txt) { $('pillTxt').textContent = txt; $('pill').style.width = (textW(txt, H.cap.size) * H.cap.condense + 2 * H.cap.pad).toFixed(1) + 'px';
    $('pillTxt').style.transform = `scaleX(${H.cap.condense})`; }
}

/* ---------------- boot ---------------- */
const loadImg = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('load ' + src)); i.src = src; });
window.__timelines = window.__timelines || {};
window.__hf = window.__hf || {}; window.__hf.buildReady = window.__hf.buildReady || {};
const ready = (async () => {
  await document.fonts.load('700 128px "Inter Tight"', D.fontText); await document.fonts.ready;
  const names = Object.keys(D.imgs);
  const ims = await Promise.all(names.map((n) => loadImg(D.imgs[n])).concat([loadImg(D.groundSrc)]));
  names.forEach((n, i) => { IMG[n] = ims[i]; }); IMG.ground = ims[names.length];
  setupStatic();
  for (const S of D.scenes) if (S.marks) for (const m of S.marks.items) if (m.kind === 'ul') m.pts = ulPts(m.rows);
  paper = makePaper($('gl'));
  for (const n of names) TX[n] = paper.texOf(IMG[n]);
  for (const [name, b] of Object.entries(D.bakes)) {   // marks baked into a page that later turns (they leave with it)
    const src = IMG[b.img], cv = document.createElement('canvas'); cv.width = src.width; cv.height = src.height;
    const c = cv.getContext('2d'); c.drawImage(src, 0, 0); for (const m of b.inks) strokeInk(c, b.A, markD(m, 1), m.w);
    TX[name] = paper.texOf(cv);
  }
  for (const [name, c] of Object.entries(D.comps)) TX[name] = paper.texOf(comp((x) => {
    if (c.ground) paintGround(x, mx(c.ground, 0));
    for (const s of c.sheets) paintSheet(x, mx(s.M, 0), IMG[s.img], s.k);
    for (const k of c.inks) strokeInk(x, mx(k.M, 0), markD(k.mark, 1, k.ev), k.w);
  }));
  const proxy = { t: 0 };
  const tl = gsap.timeline({ paused: true });
  tl.fromTo(proxy, { t: 0 }, { t: D.T, duration: D.T, ease: 'none', onUpdate: () => render(proxy.t) }, 0);
  render(0);
  window.__timelines['main'] = tl;
})();
window.__hf.buildReady['paper'] = ready;
window.addEventListener('hf-seek', (e) => render(e.detail.time));
