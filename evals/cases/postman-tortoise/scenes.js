// "The postman after the rain": the tortoise and the three shots.
// Sky, clouds, water, glints and cel shapes come from the engine's painters; this file only holds
// what is particular to this film: the tortoise, the canal town, the cobbles, the rain, the mailbox, the lamp.
import { path, cel, line, groundShadow, paintSky, paintClouds, paintRiver, glitter } from '/runtime/painters.js';

const INK = '#3b2a2e';
const T = {
  shell: '#6f8a4a', shellShade: '#4b6236', shellRim: '#b8c27a', scute: 'rgba(52,70,36,0.75)', rim: '#a3a860',
  skin: '#b8a27a', skinShade: '#86745a', skinRim: '#f2deb0', eye: '#2a1e24',
  strap: '#8a5a3a', leaf: '#5f8f4f', leafShade: '#3f6a3a', leafRim: '#a8d08a', stem: '#6a8a4a',
  letter: '#f4ecdc', letterShade: '#cfc3b4', seal: '#b23a32',
  box: '#a8423a', boxShade: '#7a2e2a', boxRim: '#e07a5a', wood: '#7a5a42', brass: '#d8b45a',
};

// ---------- the tortoise, in profile facing right ----------
// Origin on the ground under the middle of the shell, units in pixels at scale 1.
const CYCLE = 0.9; // seconds per full walk cycle
const LEGS = [
  // [hip x, phase offset, near?]: diagonal pairs move together
  [62, 0, false], [-58, Math.PI, false], [62, Math.PI, true], [-58, 0, true],
];

function leg(kit, g, hx, phase, walking, near, s) {
  const swing = walking ? 34 * Math.sin(phase) : 0;
  const lift = walking ? Math.max(0, Math.cos(phase)) * 12 : 0;
  const top = [hx, -30];
  const foot = [hx + swing, -lift];
  const base = near ? T.skin : T.skinShade;
  const { P, q } = path(kit, [[top[0] - 16, top[1]], [top[0] + 16, top[1]], [foot[0] + 18, foot[1] - 4], [foot[0] + 20, foot[1]], [foot[0] - 16, foot[1]], [foot[0] - 16, foot[1] - 6]]);
  cel(g, P, { base, shade: T.skinShade, light: [-0.6, -0.8], sd: 6 });
  line(kit, g, q, 2.2, Math.round(hx) + (near ? 1 : 2));
  // three toe nails
  for (let k = 0; k < 3; k++) kit.ink(g, [[foot[0] + 6 + k * 6, foot[1] - 2, 2], [foot[0] + 10 + k * 6, foot[1] + 1, 0.8]], '#e8dcc0');
}

/**
 * pose: { phase (walk cycle angle), walking, bob, neck (0 = tucked, 1 = stretched to the slot),
 *         look (0..1 head raised), leafLag, letter (true while carrying), light: [x, y] toward the light }
 */
export function tortoise(kit, g, x, y, s, pose) {
  const { phase = 0, walking = false, bob = 0, neck = 0, push = 0, look = 0, leafLag = 0, letter = true, light = [-0.6, -0.8] } = pose;
  g.save();
  g.translate(x, y);
  g.scale(s, s);
  const far = LEGS.filter(([, , n]) => !n);
  const near = LEGS.filter(([, , n]) => n);
  for (const [hx, off] of far) leg(kit, g, hx, phase + off, walking, false, s);

  g.translate(0, -bob);
  // tail
  const tail = path(kit, [[-108, -30], [-134, -22], [-108, -18]]);
  cel(g, tail.P, { base: T.skin, shade: T.skinShade, light, sd: 3 });
  line(kit, g, tail.q, 1.8, 3);

  // neck and head: tucked, or stretched up and forward to the slot, or raised to look at the lamp
  const hx = 150 + neck * 52 + push * 22 + look * -6;
  const hy = -70 - neck * 98 - look * 40;
  const neckShape = path(kit, [[86, -70], [hx - 26, hy - 12], [hx - 18, hy + 14], [96, -38]]);
  cel(g, neckShape.P, { base: T.skin, shade: T.skinShade, rim: T.skinRim, light, sd: 7, rw: 2 });
  line(kit, g, neckShape.q, 2.2, 4);
  const tilt = -look * 0.5;
  g.save();
  g.translate(hx, hy);
  g.rotate(tilt);
  const head = path(kit, [[-30, -6], [-14, -24], [14, -24], [34, -10], [38, 4], [26, 14], [-20, 14]]);
  cel(g, head.P, { base: T.skin, shade: T.skinShade, rim: T.skinRim, light, sd: 6, rw: 2 });
  line(kit, g, head.q, 2.4, 5);
  // beak line and a small smile
  kit.ink(g, [[18, 4, 1.2], [30, 6, 1.6], [38, 3, 1]], INK);
  g.beginPath();
  g.ellipse(10, -9, 5, 6, 0, 0, Math.PI * 2);
  g.fillStyle = T.eye;
  g.fill();
  g.beginPath();
  g.arc(12, -11, 1.8, 0, Math.PI * 2);
  g.fillStyle = '#fff6e0';
  g.fill();
  kit.ink(g, [[2, -16, 1.2], [10, -19, 1.8], [18, -16, 1.2]], INK);
  if (letter) {
    // the envelope, held in the beak
    g.save();
    g.translate(42, 8);
    // tilted while carried, level when it goes into the slot
    g.rotate(0.18 * (1 - neck) - tilt);
    const env = path(kit, [[-6, -14], [46, -14], [46, 18], [-6, 18]]);
    cel(g, env.P, { base: T.letter, shade: T.letterShade, light: [-0.6, -0.8], sd: 5 });
    line(kit, g, env.q, 1.8, 6);
    kit.ink(g, [[-4, -12, 1.2], [20, 4, 1.6], [44, -12, 1.2]], 'rgba(90,70,60,0.7)');
    g.beginPath();
    g.arc(20, 4, 4.5, 0, Math.PI * 2);
    g.fillStyle = T.seal;
    g.fill();
    g.restore();
  }
  g.restore();

  // the shell: dome, plates, a lighter rim
  const shell = path(kit, [[-114, -26], [-104, -82], [-62, -128], [0, -146], [62, -128], [104, -84], [116, -26], [70, -18], [-70, -18]]);
  cel(g, shell.P, { base: T.shell, shade: T.shellShade, rim: T.shellRim, light, sd: 18, rw: 4 });
  g.save();
  g.clip(shell.P);
  g.lineWidth = 2.2;
  g.strokeStyle = T.scute;
  for (const xs of [-58, 0, 58]) {
    g.beginPath();
    g.moveTo(xs - 26, -40);
    g.lineTo(xs - 30, -92);
    g.lineTo(xs, -112);
    g.lineTo(xs + 30, -92);
    g.lineTo(xs + 26, -40);
    g.closePath();
    g.stroke();
  }
  g.fillStyle = T.rim;
  g.fillRect(-130, -36, 260, 16);
  g.restore();
  line(kit, g, shell.q, 2.8, 7);
  // the strap, and the lotus-leaf umbrella tucked into it; the leaf lags the body a little
  kit.ink(g, [[-52, -122, 9], [-8, -76, 9], [36, -24, 9]], T.strap);
  const stemTop = [-70 - leafLag * 6, -238];
  kit.ink(g, [[-34, -118, 5], [-50, -180, 4], [stemTop[0], stemTop[1], 3]], T.stem);
  const lw = 104;
  const leaf = path(kit, [[stemTop[0] - lw, stemTop[1] + 26 + leafLag * 4], [stemTop[0] - lw * 0.6, stemTop[1] - 12], [stemTop[0], stemTop[1] - 22], [stemTop[0] + lw * 0.6, stemTop[1] - 12], [stemTop[0] + lw, stemTop[1] + 26 - leafLag * 4], [stemTop[0], stemTop[1] + 8]]);
  cel(g, leaf.P, { base: T.leaf, shade: T.leafShade, rim: T.leafRim, light, sd: 10, rw: 3 });
  for (let k = -3; k <= 3; k++) kit.ink(g, [[stemTop[0], stemTop[1] + 2, 1.6], [stemTop[0] + k * lw * 0.28, stemTop[1] + 18 - Math.abs(k) * 6, 0.8]], 'rgba(40,70,40,0.7)');
  line(kit, g, leaf.q, 2.4, 8);
  // two drops sitting on the leaf
  for (const [dx, dy] of [[-40, 4], [28, 2]]) {
    g.beginPath();
    g.ellipse(stemTop[0] + dx, stemTop[1] + dy, 5, 4, 0, 0, Math.PI * 2);
    g.fillStyle = 'rgba(220,240,255,0.8)';
    g.fill();
  }
  g.translate(0, bob);
  for (const [hx2, off] of near) leg(kit, g, hx2, phase + off, walking, true, s);
  g.restore();
}

/** Walking from x0 to x1 between t0 and t1, then standing. Footfalls are reported as cues. */
function walk(kit, t, { x0, x1, t0 = 0, t1 }) {
  const d = kit.twos(t);
  const walking = d < t1;
  const u = kit.clamp((d - t0) / (t1 - t0));
  const x = x0 + (x1 - x0) * u;
  const phase = walking ? ((d - t0) / CYCLE) * Math.PI * 2 : 0;
  const bob = walking ? 3 * Math.abs(Math.sin(phase)) : 0;
  const leafLag = walking ? Math.sin(phase * 2 - 1) : Math.exp(-(d - t1) * 4) * Math.sin((d - t1) * 14);
  return { x, phase, walking, bob, leafLag };
}

/** Footfall times for a walk: each leg lands when its lift reaches zero, on a drawing (twos). */
function footfalls(t0, t1) {
  const out = [];
  for (const [, off] of LEGS) {
    for (let k = -1; ; k++) {
      // lift = max(0, cos(phase + off)); it touches down when phase + off = pi/2 + 2 pi k
      const phase = Math.PI / 2 + 2 * Math.PI * k - off;
      const t = t0 + (phase / (2 * Math.PI)) * CYCLE;
      if (t >= t1) break;
      if (t > t0 + 0.05) out.push(Math.ceil(t * 12 - 1e-6) / 12);
    }
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

// ---------- painted things particular to this film ----------
function houses(kit, g, x0, x1, base, seed, { reflect = 0, haze = 0 } = {}) {
  const r = kit.rng(seed);
  const walls = ['#5a5f80', '#6a5a6e', '#4e6070', '#6e6458', '#585470', '#62586a'];
  const parts = [];
  for (let x = x0; x < x1; ) {
    const w = 60 + r() * 120;
    const h = 70 + r() * 170;
    parts.push({ x, w, h, roof: ['gable', 'gable', 'flat', 'hip'][Math.floor(r() * 4)], pitch: 18 + r() * 40,
      col: kit.jit(walls[Math.floor(r() * walls.length)], r, 10), chimney: r() < 0.45 ? r() : -1,
      win: Array.from({ length: 24 }, () => r()), cols: 1 + Math.floor(w / 42), rows: Math.max(1, Math.floor((h - 30) / 44)), ww: 10 + r() * 8 });
    x += w + 2 + r() * 14;
  }
  const draw = (flip) => {
    const sy = flip ? -1 : 1;
    const a = flip ? 0.45 : 1;
    for (const p of parts) {
      const top = base - sy * p.h;
      g.fillStyle = kit.css(p.col, a);
      g.fillRect(p.x, Math.min(base, top), p.w, p.h);
      // the roof
      const rc = kit.css(kit.mix(p.col, '#2e3048', 0.45), a);
      g.beginPath();
      if (p.roof === 'gable') {
        g.moveTo(p.x - 6, top);
        g.lineTo(p.x + p.w / 2, top - sy * p.pitch);
        g.lineTo(p.x + p.w + 6, top);
      } else if (p.roof === 'hip') {
        g.moveTo(p.x - 6, top);
        g.lineTo(p.x + p.w * 0.25, top - sy * p.pitch * 0.6);
        g.lineTo(p.x + p.w * 0.75, top - sy * p.pitch * 0.6);
        g.lineTo(p.x + p.w + 6, top);
      } else {
        g.rect(p.x - 4, top - sy * 8, p.w + 8, sy * 8);
      }
      g.closePath();
      g.fillStyle = rc;
      g.fill();
      if (p.chimney >= 0) {
        g.fillStyle = rc;
        g.fillRect(p.x + p.w * (0.2 + p.chimney * 0.5), top - sy * (p.pitch * 0.5 + 22), 12, sy * 26);
      }
      // windows: not a grid of lights; some lit, some dark, sizes per house
      let k = 0;
      for (let i = 0; i < p.rows; i++) {
        for (let j = 0; j < p.cols; j++) {
          const v = p.win[k++ % p.win.length];
          const wx = p.x + 10 + j * ((p.w - 20) / p.cols) + 2;
          const wy = base - sy * (30 + i * 44) - (flip ? 0 : p.ww * 1.4);
          if (v < 0.25) continue;
          g.fillStyle = v > 0.62 ? kit.css(kit.mix('#ffc874', '#ffe2a8', v - 0.62), 0.9 * a) : kit.css('#2e3048', 0.7 * a);
          g.fillRect(wx, wy, p.ww, p.ww * 1.4);
        }
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
}

/** A stone wall: blocks of different widths, mortar, wet streaks and moss; quiet, not a tiled pattern. */
function wall(kit, g, y0, y1, seed) {
  const r = kit.rng(seed);
  g.fillStyle = kit.css('#3c3a50');
  g.fillRect(0, y0, 1920, y1 - y0);
  for (let y = y0; y < y1; ) {
    const h = 24 + r() * 14;
    for (let x = -r() * 60; x < 1920; ) {
      const w = 40 + r() * 90;
      const col = kit.mix(kit.jit('#605e78', r, 16), '#6e6a7e', r() * 0.4);
      g.beginPath();
      const rad = 4 + r() * 4;
      g.roundRect(x + 2, y + 2, w - 3, h - 3, rad);
      g.fillStyle = kit.css(col);
      g.fill();
      if (r() < 0.12) {
        g.fillStyle = kit.css('#5e7050', 0.55);
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

function bridge(kit, g, x0, x1, deck, water, seed) {
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
  g.fillStyle = kit.css('#5e5c74');
  g.fill(body);
  // stones
  g.clip(body);
  for (let y = deck - 30; y < water + 40; y += 16) {
    for (let x = x0 + ((y / 16) % 2) * 18; x < x1; x += 36) {
      g.fillStyle = kit.css(kit.jit('#66647e', r, 12));
      g.fillRect(x + 1, y + 1, 34, 14);
    }
  }
  g.restore();
  // the arch opening shows the water and sky behind
  g.save();
  g.clip(arch);
  g.fillStyle = kit.css('#3a4464');
  g.fillRect(x0, deck, x1 - x0, water - deck + 60);
  g.restore();
  g.lineWidth = 3;
  g.strokeStyle = kit.css('#3e3c54');
  g.stroke(arch);
  // parapet and its lit top edge
  g.fillStyle = kit.css('#54526c');
  g.fillRect(x0 - 10, deck - 52, x1 - x0 + 20, 24);
  g.fillStyle = 'rgba(255,214,170,0.35)';
  g.fillRect(x0 - 10, deck - 52, x1 - x0 + 20, 3);
}

/** Cobblestones in rows that shrink toward the horizon: each its own size and turn, wet, catching the sky. */
function cobbles(kit, g, y0, y1, w, seed, sheen = '#c9a6a0') {
  const r = kit.rng(seed);
  g.fillStyle = kit.css('#34304a');
  g.fillRect(0, y0, w, y1 - y0);
  let y = y0;
  while (y < y1) {
    const u = (y - y0) / (y1 - y0);
    const h = 9 + u * 30;
    let x = -r() * 30;
    while (x < w) {
      const sw = h * (1.0 + r() * 1.1);
      const hh = h * (0.75 + r() * 0.3);
      const col = kit.mix(kit.jit('#66607a', r, 20), r() < 0.3 ? '#57506a' : '#8a7e8e', r() * 0.35);
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

function puddle(kit, g, cx, cy, rx, ry, seed) {
  g.save();
  g.beginPath();
  g.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  g.clip();
  const grd = g.createLinearGradient(0, cy - ry, 0, cy + ry);
  grd.addColorStop(0, '#e6bf9c');
  grd.addColorStop(1, '#737c9c');
  g.fillStyle = grd;
  g.globalAlpha = 0.65;
  g.fillRect(cx - rx, cy - ry, rx * 2, ry * 2);
  g.restore();
}

/** Ripples in a puddle: rings born every so often, spreading and fading; drawn on twos. */
function ripples(kit, g, t, cx, cy, rx, ry, seed, rate = 2.2) {
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
function rain(kit, g, t, amount, seed) {
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

function mailbox(kit, g, x, ground, s) {
  g.save();
  g.translate(x, ground);
  g.scale(s, s);
  // post
  const post = path(kit, [[-8, 0], [8, 0], [8, -120], [-8, -120]]);
  cel(g, post.P, { base: T.wood, shade: '#553e2e', light: [-0.6, -0.8], sd: 5 });
  line(kit, g, post.q, 2, 21);
  // box with a little roof
  const box = path(kit, [[-50, -118], [52, -118], [52, -210], [-50, -210]]);
  cel(g, box.P, { base: T.box, shade: T.boxShade, rim: T.boxRim, light: [-0.6, -0.8], sd: 14, rw: 3 });
  line(kit, g, box.q, 2.6, 22);
  const roof = path(kit, [[-62, -206], [64, -206], [40, -236], [-40, -236]]);
  cel(g, roof.P, { base: '#5a3a30', shade: '#3e2620', light: [-0.6, -0.8], sd: 5 });
  line(kit, g, roof.q, 2.4, 23);
  // the brass slot on the face the tortoise walks up to
  g.fillStyle = T.brass;
  g.fillRect(-54, -186, 8, 34);
  g.fillStyle = '#2a1e24';
  g.fillRect(-52, -182, 4, 26);
  // a painted envelope on the side instead of words
  kit.ink(g, [[-20, -170, 1.6], [0, -156, 1.8], [20, -170, 1.6]], '#f2e6cc');
  g.strokeStyle = '#f2e6cc';
  g.lineWidth = 2;
  g.strokeRect(-22, -172, 44, 28);
  g.restore();
}

function lampPost(kit, g, x, ground, top, on) {
  // iron post
  kit.ink(g, [[x, ground, 14], [x, top + 60, 10], [x + 4, top + 20, 8]], '#2e2a3a');
  kit.ink(g, [[x, top + 30, 5], [x + 50, top + 6, 4], [x + 80, top + 24, 3]], '#2e2a3a');
  const lx = x + 86;
  const ly = top + 52;
  // the lantern
  const lantern = new Path2D();
  lantern.moveTo(lx - 22, ly - 24);
  lantern.lineTo(lx + 22, ly - 24);
  lantern.lineTo(lx + 16, ly + 22);
  lantern.lineTo(lx - 16, ly + 22);
  lantern.closePath();
  g.fillStyle = on > 0 ? kit.css(kit.mix('#6a6070', '#fff0c8', on)) : '#6a6070';
  g.fill(lantern);
  g.lineWidth = 3;
  g.strokeStyle = '#2e2a3a';
  g.stroke(lantern);
  g.fillStyle = '#2e2a3a';
  g.fillRect(lx - 26, ly - 30, 52, 8);
  return [lx, ly];
}

// ---------- shots ----------
export default {
  /** Wide: the canal, the bridge and the lit houses; the tortoise small on the wet stones. */
  canal(kit, scene) {
    const plate = kit.layer(1920, 1080);
    const g = plate.g;
    const sun = [1500, 470];
    paintSky(kit, g, 1920, 520, sun, 61);
    paintClouds(kit, g, [[300, 150, 820, 230], [1000, 110, 640, 180], [1600, 200, 760, 220], [700, 330, 520, 110]], sun);
    paintRiver(kit, g, 1920, 560, 830, sun[0], 62);
    houses(kit, g, -40, 1960, 560, 63, { reflect: 0.6 });
    bridge(kit, g, 620, 1300, 520, 640, 64);
    // quay wall and the cobbled path
    g.fillStyle = kit.css('#4a4660');
    g.fillRect(0, 822, 1920, 30);
    g.fillStyle = 'rgba(255,214,170,0.3)';
    g.fillRect(0, 822, 1920, 3);
    cobbles(kit, g, 852, 1080, 1920, 65);
    puddle(kit, g, 1220, 1010, 170, 26, 66);
    puddle(kit, g, 420, 930, 110, 16, 67);
    kit.tooth(g, 1920, 1080, 68, 0.05);
    const steps = footfalls(0, 3.9);
    steps.forEach((at, i) => kit.cue(`step${i + 1}`, at, 'step', { minor: true, near: 0.3 }));
    return (g2, t) => {
      g2.drawImage(plate.canvas, 0, 0);
      glitter(kit, g2, t, sun[0], 600, 800, 90, 69, 0);
      ripples(kit, g2, t, 1220, 1010, 170, 26, 70);
      ripples(kit, g2, t, 420, 930, 110, 16, 71, 1.6);
      const w = walk(kit, t, { x0: 300, x1: 420, t1: 3.9 });
      const y = 990;
      groundShadow(g2, w.x, y + 2, 0.42, 300, 'rgba(30,24,50,0.45)');
      tortoise(kit, g2, w.x, y, 0.42, { ...w, letter: true });
      kit.actor('乌龟', { x: w.x, y, s: 0.42, facing: 'right' });
      rain(kit, g2, t, 0.8, 72);
    };
  },

  /** Side: up to the mailbox, stop, stretch, post the letter. */
  mailbox(kit, scene) {
    const plate = kit.layer(1920, 1080);
    const g = plate.g;
    const sun = [1400, 260];
    paintSky(kit, g, 1920, 420, sun, 81);
    paintClouds(kit, g, [[300, 110, 760, 200], [1200, 90, 700, 190]], sun);
    houses(kit, g, -40, 1960, 420, 82, { haze: 0.18 });
    wall(kit, g, 400, 720, 83);
    cobbles(kit, g, 720, 1080, 1920, 84);
    puddle(kit, g, 560, 1000, 210, 30, 85);
    kit.tooth(g, 1920, 1080, 86, 0.05);
    const drop = scene.events.drop;
    const stopAt = 2.2;
    const steps = footfalls(0, stopAt);
    steps.forEach((at, i) => kit.cue(`step${i + 1}`, at, 'step', { minor: true, near: 1 }));
    const ground = 930;
    const s = 1.4;
    return (g2, t) => {
      g2.drawImage(plate.canvas, 0, 0);
      ripples(kit, g2, t, 560, 1000, 210, 30, 87);
      const w = walk(kit, t, { x0: 600, x1: 846, t1: stopAt });
      const d = kit.twos(t);
      // stretch up to the slot, push the letter in, settle back
      const neck = kit.smooth((d - 2.4) / 0.6) * (1 - kit.smooth((d - drop - 0.3) / 0.5));
      const push = kit.smooth((d - 3.0) / (drop - 3.0)) * (1 - kit.smooth((d - drop - 0.1) / 0.3));
      groundShadow(g2, w.x, ground + 2, s, 300, 'rgba(30,24,50,0.45)');
      tortoise(kit, g2, w.x, ground, s, { ...w, neck, push, letter: d < drop });
      // the box is drawn after the tortoise, so the part of the letter inside the slot is hidden
      mailbox(kit, g2, 1330, ground, s);
      kit.actor('乌龟', { x: w.x, y: ground, s, facing: 'right' });
      rain(kit, g2, t, 0.55, 88);
    };
  },

  /** The lamp comes on above; the tortoise looks up into the warm light. */
  lamp(kit, scene) {
    const plate = kit.layer(1920, 1080);
    const g = plate.g;
    const sun = [1500, 300];
    paintSky(kit, g, 1920, 460, sun, 91);
    paintClouds(kit, g, [[500, 120, 900, 220], [1500, 160, 700, 200]], sun);
    houses(kit, g, -40, 1960, 460, 92, { haze: 0.18 });
    wall(kit, g, 440, 700, 93);
    cobbles(kit, g, 700, 1080, 1920, 94);
    kit.tooth(g, 1920, 1080, 95, 0.05);
    const on = scene.events.lamp;
    const ground = 940;
    const s = 1.7;
    const tx = 1040;
    return (g2, t) => {
      g2.drawImage(plate.canvas, 0, 0);
      const d = kit.twos(t);
      // the lamp catches, flickers once, then holds
      const level = d < on ? 0 : d < on + 1 / 12 ? 1 : d < on + 2 / 12 ? 0.35 : kit.smooth((d - on - 2 / 12) / 0.25);
      const [lx, ly] = lampPost(kit, g2, 640, 1020, 140, level);
      if (level > 0) {
        // the pool of warm light on the wet stones and on the tortoise
        g2.save();
        g2.globalCompositeOperation = 'screen';
        const pool = g2.createRadialGradient(lx + 160, ground - 40, 20, lx + 160, ground - 40, 620);
        pool.addColorStop(0, `rgba(255,196,120,${0.55 * level})`);
        pool.addColorStop(1, 'rgba(255,196,120,0)');
        g2.fillStyle = pool;
        g2.fillRect(0, 0, 1920, 1080);
        const halo = g2.createRadialGradient(lx, ly, 4, lx, ly, 160);
        halo.addColorStop(0, `rgba(255,240,200,${0.9 * level})`);
        halo.addColorStop(1, 'rgba(255,220,160,0)');
        g2.fillStyle = halo;
        g2.fillRect(lx - 200, ly - 200, 400, 400);
        g2.restore();
      }
      // it looks up toward the light a beat after it comes on
      const look = kit.smooth((d - on - 0.6) / 0.6);
      groundShadow(g2, tx + 30, ground + 2, s, 300, 'rgba(30,24,50,0.5)');
      // lit from the lamp above and to the left once it is on
      const light = level > 0.5 ? [-0.5, -0.86] : [-0.6, -0.8];
      tortoise(kit, g2, tx, ground, s, { walking: false, look, leafLag: 0, letter: false, light });
      kit.actor('乌龟', { x: tx, y: ground, s, facing: 'right' });
      // the last of the rain, stopping
      rain(kit, g2, t, Math.max(0, 0.4 - d * 0.25), 96);
    };
  },
};
