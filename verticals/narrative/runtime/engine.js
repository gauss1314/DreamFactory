// Narrative engine: painted backgrounds, inked cels and the finish, on a 2D canvas.
// Every random choice comes from a seeded generator, so a frame is a pure function of its time.
export const W = 1920;
export const H = 1080;

// ---------- numbers and colour ----------
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (x) => {
  const t = clamp(x);
  return t * t * (3 - 2 * t);
};
/** Character drawings change twelve times a second (on twos at 24 fps). */
export const twos = (t) => Math.floor(t * 12 + 1e-6) / 12;

export function hex(c) {
  const v = parseInt(c.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}
export function mix(a, b, t) {
  const x = typeof a === 'string' ? hex(a) : a;
  const y = typeof b === 'string' ? hex(b) : b;
  return [0, 1, 2].map((i) => lerp(x[i], y[i], t));
}
export function css(c, alpha = 1) {
  const v = typeof c === 'string' ? hex(c) : c;
  return `rgba(${v.map((x) => Math.round(clamp(x, 0, 255))).join(',')},${alpha})`;
}
/** Nudge a colour so no two marks are the same. */
export function jit(c, r, amt = 10) {
  const v = typeof c === 'string' ? hex(c) : c;
  const d = (r() - 0.5) * amt;
  return v.map((x) => x + d + (r() - 0.5) * amt * 0.6);
}
/** A vertical ramp through colour stops: [[0, '#...'], [0.5, '#...'], [1, '#...']]. */
export function ramp(stops, t) {
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [t0, c0] = stops[i - 1];
      const [t1, c1] = stops[i];
      return mix(c0, c1, (t - t0) / (t1 - t0 || 1));
    }
  }
  return hex(stops.at(-1)[1]);
}

export function layer(w = W, h = H) {
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  return { canvas, g: canvas.getContext('2d') };
}

// ---------- curves ----------
/** Catmull-Rom through points [[x, y, ...extra], ...], k samples per span. */
export function spline(pts, k = 10) {
  if (pts.length < 3) return pts;
  const out = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    for (let s = 0; s < k; s++) {
      const t = s / k;
      const t2 = t * t;
      const t3 = t2 * t;
      out.push(p1.map((_, j) => 0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)));
    }
  }
  out.push(pts.at(-1));
  return out;
}

// ---------- paint ----------
/**
 * One flat-brush stroke along a path: several bristles, each its own shade, thinning at both ends,
 * with dry gaps. pts: [[x, y], ...]. Strokes follow the form they describe.
 */
export function stroke(g, pts, { width = 12, color = '#888', alpha = 0.85, r = rng(1), bristles = 6, dry = 0.15, taper = 0.35 } = {}) {
  const path = spline(pts, 6);
  const len = path.length;
  for (let b = 0; b < bristles; b++) {
    const off = ((b + 0.5) / bristles - 0.5) * width;
    const col = jit(color, r, 14);
    const a = alpha * (0.55 + 0.45 * r());
    const start = Math.floor(r() * len * 0.12);
    const end = len - Math.floor(r() * len * 0.15);
    g.beginPath();
    for (let i = start; i < end; i++) {
      const [x, y] = path[i];
      const [x2, y2] = path[Math.min(len - 1, i + 1)];
      const dx = x2 - x || 1e-6;
      const dy = y2 - y;
      const l = Math.hypot(dx, dy) || 1;
      const u = i / (len - 1);
      const thin = Math.min(1, u / taper, (1 - u) / taper);
      const nx = (-dy / l) * off * (0.4 + 0.6 * thin);
      const ny = (dx / l) * off * (0.4 + 0.6 * thin);
      if (i === start || r() < dry * 0.08) g.moveTo(x + nx, y + ny);
      else g.lineTo(x + nx, y + ny);
    }
    g.strokeStyle = css(col, a);
    g.lineWidth = Math.max(1, (width / bristles) * (1.1 + r() * 0.9));
    g.lineCap = 'round';
    g.lineJoin = 'round';
    g.stroke();
  }
}

/** A short flat-brush dab with a ragged edge. */
export function dab(g, x, y, w, h, angle, color, alpha, r) {
  g.save();
  g.translate(x, y);
  g.rotate(angle);
  g.beginPath();
  const k = 9;
  for (let i = 0; i < k; i++) {
    const a = (i / k) * Math.PI * 2;
    const rr = 0.78 + r() * 0.3;
    g.lineTo(Math.cos(a) * w * 0.5 * rr, Math.sin(a) * h * 0.5 * rr);
  }
  g.closePath();
  g.fillStyle = css(jit(color, r, 12), alpha);
  g.fill();
  g.restore();
}

/** Fill a region with many dabs of a colour ramp, so a flat area reads as painted. */
export function mottle(g, x0, y0, w, h, colorAt, { n = 400, size = 40, alpha = 0.18, r = rng(2), angle = 0 } = {}) {
  for (let i = 0; i < n; i++) {
    const x = x0 + r() * w;
    const y = y0 + r() * h;
    const s = size * (0.5 + r());
    dab(g, x, y, s, s * (0.35 + r() * 0.4), angle + (r() - 0.5) * 0.6, colorAt(x, y), alpha * (0.5 + r()), r);
  }
}

/** An irregular lobe: a circle whose radius wanders, so no two lobes are the same shape. */
function lobePath(g, x, y, rad, r, squash = 0.9) {
  const k = 22;
  const ph = r() * 6.28;
  const amp = 0.06 + r() * 0.08;
  g.beginPath();
  for (let i = 0; i <= k; i++) {
    const a = (i / k) * Math.PI * 2;
    const rr = rad * (1 + amp * Math.sin(a * 3 + ph) + amp * 0.6 * Math.sin(a * 5 - ph * 1.7));
    const px = x + Math.cos(a) * rr;
    const py = y + Math.sin(a) * rr * squash;
    if (i === 0) g.moveTo(px, py);
    else g.lineTo(px, py);
  }
  g.closePath();
}

/**
 * A painted cumulus, lit from the direction (lx, ly): a flat, cool underside; lobes of many sizes
 * built up from shadow to light; brushwork that follows the lobes; no outlines.
 */
export function cloud(g, cx, cy, w, h, { light, half, shadow, lx = 1, ly = -0.3, r = rng(3), lobes = 9 }) {
  const parts = [];
  for (let i = 0; i < lobes * 2; i++) {
    const u = r();
    const px = cx + (u - 0.5) * w;
    const rise = Math.sin(u * Math.PI) ** 0.8;
    const rad = h * (0.14 + 0.36 * rise * (0.55 + r() * 0.6));
    const py = cy - rise * h * (0.2 + r() * 0.35) + rad * 0.25;
    parts.push([px, py, rad]);
  }
  parts.sort((a, b) => a[1] - b[1]);
  const L = Math.hypot(lx, ly) || 1;
  const ux = lx / L;
  const uy = ly / L;
  g.save();
  // the base of a cumulus is flat: nothing below it
  g.beginPath();
  g.rect(cx - w, cy - h * 2, w * 2, h * 2 + h * 0.18);
  g.clip();
  // shadow side: the whole mass, sitting away from the light
  for (const [px, py, rad] of parts) {
    lobePath(g, px - ux * rad * 0.08, py - uy * rad * 0.08 + rad * 0.06, rad, r);
    g.fillStyle = css(jit(shadow, r, 6), 1);
    g.fill();
  }
  // half tone, then light, each pulled toward the light so the shadow shows only on the far side
  for (const [col, shift, scale] of [[half, 0.2, 0.9], [light, 0.36, 0.68]]) {
    for (const [px, py, rad] of parts) {
      const facing = 0.5 + 0.5 * ((px - cx) / (w * 0.5)) * ux;
      lobePath(g, px + ux * rad * shift, py + uy * rad * shift, rad * scale * (0.7 + 0.4 * facing), r);
      g.fillStyle = css(jit(col, r, 8), 1);
      g.fill();
    }
  }
  // brushwork wrapping each lobe, in the lobe's own tones
  for (const [px, py, rad] of parts) {
    for (let k = 0; k < 3; k++) {
      const a0 = Math.atan2(uy, ux) - 1.2 + r() * 2.4;
      const arc = [];
      for (let s = 0; s < 4; s++) {
        const a = a0 + s * 0.28;
        const rr = rad * (0.45 + r() * 0.3);
        arc.push([px + Math.cos(a) * rr, py + Math.sin(a) * rr * 0.9]);
      }
      stroke(g, arc, { width: rad * 0.2, color: light, alpha: 0.16, r, bristles: 4 });
    }
  }
  g.restore();
}

/** Grass along a slope: individual blades, each its own length, bend and shade. */
export function grass(g, xs, baseY, { n = 600, len = 40, colors, lean = 0.3, r = rng(4), sway = 0, width = 2.2 }) {
  for (let i = 0; i < n; i++) {
    const x = xs[0] + r() * (xs[1] - xs[0]);
    const y = typeof baseY === 'function' ? baseY(x) + r() * 6 : baseY + r() * 6;
    const L = len * (0.5 + r());
    const bend = (lean + (r() - 0.5) * 0.5 + sway * (0.6 + r() * 0.8)) * L;
    const col = colors[Math.floor(r() * colors.length)];
    g.beginPath();
    g.moveTo(x, y);
    g.quadraticCurveTo(x + bend * 0.3, y - L * 0.6, x + bend, y - L);
    g.strokeStyle = css(jit(col, r, 16), 0.85);
    g.lineWidth = width * (0.6 + r() * 0.8);
    g.lineCap = 'round';
    g.stroke();
  }
}

// ---------- ink ----------
/**
 * A pressure-varied ink line through pts: [[x, y, w], ...], w = width at that point. Ends taper.
 * Drawn as a filled outline so the width really varies along the line.
 */
export function ink(g, pts, color = '#3b2a2e', { taper = true } = {}) {
  const p = spline(pts, 8);
  if (p.length < 2) return;
  const L = [];
  const R = [];
  for (let i = 0; i < p.length; i++) {
    const a = p[Math.max(0, i - 1)];
    const b = p[Math.min(p.length - 1, i + 1)];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const l = Math.hypot(dx, dy) || 1;
    const u = i / (p.length - 1);
    const t = taper ? Math.min(1, u / 0.15, (1 - u) / 0.15) : 1;
    const w = (p[i][2] ?? 2) * (0.25 + 0.75 * t) * 0.5;
    L.push([p[i][0] - (dy / l) * w, p[i][1] + (dx / l) * w]);
    R.push([p[i][0] + (dy / l) * w, p[i][1] - (dx / l) * w]);
  }
  g.beginPath();
  g.moveTo(L[0][0], L[0][1]);
  for (const q of L) g.lineTo(q[0], q[1]);
  for (const q of R.reverse()) g.lineTo(q[0], q[1]);
  g.closePath();
  g.fillStyle = color;
  g.fill();
}

/** Fill a closed spline shape. */
export function blob(g, pts, color) {
  const p = spline([...pts, pts[0], pts[1]], 8).slice(0, -8);
  g.beginPath();
  g.moveTo(p[0][0], p[0][1]);
  for (const q of p) g.lineTo(q[0], q[1]);
  g.closePath();
  g.fillStyle = color;
  g.fill();
  return p;
}

/** Outline a closed spline shape in ink, with gentle pressure variation. */
export function outline(g, pts, w, color = '#3b2a2e', seed = 1) {
  const r = rng(seed);
  const closed = [...pts, pts[0]];
  ink(g, closed.map(([x, y]) => [x, y, w * (0.75 + r() * 0.5)]), color, { taper: false });
}

// ---------- finish ----------
const grainTiles = [];
export function initGrain() {
  for (let k = 0; k < 4; k++) {
    const { canvas, g } = layer(256, 256);
    const img = g.createImageData(256, 256);
    const r = rng(500 + k * 97);
    for (let i = 0; i < img.data.length; i += 4) {
      const v = Math.round(255 * ((r() + r() + r()) / 3));
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    grainTiles.push(g.createPattern(canvas, 'repeat'));
  }
}

/** Paper tooth for painted layers: a fixed, faint texture. */
export function tooth(g, w, h, seed = 11, amt = 0.05) {
  const r = rng(seed);
  for (let i = 0; i < (w * h) / 900; i++) {
    const x = r() * w;
    const y = r() * h;
    g.fillStyle = r() < 0.5 ? `rgba(255,248,235,${amt * r()})` : `rgba(40,30,60,${amt * r()})`;
    g.fillRect(x, y, 1 + r() * 2.5, 1 + r() * 2.5);
  }
}

/** Halation, vignette, grain. Applied once to every finished frame. */
export function finish(g, t, { vignette = 0.32, halation = 0.18, grain = 0.06, warm = '#ffd9a0' } = {}) {
  if (halation > 0) {
    g.save();
    g.globalCompositeOperation = 'screen';
    g.globalAlpha = halation;
    g.filter = 'blur(26px) brightness(1.1)';
    g.drawImage(g.canvas, 0, 0);
    g.filter = 'none';
    g.restore();
    g.save();
    g.globalCompositeOperation = 'soft-light';
    g.fillStyle = css(warm, 0.12);
    g.fillRect(0, 0, W, H);
    g.restore();
  }
  const v = g.createRadialGradient(W * 0.5, H * 0.48, H * 0.35, W * 0.5, H * 0.48, H * 1.05);
  v.addColorStop(0, 'rgba(20,12,30,0)');
  v.addColorStop(1, `rgba(20,12,30,${vignette})`);
  g.fillStyle = v;
  g.fillRect(0, 0, W, H);
  if (grain > 0 && grainTiles.length) {
    g.save();
    g.globalCompositeOperation = 'overlay';
    g.globalAlpha = grain;
    g.fillStyle = grainTiles[Math.floor(t * 12 + 1e-6) % grainTiles.length];
    g.fillRect(0, 0, W, H);
    g.restore();
  }
}
