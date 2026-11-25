// Painters shared by every narrative film: cel shapes, skies, clouds, water, slopes, roads, reeds.
// They take the kit first and read a film's colours from kit.look (film.json "look").
const INK = '#3b2a2e';

// ---------- cel helpers ----------
export function path(kit, pts, closed = true) {
  const p = kit.spline(closed ? [...pts, pts[0], pts[1]] : pts, 8);
  const q = closed ? p.slice(0, -8) : p;
  const P = new Path2D();
  P.moveTo(q[0][0], q[0][1]);
  for (const v of q) P.lineTo(v[0], v[1]);
  if (closed) P.closePath();
  return { P, q };
}

/** Flat colour, one hard shadow away from the light, a thin rim toward it. */
export function cel(g, P, { base, shade, rim, light = [1, -0.4], sd = 10, rw = 3 }) {
  g.fillStyle = base;
  g.fill(P);
  g.save();
  g.clip(P);
  const big = new Path2D();
  big.rect(-5000, -5000, 10000, 10000);
  if (shade) {
    const S = new Path2D();
    S.addPath(big);
    S.addPath(P, new DOMMatrix().translate(light[0] * sd, light[1] * sd));
    g.fillStyle = shade;
    g.fill(S, 'evenodd');
  }
  if (rim) {
    const R = new Path2D();
    R.addPath(big);
    R.addPath(P, new DOMMatrix().translate(-light[0] * rw, -light[1] * rw));
    g.fillStyle = rim;
    g.fill(R, 'evenodd');
  }
  g.restore();
}

export function line(kit, g, q, w, seed, closed = true) {
  const r = kit.rng(seed);
  const pts = (closed ? [...q, q[0]] : q).filter((_, i, a) => i % 3 === 0 || i === a.length - 1);
  kit.ink(g, pts.map(([x, y]) => [x, y, w * (0.7 + 0.6 * r())]), INK, { taper: !closed });
}

export function lerpPt(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

/** A ground shadow under the bike: soft-edged, violet, flattened. */
export function groundShadow(g, x, y, s, len = 330, color = 'rgba(70,50,100,0.45)') {
  g.save();
  g.translate(x, y);
  g.scale(s, s * 0.18);
  const grd = g.createRadialGradient(0, 0, 10, 0, 0, len * 0.6);
  grd.addColorStop(0, color);
  grd.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grd;
  g.beginPath();
  g.ellipse(0, 0, len * 0.6, len * 0.6, 0, 0, Math.PI * 2);
  g.fill();
  g.restore();
}

// ---------- painted plates ----------
// Default colours: a clear evening. A film sets its own in film.json under "look".
export const DEFAULT_LOOK = {
  sky: [[0, '#3d4f8a'], [0.42, '#8a86b8'], [0.75, '#f2b98a'], [1, '#ffd99a']],
  cloud: { light: '#ffe2b8', half: '#e6a58f', shadow: '#8f7aa6', deep: '#6d6194' },
  hills: '#9a92bd', town: '#6f6f9e', bank: '#5f6595', windows: '#ffcf86', bridge: '#56588a',
  water: '#4a4f80', glint: '#ffe2a0',
  grass: { lit: '#d2c067', mid: '#a69a58', base: '#a3964f', dark: '#8a8650', foot: '#6a6458', stroke: '#d8c878', strokeDark: '#9a925a', cool: '#8a7aa0', patch: '#c9b45e', patchDark: '#94904f', shade: '#7d6d98' },
  road: { light: '#e3c9a1', dark: '#9e8478', base: '#b89a86', verge: 'rgba(255,226,170,0.5)' },
  reeds: { stem: ['#8a7d4a', '#b29a5a'], stemBacklit: ['#5b4a5e', '#3e3550'], plume: '#efe0c0', plumeBacklit: '#ffd9a8' },
  shadow: 'rgba(70,50,100,0.45)',
};
const look = (kit) => ({ ...DEFAULT_LOOK, ...(kit.look || {}) });
const SKYOF = (kit) => look(kit).sky;

export function paintSky(kit, g, w, horizon, sun, seed) {
  const r = kit.rng(seed);
  for (let y = 0; y < horizon; y += 2) {
    g.fillStyle = kit.css(kit.ramp(SKYOF(kit), y / horizon));
    g.fillRect(0, y, w, 2);
  }
  kit.mottle(g, 0, 0, w, horizon, (x, y) => kit.ramp(SKYOF(kit), y / horizon), { n: Math.round(w / 3), size: 70, alpha: 0.12, r, angle: 0 });
  // the sun and its warm pool of air
  const glow = g.createRadialGradient(sun[0], sun[1], 10, sun[0], sun[1], 620);
  glow.addColorStop(0, 'rgba(255,241,201,0.95)');
  glow.addColorStop(0.12, 'rgba(255,220,160,0.55)');
  glow.addColorStop(1, 'rgba(255,190,140,0)');
  g.fillStyle = glow;
  g.fillRect(0, 0, w, horizon + 80);
  g.beginPath();
  g.arc(sun[0], sun[1], 46, 0, Math.PI * 2);
  g.fillStyle = '#fff6dc';
  g.fill();
}

export function paintClouds(kit, g, specs, sun) {
  for (const [i, [cx, cy, cw, ch]] of specs.entries()) {
    const dx = sun[0] - cx;
    const dy = sun[1] - cy;
    const l = Math.hypot(dx, dy) || 1;
    // farther from the sun, the cloud sits more in shadow
    const near = kit.clamp(1 - l / 1800);
    kit.cloud(g, cx, cy, cw, ch, {
      light: kit.mix(look(kit).cloud.half, look(kit).cloud.light, 0.5 + 0.5 * near),
      half: kit.mix(look(kit).cloud.shadow, look(kit).cloud.half, 0.6 + 0.4 * near),
      shadow: kit.mix(look(kit).cloud.deep, look(kit).cloud.shadow, 0.5 + 0.5 * near),
      lx: dx / l, ly: dy / l, r: kit.rng(100 + i * 17), lobes: 7 + (i % 4),
    });
  }
}

export function paintFarBank(kit, g, w, y0, seed) {
  const r = kit.rng(seed);
  // distant hills
  g.beginPath();
  g.moveTo(0, y0);
  for (let x = 0; x <= w; x += 40) g.lineTo(x, y0 - 30 - 26 * Math.sin(x / 260 + 1) - 14 * Math.sin(x / 97) - r() * 6);
  g.lineTo(w, y0 + 10);
  g.lineTo(0, y0 + 10);
  g.fillStyle = kit.css(look(kit).hills);
  g.fill();
  // the town: roofs and a few lit windows
  for (let x = 20; x < w; x += 26 + r() * 50) {
    const bw = 18 + r() * 40;
    const bh = 10 + r() * 34;
    g.fillStyle = kit.css(kit.jit(look(kit).town, r, 14));
    g.fillRect(x, y0 - bh, bw, bh + 12);
    if (r() < 0.45) {
      g.fillStyle = kit.css(look(kit).windows, 0.85);
      g.fillRect(x + bw * 0.3, y0 - bh * 0.6, 3, 3);
    }
  }
  g.fillStyle = kit.css(look(kit).bank);
  g.fillRect(0, y0, w, 14);
}

export function paintBridge(kit, g, x0, x1, y, h) {
  g.strokeStyle = kit.css(look(kit).bridge, 0.95);
  g.lineWidth = 3;
  g.beginPath();
  g.moveTo(x0, y);
  g.lineTo(x1, y);
  g.stroke();
  const n = Math.round((x1 - x0) / 34);
  g.lineWidth = 1.6;
  for (let i = 0; i < n; i++) {
    const a = x0 + (i / n) * (x1 - x0);
    const b = x0 + ((i + 1) / n) * (x1 - x0);
    const arch = (u) => y - h * Math.sin(Math.PI * ((u - x0) / (x1 - x0))) ** 0.6;
    g.beginPath();
    g.moveTo(a, y);
    g.lineTo(b, arch(b));
    g.moveTo(a, arch(a));
    g.lineTo(b, arch(b));
    g.moveTo(a, y);
    g.lineTo(a, arch(a));
    g.stroke();
  }
  for (let i = 0; i <= 3; i++) {
    const px = x0 + ((i + 0.5) / 4) * (x1 - x0);
    g.fillStyle = kit.css(look(kit).bridge);
    g.fillRect(px - 4, y, 8, 26);
  }
}

export function paintRiver(kit, g, w, y0, y1, sunX, seed) {
  const r = kit.rng(seed);
  for (let y = y0; y < y1; y += 2) {
    const u = (y - y0) / (y1 - y0);
    // the water mirrors the sky, upside down, a little darker
    g.fillStyle = kit.css(kit.mix(kit.ramp(SKYOF(kit), 1 - u * 0.75), look(kit).water, 0.18 + u * 0.25));
    g.fillRect(0, y, w, 2);
  }
  for (let i = 0; i < w / 9; i++) {
    const y = y0 + r() * (y1 - y0);
    const u = (y - y0) / (y1 - y0);
    const x = r() * w;
    const L = 40 + r() * 160 * (0.4 + u);
    const lightStroke = r() < 0.6;
    const col = lightStroke ? kit.mix(kit.ramp(SKYOF(kit), 1 - u * 0.6), '#fff1d0', 0.25) : kit.mix(kit.ramp(SKYOF(kit), 0.35), look(kit).water, 0.3);
    kit.stroke(g, [[x, y], [x + L * 0.5, y + (r() - 0.5) * 1.2], [x + L, y]], { width: 2 + u * 3, color: col, alpha: 0.22, r, bristles: 3 });
  }
}

/** Glitter under the sun: on twos, each glint has its own phase. */
export function glitter(kit, g, t, sunX, y0, y1, spread, seed, ox = 0, below = () => Infinity, onWater = () => true) {
  const r = kit.rng(seed);
  const d = kit.twos(t);
  for (let i = 0; i < 160; i++) {
    const u = r();
    const y = y0 + u * (y1 - y0);
    const half = spread * (0.15 + u);
    const x = sunX + (r() - 0.5) * 2 * half - ox;
    const ph = r() * 6.28;
    const on = Math.sin(d * 9 + ph) > 0.35;
    if (!on || y > below(x) || !onWater(x, y)) continue;
    g.fillStyle = kit.css(look(kit).glint, 0.85);
    g.fillRect(x, y, 6 + u * 16, 2);
  }
}

export function paintSlope(kit, g, w, topAt, h, seed, { lit = 0.5 } = {}) {
  const r = kit.rng(seed);
  const top = (x) => topAt(x);
  // the big shape: lit at the crest, cooling and going violet toward the foot
  for (let x = 0; x < w; x += 3) {
    const y0 = top(x);
    const grd = g.createLinearGradient(0, y0, 0, y0 + h);
    const G = look(kit).grass;
    grd.addColorStop(0, kit.css(kit.mix(G.base, G.lit, lit)));
    grd.addColorStop(0.45, kit.css(kit.mix(G.dark, G.mid, lit * 0.6)));
    grd.addColorStop(1, kit.css(G.foot));
    g.fillStyle = grd;
    g.fillRect(x, y0, 3, h);
  }
  // broad patches of colour so the slope is not one gradient
  kit.mottle(g, 0, top(w / 2) - 40, w, h + 80, (x, y) => {
    const u = kit.clamp((y - top(x)) / h);
    const G2 = look(kit).grass;
    return kit.mix(kit.mix(G2.patch, G2.patchDark, u), G2.shade, u * 0.3);
  }, { n: Math.round(w * h / 9000), size: 120, alpha: 0.12, r, angle: -0.2 });
  // strokes down the slope: fewer, light, each its own length; quiet patches left alone
  for (let i = 0; i < w * h / 2600; i++) {
    const x = r() * w;
    const y = top(x) + r() * h;
    const u = (y - top(x)) / h;
    if (Math.sin(x * 0.004 + y * 0.01) > 0.55) continue;
    const G3 = look(kit).grass;
    const col = kit.mix(kit.mix(G3.stroke, G3.strokeDark, u), G3.cool, u * 0.25);
    const L = 10 + r() * 26 * (0.5 + u);
    kit.stroke(g, [[x, y], [x + 4 + r() * 6, y + L * 0.5], [x + 6 + r() * 8, y + L]], { width: 4 + u * 7, color: col, alpha: 0.3, r, bristles: 3 });
  }
}

export function paintRoad(kit, g, w, topAt, depth, seed) {
  const r = kit.rng(seed);
  for (let x = 0; x < w; x += 2) {
    const top = topAt(x);
    g.fillStyle = kit.css(kit.mix(look(kit).road.light, look(kit).road.base, 0.3));
    g.fillRect(x, top, 2, depth(x));
  }
  for (let i = 0; i < w * 1.2; i++) {
    const x = r() * w;
    const y = topAt(x) + r() * depth(x);
    g.fillStyle = kit.css(kit.jit(r() < 0.6 ? look(kit).road.light : look(kit).road.dark, r, 20), 0.7);
    g.fillRect(x, y, 1.5 + r() * 4, 1 + r() * 2);
  }
  // the near verge catches the light
  for (let x = 0; x < w; x += 2) {
    g.fillStyle = look(kit).road.verge;
    g.fillRect(x, topAt(x), 2, 2);
  }
}

/** Reeds with plumed heads, each blade drawn as its own curve; sway on twos. */
export function reeds(kit, g, t, specs, seed, { backlit = false } = {}) {
  const r = kit.rng(seed);
  const d = kit.twos(t);
  for (const [x0, x1, base, hMin, hMax, n] of specs) {
    for (let i = 0; i < n; i++) {
      const x = x0 + r() * (x1 - x0);
      const hgt = hMin + r() * (hMax - hMin);
      const ph = r() * 6.28;
      const sway = (Math.sin(d * 1.6 + ph + x * 0.004) * 0.6 + Math.sin(d * 3.7 + ph * 2) * 0.2) * (0.06 + r() * 0.05) * hgt;
      const tipX = x + sway + (r() - 0.5) * 20;
      const tipY = base - hgt;
      const R = look(kit).reeds;
      const col = backlit ? kit.mix(R.stemBacklit[0], R.stemBacklit[1], r()) : kit.mix(R.stem[0], R.stem[1], r());
      kit.ink(g, [[x, base, 4], [x + sway * 0.4, base - hgt * 0.55, 3], [tipX, tipY, 1.4]], kit.css(col));
      if (r() < 0.55) {
        // the plume
        const pc = backlit ? R.plumeBacklit : R.plume;
        for (let k = 0; k < 6; k++) {
          const a = -1.9 + (k / 6) * 0.9 + sway * 0.004;
          kit.ink(g, [[tipX, tipY, 2.5], [tipX + Math.cos(a) * 26, tipY + Math.sin(a) * 26 + 10, 0.8]], kit.css(pc, 0.8));
        }
      }
    }
  }
}


export function lerp(a, b, t) {
  return a + (b - a) * t;
}
