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
  houseWalls: ['#5a5f80', '#6a5a6e', '#4e6070', '#6e6458', '#585470', '#62586a'], roofShade: '#2e3048', windowsBright: '#ffe2a8',
  stone: { mortar: '#3c3a50', block: '#605e78', block2: '#6e6a7e', moss: '#5e7050' },
  archBridge: { body: '#5e5c74', block: '#66647e', edge: '#3e3c54', parapet: '#54526c' },
  cobble: { gap: '#34304a', stone: '#66607a', dark: '#57506a', light: '#8a7e8e', sheen: '#c9a6a0' },
  lamp: { iron: '#2e2a3a', glass: '#6a6070', lit: '#fff0c8' },
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

// ---------- town, stone and weather ----------

/**
 * A row of houses, each different: height, width, roof, colour. Painted, not blocked in: walls with
 * vertical brushwork, lighter at the top; eaves with a shadow under them, capped chimneys; windows
 * with sills and lintels, some shuttered, some with glazing bars, each lit its own way; doors on the
 * ground floor. `light` is the side the sun is on (1 right, -1 left, 0 none): that edge catches it.
 * Returns the chimney tops, for smoke.
 */
export function paintHouses(kit, g, x0, x1, base, seed, { reflect = 0, haze = 0, light = 0 } = {}) {
  const r = kit.rng(seed);
  // details come from their own stream, so adding them never moves a house
  const d = kit.rng(seed * 7 + 13);
  const L = look(kit);
  const walls = L.houseWalls;
  const parts = [];
  for (let x = x0; x < x1; ) {
    const w = 60 + r() * 120;
    const h = 70 + r() * 170;
    parts.push({ x, w, h, roof: ['gable', 'gable', 'flat', 'hip'][Math.floor(r() * 4)], pitch: 18 + r() * 40,
      col: kit.jit(walls[Math.floor(r() * walls.length)], r, 10), chimney: r() < 0.45 ? r() : -1,
      win: Array.from({ length: 24 }, () => r()), cols: 1 + Math.floor(w / 42), rows: Math.max(1, Math.floor((h - 30) / 44)), ww: 10 + r() * 8,
      shutters: d() < 0.35 ? kit.jit(kit.mix(L.roofShade, '#6f8a7a', d()), d, 12) : null,
      bars: d() < 0.6, door: w > 72 ? 0.2 + d() * 0.6 : -1, cornice: d() < 0.5, seed: Math.floor(d() * 1e6) });
    x += w + 2 + r() * 14;
  }
  const chimneys = [];
  const draw = (flip) => {
    const sy = flip ? -1 : 1;
    const a = flip ? 0.45 : 1;
    for (const p of parts) {
      const top = base - sy * p.h;
      const dr = kit.rng(p.seed);
      g.fillStyle = kit.css(p.col, a);
      g.fillRect(p.x, Math.min(base, top), p.w, p.h);
      if (!flip) {
        // the wall: lighter toward the eaves, darker at the street, brushed in vertical strokes
        const grad = g.createLinearGradient(0, top, 0, base);
        grad.addColorStop(0, kit.css(kit.mix(p.col, '#fff4e0', 0.12), 0.9));
        grad.addColorStop(1, kit.css(kit.mix(p.col, L.roofShade, 0.22), 0.9));
        g.fillStyle = grad;
        g.fillRect(p.x, top, p.w, p.h);
        g.save();
        g.beginPath();
        g.rect(p.x, top, p.w, p.h);
        g.clip();
        kit.mottle(g, p.x, top, p.w, p.h, () => kit.jit(p.col, dr, 14), { n: Math.max(6, Math.round((p.w * p.h) / 700)), size: 18, alpha: 0.16, r: dr, angle: Math.PI / 2 });
        g.restore();
        // the edge toward the sun catches it; the other side stays a touch darker
        if (light) {
          const lx = light > 0 ? p.x + p.w - 4 : p.x;
          g.fillStyle = kit.css(kit.mix(p.col, L.windowsBright, 0.45), 0.55);
          g.fillRect(lx, top, 4, p.h);
          g.fillStyle = kit.css(L.roofShade, 0.12);
          g.fillRect(light > 0 ? p.x : p.x + p.w - 6, top, 6, p.h);
        }
        if (p.cornice) {
          g.fillStyle = kit.css(kit.mix(p.col, '#fff4e0', 0.25), 0.8);
          g.fillRect(p.x - 2, top + 4, p.w + 4, 3);
        }
        // the shadow under the eaves
        g.fillStyle = kit.css(L.roofShade, 0.35);
        g.fillRect(p.x, top, p.w, 7);
      }
      // the roof
      const rc = kit.css(kit.mix(p.col, L.roofShade, 0.45), a);
      g.beginPath();
      if (p.roof === 'gable') {
        g.moveTo(p.x - 8, top);
        g.lineTo(p.x + p.w / 2, top - sy * p.pitch);
        g.lineTo(p.x + p.w + 8, top);
      } else if (p.roof === 'hip') {
        g.moveTo(p.x - 8, top);
        g.lineTo(p.x + p.w * 0.25, top - sy * p.pitch * 0.6);
        g.lineTo(p.x + p.w * 0.75, top - sy * p.pitch * 0.6);
        g.lineTo(p.x + p.w + 8, top);
      } else {
        g.rect(p.x - 5, top - sy * 8, p.w + 10, sy * 8);
      }
      g.closePath();
      g.fillStyle = rc;
      g.fill();
      if (!flip && p.roof !== 'flat') {
        // courses of tiles, following the slope, and a lit ridge on the sun side
        g.save();
        g.clip();
        g.strokeStyle = kit.css(L.roofShade, 0.35);
        g.lineWidth = 1.2;
        for (let k = 1; k < 5; k++) {
          const y = top - (p.pitch * (p.roof === 'hip' ? 0.6 : 1) * k) / 5;
          g.beginPath();
          g.moveTo(p.x - 8, y);
          g.lineTo(p.x + p.w + 8, y);
          g.stroke();
        }
        if (light) {
          g.fillStyle = kit.css(L.windowsBright, 0.18);
          g.fillRect(light > 0 ? p.x + p.w / 2 : p.x - 8, top - p.pitch, p.w / 2 + 8, p.pitch);
        }
        g.restore();
        g.strokeStyle = kit.css(L.roofShade, 0.8);
        g.lineWidth = 2;
        g.beginPath();
        g.moveTo(p.x - 8, top);
        g.lineTo(p.x + p.w + 8, top);
        g.stroke();
      }
      if (p.chimney >= 0) {
        const cx = p.x + p.w * (0.2 + p.chimney * 0.5);
        const cy = top - sy * (p.pitch * 0.5 + 22);
        g.fillStyle = rc;
        g.fillRect(cx, cy, 12, sy * 26);
        // the cap
        g.fillRect(cx - 3, cy - sy * 4, 18, sy * 5);
        if (!flip) chimneys.push([cx + 6, cy - 4]);
      }
      // windows: not a grid of lights; some lit, some dark, sizes per house
      let k = 0;
      for (let i = 0; i < p.rows; i++) {
        for (let j = 0; j < p.cols; j++) {
          const v = p.win[k++ % p.win.length];
          const wx = p.x + 10 + j * ((p.w - 20) / p.cols) + 2;
          const wy = base - sy * (30 + i * 44) - (flip ? 0 : p.ww * 1.4);
          if (v < 0.25) continue;
          const wh = p.ww * 1.4;
          if (p.door >= 0 && i === 0 && Math.abs(wx + p.ww / 2 - (p.x + p.w * p.door)) < p.ww) continue;
          const lit = v > 0.62;
          g.fillStyle = lit ? kit.css(kit.mix(L.windows, L.windowsBright, v - 0.62), 0.9 * a) : kit.css(L.roofShade, 0.7 * a);
          g.fillRect(wx, wy, p.ww, wh);
          if (flip) continue;
          if (lit) {
            // the light is warmest low in the room
            const lg = g.createLinearGradient(0, wy, 0, wy + wh);
            lg.addColorStop(0, kit.css(L.roofShade, 0.25));
            lg.addColorStop(1, kit.css(L.windowsBright, 0.25));
            g.fillStyle = lg;
            g.fillRect(wx, wy, p.ww, wh);
          }
          if (p.bars) {
            g.fillStyle = kit.css(L.roofShade, lit ? 0.55 : 0.3);
            g.fillRect(wx + p.ww / 2 - 0.8, wy, 1.6, wh);
            g.fillRect(wx, wy + wh * 0.45, p.ww, 1.6);
          }
          // sill below, lintel above
          g.fillStyle = kit.css(kit.mix(p.col, '#fff4e0', 0.35), 0.85);
          g.fillRect(wx - 2, wy + wh, p.ww + 4, 3);
          g.fillStyle = kit.css(L.roofShade, 0.4);
          g.fillRect(wx - 1, wy - 3, p.ww + 2, 2);
          if (p.shutters) {
            g.fillStyle = kit.css(p.shutters, 0.9);
            g.fillRect(wx - p.ww * 0.45 - 1, wy, p.ww * 0.42, wh);
            g.fillRect(wx + p.ww + 1, wy, p.ww * 0.42, wh);
          }
        }
      }
      if (!flip && p.door >= 0) {
        // a door with a rounded head and a step
        const dw = 16 + (p.seed % 7);
        const dh = 34 + (p.seed % 9);
        const dx = p.x + p.w * p.door - dw / 2;
        g.fillStyle = kit.css(kit.mix(L.roofShade, p.col, 0.25), 0.95);
        g.beginPath();
        g.moveTo(dx, base);
        g.lineTo(dx, base - dh + dw / 2);
        g.arc(dx + dw / 2, base - dh + dw / 2, dw / 2, Math.PI, 0);
        g.lineTo(dx + dw, base);
        g.closePath();
        g.fill();
        g.fillStyle = kit.css(kit.mix(p.col, '#fff4e0', 0.3), 0.8);
        g.fillRect(dx - 3, base - 3, dw + 6, 3);
      }
    }
  };
  draw(false);
  if (reflect) {
    g.save();
    g.globalAlpha = reflect;
    draw(true);
    g.restore();
  }
  if (haze) {
    g.fillStyle = `rgba(150,150,180,${haze})`;
    g.fillRect(x0, base - 300, x1 - x0, 300);
  }
  return { chimneys };
}

/**
 * Smoke from a chimney top at (x, y): puffs that rise, widen, thin out and lean with the wind,
 * cycling on twos. `scale` for distance, `wind` for the lean (negative leans left).
 */
export function smoke(kit, g, t, x, y, { scale = 1, wind = 1, alpha = 0.5, seed = 1, color = [222, 212, 226] } = {}) {
  const r = kit.rng(900 + seed * 13);
  const ph = r();
  const tw = kit.twos(t);
  const [cr, cg, cb] = color;
  for (let p = 0; p < 8; p++) {
    const u = (tw * 0.3 + p / 8 + ph) % 1;
    const al = alpha * (1 - u) * Math.min(1, u * 6);
    const px = x + scale * (wind * u * u * 150 + 10 * Math.sin(u * 6 + ph * 6));
    const py = y - scale * u * 230;
    const rad = scale * (9 + u * 40);
    const grd = g.createRadialGradient(px - rad * 0.2, py - rad * 0.2, 1, px, py, rad);
    grd.addColorStop(0, `rgba(${cr},${cg},${cb},${al})`);
    grd.addColorStop(0.6, `rgba(${cr - 26},${cg - 28},${cb - 16},${al * 0.7})`);
    grd.addColorStop(1, `rgba(${cr - 40},${cg - 42},${cb - 25},0)`);
    g.fillStyle = grd;
    g.beginPath();
    g.arc(px, py, rad, 0, Math.PI * 2);
    g.fill();
  }
}

/**
 * Ground mist between y0 (its top) and y1 (the ground): densest at the ground, soft at the top,
 * broken into drifting patches. `drift` moves the patches sideways (pass t times a speed).
 */
export function paintMist(kit, g, y0, y1, seed, { color = [226, 218, 230], alpha = 0.45, drift = 0, w = 1920 } = {}) {
  const [cr, cg, cb] = color;
  const band = g.createLinearGradient(0, y0, 0, y1);
  band.addColorStop(0, `rgba(${cr},${cg},${cb},0)`);
  band.addColorStop(0.7, `rgba(${cr},${cg},${cb},${alpha * 0.6})`);
  band.addColorStop(1, `rgba(${cr},${cg},${cb},${alpha})`);
  g.fillStyle = band;
  g.fillRect(0, y0, w, y1 - y0);
  const r = kit.rng(seed);
  const h = y1 - y0;
  for (let i = 0; i < 14; i++) {
    const cx = ((((r() * (w + 800) + drift) % (w + 800)) + (w + 800)) % (w + 800)) - 400;
    const cy = y0 + h * (0.35 + r() * 0.6);
    const rx = 220 + r() * 380;
    const ry = h * (0.15 + r() * 0.25);
    const al = alpha * (0.25 + r() * 0.35);
    g.save();
    g.translate(cx, cy);
    g.scale(1, ry / rx);
    const grd = g.createRadialGradient(0, 0, 1, 0, 0, rx);
    grd.addColorStop(0, `rgba(${cr},${cg},${cb},${al})`);
    grd.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
    g.fillStyle = grd;
    g.beginPath();
    g.arc(0, 0, rx, 0, Math.PI * 2);
    g.fill();
    g.restore();
  }
}

/** A stone wall: blocks of different widths, mortar, wet streaks and moss; quiet, not a tiled pattern. */
export function paintWall(kit, g, y0, y1, seed) {
  const r = kit.rng(seed);
  const S = look(kit).stone;
  g.fillStyle = kit.css(S.mortar);
  g.fillRect(0, y0, 1920, y1 - y0);
  for (let y = y0; y < y1; ) {
    const h = 24 + r() * 14;
    for (let x = -r() * 60; x < 1920; ) {
      const w = 40 + r() * 90;
      const col = kit.mix(kit.jit(S.block, r, 16), S.block2, r() * 0.4);
      g.beginPath();
      const rad = 4 + r() * 4;
      g.roundRect(x + 2, y + 2, w - 3, h - 3, rad);
      g.fillStyle = kit.css(col);
      g.fill();
      if (r() < 0.12) {
        g.fillStyle = kit.css(S.moss, 0.55);
        g.fillRect(x + 4, y + h - 8, w * (0.3 + r() * 0.5), 6);
      }
      x += w;
    }
    y += h;
  }
  // rain has run down the wall in streaks
  for (let i = 0; i < 60; i++) {
    const x = r() * 1920;
    g.fillStyle = 'rgba(30,30,50,0.12)';
    g.fillRect(x, y0, 3 + r() * 6, (y1 - y0) * (0.3 + r() * 0.7));
  }
  g.fillStyle = 'rgba(255,214,170,0.3)';
  g.fillRect(0, y0 - 2, 1920, 3);
}

export function paintArchBridge(kit, g, x0, x1, deck, water, seed) {
  const r = kit.rng(seed);
  const cx = (x0 + x1) / 2;
  const R = (x1 - x0) / 2 - 60;
  const body = new Path2D();
  body.rect(x0, deck - 30, x1 - x0, water - deck + 40);
  const arch = new Path2D();
  arch.ellipse(cx, water + 10, R, water - deck - 10, 0, Math.PI, 0);
  arch.lineTo(cx + R, water + 40);
  arch.lineTo(cx - R, water + 40);
  arch.closePath();
  g.save();
  const B = look(kit).archBridge;
  g.fillStyle = kit.css(B.body);
  g.fill(body);
  // stones
  g.clip(body);
  for (let y = deck - 30; y < water + 40; y += 16) {
    for (let x = x0 + ((y / 16) % 2) * 18; x < x1; x += 36) {
      g.fillStyle = kit.css(kit.jit(B.block, r, 12));
      g.fillRect(x + 1, y + 1, 34, 14);
    }
  }
  g.restore();
  // the arch opening shows the water and sky behind
  g.save();
  g.clip(arch);
  g.fillStyle = kit.css(look(kit).water);
  g.fillRect(x0, deck, x1 - x0, water - deck + 60);
  g.restore();
  g.lineWidth = 3;
  g.strokeStyle = kit.css(B.edge);
  g.stroke(arch);
  // parapet and its lit top edge
  g.fillStyle = kit.css(B.parapet);
  g.fillRect(x0 - 10, deck - 52, x1 - x0 + 20, 24);
  g.fillStyle = 'rgba(255,214,170,0.35)';
  g.fillRect(x0 - 10, deck - 52, x1 - x0 + 20, 3);
}

/** Cobblestones in rows that shrink toward the horizon: each its own size and turn, wet, catching the sky. */
export function paintCobbles(kit, g, y0, y1, w, seed, sheen = look(kit).cobble.sheen) {
  const r = kit.rng(seed);
  const CB = look(kit).cobble;
  g.fillStyle = kit.css(CB.gap);
  g.fillRect(0, y0, w, y1 - y0);
  let y = y0;
  while (y < y1) {
    const u = (y - y0) / (y1 - y0);
    const h = 9 + u * 30;
    let x = -r() * 30;
    while (x < w) {
      const sw = h * (1.0 + r() * 1.1);
      const hh = h * (0.75 + r() * 0.3);
      const col = kit.mix(kit.jit(CB.stone, r, 20), r() < 0.3 ? CB.dark : CB.light, r() * 0.35);
      const cx = x + sw / 2 + (r() - 0.5) * 3;
      const cy = y + h / 2 + (r() - 0.5) * 3;
      const rot = (r() - 0.5) * 0.25;
      g.beginPath();
      const k = 10;
      for (let i = 0; i <= k; i++) {
        const a = (i / k) * Math.PI * 2;
        const rr = 1 + (r() - 0.5) * 0.12;
        const px = Math.cos(a) * (sw / 2 - 2) * rr;
        const py = Math.sin(a) * (hh / 2 - 1.5) * rr;
        g.lineTo(cx + px * Math.cos(rot) - py * Math.sin(rot), cy + px * Math.sin(rot) + py * Math.cos(rot));
      }
      g.closePath();
      g.fillStyle = kit.css(col);
      g.fill();
      if (r() < 0.7) {
        g.beginPath();
        g.ellipse(cx - sw * 0.08, cy - hh * 0.18, sw * (0.2 + r() * 0.15), hh * 0.12, rot, 0, Math.PI * 2);
        g.fillStyle = kit.css(sheen, 0.2 + r() * 0.25);
        g.fill();
      }
      x += sw + 1 + r() * 2;
    }
    y += h * 0.85 + 1;
  }
}

export function paintPuddle(kit, g, cx, cy, rx, ry, seed) {
  g.save();
  g.beginPath();
  g.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  g.clip();
  const grd = g.createLinearGradient(0, cy - ry, 0, cy + ry);
  // a puddle mirrors the sky: its low, bright end above, the higher sky below
  grd.addColorStop(0, kit.css(kit.ramp(look(kit).sky, 1)));
  grd.addColorStop(1, kit.css(kit.ramp(look(kit).sky, 0.5)));
  g.fillStyle = grd;
  g.globalAlpha = 0.65;
  g.fillRect(cx - rx, cy - ry, rx * 2, ry * 2);
  g.restore();
}

/** Ripples in a puddle: rings born every so often, spreading and fading; drawn on twos. */
export function ripples(kit, g, t, cx, cy, rx, ry, seed, rate = 2.2) {
  const d = kit.twos(t);
  const r = kit.rng(seed);
  const births = [];
  for (let k = 0; k < 40; k++) births.push([k / rate + r() * 0.4, (r() - 0.5) * rx * 1.4, (r() - 0.5) * ry * 1.2]);
  g.save();
  g.beginPath();
  g.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  g.clip();
  for (const [b, ox, oy] of births) {
    const age = d - b;
    if (age < 0 || age > 0.9) continue;
    g.beginPath();
    g.ellipse(cx + ox, cy + oy, 4 + age * 40, (4 + age * 40) * (ry / rx) * 0.9, 0, 0, Math.PI * 2);
    g.lineWidth = 1.5;
    g.strokeStyle = `rgba(255,240,225,${0.5 * (1 - age / 0.9)})`;
    g.stroke();
  }
  g.restore();
}

/** Light rain: thin streaks falling at a slant, a new drawing twelve times a second. */
export function rain(kit, g, t, amount, seed) {
  if (amount <= 0) return;
  const d = kit.twos(t);
  const r = kit.rng(seed);
  g.save();
  g.lineCap = 'round';
  for (let i = 0; i < 220 * amount; i++) {
    const x0 = r() * 2100 - 100;
    const v = 1400 + r() * 500;
    const y = ((r() * 1300 + d * v) % 1300) - 120;
    const x = x0 - (y + 120) * 0.18;
    const L = 22 + r() * 20;
    g.beginPath();
    g.moveTo(x, y);
    g.lineTo(x - L * 0.18, y + L);
    g.lineWidth = 1.2;
    g.strokeStyle = `rgba(220,230,245,${0.18 + r() * 0.2})`;
    g.stroke();
  }
  g.restore();
}

export function lampPost(kit, g, x, ground, top, on) {
  // iron post
  const LP = look(kit).lamp;
  kit.ink(g, [[x, ground, 14], [x, top + 60, 10], [x + 4, top + 20, 8]], LP.iron);
  kit.ink(g, [[x, top + 30, 5], [x + 50, top + 6, 4], [x + 80, top + 24, 3]], LP.iron);
  const lx = x + 86;
  const ly = top + 52;
  // the lantern
  const lantern = new Path2D();
  lantern.moveTo(lx - 22, ly - 24);
  lantern.lineTo(lx + 22, ly - 24);
  lantern.lineTo(lx + 16, ly + 22);
  lantern.lineTo(lx - 16, ly + 22);
  lantern.closePath();
  g.fillStyle = on > 0 ? kit.css(kit.mix(LP.glass, LP.lit, on)) : LP.glass;
  g.fill(lantern);
  g.lineWidth = 3;
  g.strokeStyle = LP.iron;
  g.stroke(lantern);
  g.fillStyle = LP.iron;
  g.fillRect(lx - 26, ly - 30, 52, 8);
  return [lx, ly];
}

/**
 * A low sun shining into the lens: a warm glow that lifts everything near it (screen blend), and a
 * few soft rays fanning down through haze. Call it after the background and before the characters,
 * so they stand dark against it. `strength` 0..1 can rise over a shot as the sun comes up.
 */
export function sunGlow(kit, g, [sx, sy], { strength = 1, rays = 7, seed = 1, color = [255, 206, 150], w = 1920, h = 1080 } = {}) {
  const [cr, cg, cb] = color;
  g.save();
  g.globalCompositeOperation = 'screen';
  const glow = g.createRadialGradient(sx, sy, 10, sx, sy, Math.max(w, h) * 0.6);
  glow.addColorStop(0, `rgba(${cr},${cg},${cb},${0.55 * strength})`);
  glow.addColorStop(0.35, `rgba(${cr},${cg},${cb},${0.18 * strength})`);
  glow.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
  g.fillStyle = glow;
  g.fillRect(0, 0, w, h);
  const r = kit.rng(seed);
  for (let i = 0; i < rays; i++) {
    // rays fan downward and away from the sun, each its own width and strength
    const a = Math.PI / 2 + (r() - 0.5) * 2.2;
    const len = h * (0.6 + r() * 0.6);
    const spread = 0.03 + r() * 0.05;
    const ex = sx + Math.cos(a) * len;
    const ey = sy + Math.sin(a) * len;
    const ray = g.createLinearGradient(sx, sy, ex, ey);
    ray.addColorStop(0, `rgba(${cr},${cg},${cb},${(0.1 + r() * 0.1) * strength})`);
    ray.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
    g.fillStyle = ray;
    g.beginPath();
    g.moveTo(sx, sy);
    g.lineTo(sx + Math.cos(a - spread) * len, sy + Math.sin(a - spread) * len);
    g.lineTo(sx + Math.cos(a + spread) * len, sy + Math.sin(a + spread) * len);
    g.closePath();
    g.fill();
  }
  g.restore();
}
