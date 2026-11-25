import { paintSky, paintClouds, paintFarBank, lampPost, path, cel, line, DEFAULT_LOOK } from '/runtime/painters.js';

const INK = '#3b2a2e';
const LIGHT = [1, -0.55];
const LK = (kit) => ({ ...DEFAULT_LOOK, ...(kit.look || {}) });
// The low sun: behind and to the right in the street shots, so shadows run off to the left and toward us.
const SUN_STREET = { dir: [-1, 0.2], len: 1 };
const SUN_TOWN = { dir: [-0.5, 0.34], len: 0.75 };
// distance from the baker's feet to the middle of the cart, in drawing units
const GAP = 300;

// ---------------------------------------------------------------- shapes
function shape(kit, g, pts, fill, w, seed) {
  const { P, q } = path(kit, pts);
  cel(g, P, fill);
  if (w) line(kit, g, q, w, seed);
  return P;
}
function ellPts(cx, cy, rx, ry, n = 12, rot = 0, flat = 1) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const x = Math.cos(a) * rx;
    const y = Math.sin(a) * ry * (Math.sin(a) > 0 ? flat : 1);
    out.push([cx + x * Math.cos(rot) - y * Math.sin(rot), cy + x * Math.sin(rot) + y * Math.cos(rot)]);
  }
  return out;
}
function ring(kit, g, rad, w, color, seed) {
  const r = kit.rng(seed);
  const pts = [];
  for (let i = 0; i <= 18; i++) {
    const a = (i / 18) * Math.PI * 2;
    pts.push([Math.cos(a) * rad, Math.sin(a) * rad, w * (0.8 + 0.4 * r())]);
  }
  pts[18][2] = pts[0][2];
  kit.ink(g, pts, color, { taper: false });
}

// ---------------------------------------------------------------- shadows
// A shadow cast by the low sun: dark where the thing meets the ground, stretching away and fading.
function castShadow(g, x, y, rx, L, dir, a) {
  if (a <= 0.003) return;
  const [dx, dy] = dir;
  const ry = Math.max(2, rx * 0.16);
  const tx = x + dx * L;
  const ty = y + dy * L;
  const rx2 = rx * 0.9;
  const ry2 = ry * 1.8;
  const grd = g.createLinearGradient(x, y, tx, ty);
  a = Math.min(0.9, a * 1.9);
  grd.addColorStop(0, `rgba(92,66,140,${a})`);
  grd.addColorStop(0.45, `rgba(104,78,150,${a * 0.5})`);
  grd.addColorStop(1, 'rgba(110,84,156,0)');
  const P = new Path2D();
  P.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
  P.ellipse(tx, ty, rx2, ry2, 0, 0, Math.PI * 2);
  P.moveTo(x + rx, y);
  P.lineTo(x, y + ry);
  P.lineTo(tx, ty + ry2);
  P.lineTo(tx - rx2, ty);
  P.lineTo(tx, ty - ry2);
  P.lineTo(x, y - ry);
  P.closePath();
  g.save();
  g.globalCompositeOperation = 'multiply';
  g.fillStyle = grd;
  g.fill(P, 'nonzero');
  g.restore();
}
// The small, dark patch right where a foot or a wheel presses on the stones.
function contactShadow(g, x, y, rx, a) {
  if (a <= 0.003) return;
  g.save();
  g.globalCompositeOperation = 'multiply';
  g.translate(x, y);
  g.scale(1, 0.24);
  const grd = g.createRadialGradient(0, 0, 0, 0, 0, rx);
  a = Math.min(0.95, a * 1.6);
  grd.addColorStop(0, `rgba(60,40,104,${a})`);
  grd.addColorStop(0.6, `rgba(76,54,120,${a * 0.6})`);
  grd.addColorStop(1, 'rgba(80,58,124,0)');
  g.fillStyle = grd;
  g.beginPath();
  g.arc(0, 0, rx, 0, Math.PI * 2);
  g.fill();
  g.restore();
}

// ---------------------------------------------------------------- walking
// A foot is planted in the world while in stance, and swings forward twice as fast while in the air.
function walkPose(d, S, phi) {
  const Lc = 2 * S;
  const foot = (u) => {
    u = ((u % 1) + 1) % 1;
    if (u < 0.5) return [S / 2 - (u / 0.5) * S, 0];
    const v = (u - 0.5) / 0.5;
    return [-S / 2 + v * S, Math.sin(Math.PI * v) * S * 0.32];
  };
  const u = d / Lc + phi;
  return { a: foot(u), b: foot(u + 0.5), bob: -3.5 * (1 - Math.cos(4 * Math.PI * u)) / 2 };
}
function table(vfun, dur) {
  const N = Math.ceil(dur * 240) + 2;
  const T = new Float64Array(N);
  for (let i = 1; i < N; i++) T[i] = T[i - 1] + vfun((i - 0.5) / 240) / 240;
  return (tw) => T[Math.max(0, Math.min(N - 1, Math.round(tw * 240)))];
}
function stepCues(kit, dAt, dur, S, phi, tag = 'step') {
  let prev = Math.floor(2 * (dAt(0) / (2 * S) + phi) + 1e-9);
  for (let k = 1; k <= dur * 12; k++) {
    const tw = k / 12;
    const cur = Math.floor(2 * (dAt(tw) / (2 * S) + phi) + 1e-9);
    if (cur > prev) kit.cue(`${tag}${k}`, tw, 'step', { minor: true });
    prev = cur;
  }
}
function rattleCues(kit, dAt, dur, avoid = []) {
  let prev = Math.floor(dAt(0) / 34);
  for (let k = 1; k <= dur * 12; k++) {
    const tw = k / 12;
    const cur = Math.floor(dAt(tw) / 34);
    if (cur > prev && !avoid.some((a) => Math.abs(a - tw) < 0.2)) kit.cue(`rattle${k}`, tw, 'rattle', { minor: true });
    prev = cur;
  }
}

// ---------------------------------------------------------------- the hedgehog baker
const HH = {
  fur: '#dcb48a', furSh: '#a97f6e', furRim: '#ffe0b0', spine: '#6e4c3c', spineTip: '#b38d6c', spineDark: '#4c3443', spineRim: '#f0b06c',
  apron: '#f7f1e6', apronSh: '#c6bad4', hat: '#fcf9f1', hatSh: '#cbc4dc', hatRim: '#ffcf8e', foot: '#7c5448', footSh: '#57394a',
};

function hedgehog(kit, g, x, y, s, o) {
  const { d = 0, S = 50, phi = 0, turn = 0, grip = null, light = LIGHT, seed = 5, sun = SUN_STREET } = o;
  const w = walkPose(d, S, phi);
  // shadows: the body's long shadow, then each foot pressing on the stones
  castShadow(g, x + 4 * s, y, 60 * s, 240 * s * sun.len, sun.dir, 0.3);
  for (const [hip, f] of [[-6, w.b], [12, w.a]]) contactShadow(g, x + (hip + f[0] + 3) * s, y, 19 * s, 0.55 * kit.clamp(1 - f[1] / 12));
  g.save();
  g.translate(x, y);
  g.scale(s, s);
  const leg = (hip, f, far) => {
    const hx = hip[0];
    const hy = hip[1] + w.bob;
    const fx = hip[0] + f[0];
    const fy = -f[1];
    const mx = (hx + fx) / 2 + 3;
    const my = (hy + fy) / 2 - 2;
    kit.ink(g, [[hx, hy, 18], [mx, my, 16], [fx, fy - 5, 13]], INK, { taper: false });
    kit.ink(g, [[hx, hy, 13], [mx, my, 11.5], [fx, fy - 5, 8.5]], far ? HH.footSh : HH.foot, { taper: false });
    shape(kit, g, [[fx - 9, fy - 9], [fx + 5, fy - 11], [fx + 16, fy - 5], [fx + 15, fy], [fx - 9, fy]], { base: far ? HH.footSh : HH.foot, shade: HH.footSh, light, sd: 3 }, 2.2, seed + (far ? 3 : 4));
  };
  leg([-6, -32], w.b, true);

  g.save();
  g.translate(0, w.bob);
  g.translate(0, -32);
  g.rotate(0.07 - 0.04 * turn);
  g.translate(0, 32);
  let hand = [78, -57];
  if (grip) {
    const p = g.getTransform().invertSelf().transformPoint(new DOMPoint(grip[0], grip[1]));
    hand = [p.x, p.y];
  }
  const arm = (sh, hd, far) => {
    const mx = (sh[0] + hd[0]) / 2 - 1;
    const my = (sh[1] + hd[1]) / 2 + 7;
    kit.ink(g, [[sh[0], sh[1], 19], [mx, my, 16], [hd[0], hd[1], 13]], INK, { taper: false });
    kit.ink(g, [[sh[0], sh[1], 14], [mx, my, 11.5], [hd[0], hd[1], 8.5]], far ? HH.furSh : HH.fur, { taper: false });
    shape(kit, g, ellPts(hd[0], hd[1], 10, 9, 9), { base: far ? HH.furSh : HH.fur, shade: HH.furSh, light, sd: 4 }, 2.4, seed + (far ? 11 : 12));
    // fingers curled round the bar
    kit.ink(g, [[hd[0] - 3, hd[1] - 8, 1], [hd[0] + 3, hd[1] - 2, 2.2], [hd[0] + 1, hd[1] + 6, 1]], INK);
    kit.ink(g, [[hd[0] + 3, hd[1] - 7, 1], [hd[0] + 8, hd[1] - 1, 2], [hd[0] + 6, hd[1] + 5, 1]], INK);
  };
  arm([16, -80], [hand[0] - 4, hand[1] + 1], true);

  const cx = 2;
  const cy = -94;
  const spines = (front) => {
    const r = kit.rng(seed * 7 + (front ? 1 : 0));
    const n = front ? 30 : 42;
    for (let i = 0; i < n; i++) {
      const u = (i + r() * 0.7) / n;
      const th = ((-70 - u * 152) * Math.PI) / 180;
      const rb = front ? 0.8 : 0.9;
      const len = (front ? 30 : 42) + r() * 14;
      const bx = cx + Math.cos(th) * 64 * rb;
      const by = cy + Math.sin(th) * 74 * rb;
      const sw = th - 0.45 - r() * 0.15;
      const lag = -w.bob * 0.6 * (1 - u * 0.5);
      const tx = bx + Math.cos(sw) * len;
      const ty = by + Math.sin(sw) * len + lag;
      const col = front ? kit.mix(HH.spine, HH.spineTip, 0.25 + r() * 0.5) : kit.mix(HH.spineDark, HH.spine, r() * 0.5);
      if (!front) kit.ink(g, [[bx, by, 13], [(bx + tx) / 2, (by + ty) / 2, 8], [tx, ty, 2.5]], INK, { taper: false });
      kit.ink(g, [[bx, by, front ? 8 : 10], [(bx + tx) / 2, (by + ty) / 2, front ? 5 : 6], [tx, ty, 1]], kit.css(col), { taper: false });
      // the spines facing the low sun catch it at the tips
      if (front && u < 0.35) kit.ink(g, [[(bx + tx) / 2, (by + ty) / 2, 2.2], [tx, ty, 0.6]], kit.css(HH.spineRim, 0.9));
    }
  };
  spines(false);
  // body
  const body = [];
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2;
    body.push([cx + Math.cos(a) * 62 * (1 + 0.07 * Math.sin(a)), cy + Math.sin(a) * 72]);
  }
  shape(kit, g, body, { base: HH.fur, shade: HH.furSh, rim: HH.furRim, light, sd: 16, rw: 3 }, 3.4, seed + 1);
  // apron
  shape(kit, g, [[22, -122], [48, -112], [62, -76], [58, -36], [34, -24], [14, -40], [10, -84]], { base: HH.apron, shade: HH.apronSh, rim: '#fff3dc', light, sd: 9, rw: 2 }, 2.6, seed + 2);
  kit.ink(g, [[22, -122, 3], [10, -142, 2.6], [-4, -150, 2]], INK);
  // the mass of spines over the back, its sunward edge lit warm
  const mass = [];
  for (let i = 0; i <= 12; i++) {
    const th = ((-66 - (i / 12) * 160) * Math.PI) / 180;
    mass.push([cx + Math.cos(th) * 66, cy + Math.sin(th) * 76]);
  }
  mass.push([cx - 36, cy + 48], [cx - 18, cy + 6], [cx + 0, cy - 36], [cx + 14, cy - 62]);
  shape(kit, g, mass, { base: HH.spine, shade: HH.spineDark, rim: HH.spineRim, light, sd: 12, rw: 6 }, 3, seed + 3);
  spines(true);
  // the near arm reaches forward to the grip at waist height
  arm([34, -72], hand, false);
  // face: in profile (turn 0); at turn 1 the head is turned right round over the shoulder, looking back and down
  const k = turn;
  const c = Math.cos(Math.PI * k);
  const sg = c >= 0 ? 1 : -1;
  const cs = sg * Math.max(Math.abs(c), 0.32);
  const C = [kit.lerp(36, 14, k), kit.lerp(-110, -138, k)];
  const droop = 0.24 * k;
  const F = ([px, py]) => [C[0] + px * cs, C[1] + py + Math.abs(px * cs) * droop];
  // ear on the far side of the head when it turns
  shape(kit, g, ellPts(kit.lerp(14, 34, k), kit.lerp(-150, -152, k), 11, 10, 9), { base: HH.fur, shade: HH.furSh, light, sd: 4 }, 2.4, seed + 6);
  const snout = [[-2, -22], [44, -6], [72, 8], [48, 24], [2, 30]].map(F);
  shape(kit, g, snout, { base: HH.fur, shade: HH.furSh, rim: HH.furRim, light, sd: 7, rw: 2 }, 2.8, seed + 7);
  const nose = F([74, 9]);
  shape(kit, g, ellPts(nose[0], nose[1], 7.5, 6.5, 8), { base: '#3b2a2e', rim: '#8a6a78', light, rw: 2 }, 0, 0);
  g.fillStyle = 'rgba(255,240,230,0.8)';
  g.fillRect(nose[0] - 3, nose[1] - 4, 3, 2);
  const eye = (ex, ey) => {
    g.fillStyle = INK;
    g.beginPath();
    g.ellipse(ex, ey, 5, 6.5, 0, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = '#fff6ea';
    g.fillRect(ex + 0.5 * sg - (sg < 0 ? 2.4 : 0), ey - 4, 2.4, 2.4);
  };
  const e1 = F([22, -11]);
  eye(e1[0], e1[1]);
  if (Math.abs(c) < 0.55) eye(e1[0] - 20 * (1 - Math.abs(c)), e1[1]);
  const m0 = F([42, 20]);
  const m1 = F([52, 22]);
  kit.ink(g, [[m0[0], m0[1], 2], [m1[0], m1[1], 2.4]], INK);
  // the chef's hat: the puff lags the bob a little; its sunward side lit warm
  const lagY = -w.bob * 0.8;
  const puff = [[-16, -174], [-30, -192], [-22, -220], [2, -236], [30, -236], [56, -220], [64, -196], [54, -178]].map(([px, py]) => [px, py + lagY * (1 - (py + 174) / 62)]);
  shape(kit, g, puff, { base: HH.hat, shade: HH.hatSh, rim: HH.hatRim, light, sd: 10, rw: 5 }, 2.8, seed + 9);
  kit.ink(g, [[8, -180, 2], [6, -204 + lagY * 0.5, 1.8], [10, -224 + lagY, 1]], '#a9a2c4');
  kit.ink(g, [[30, -181, 2], [33, -206 + lagY * 0.5, 1.8], [36, -226 + lagY, 1]], '#a9a2c4');
  // the band sits down over the crown of the head, in front of the puff
  shape(kit, g, [[-10, -150], [16, -156], [44, -162], [52, -172], [50, -184], [20, -180], [-8, -174], [-13, -162]], { base: HH.hat, shade: HH.hatSh, rim: HH.hatRim, light, sd: 6, rw: 3 }, 2.6, seed + 8);
  const pts = { hand: kit.at(g, hand[0], hand[1]), nose: kit.at(g, nose[0] + 6 * sg, nose[1]) };
  g.restore();
  leg([12, -32], w.a, false);
  g.restore();
  return pts;
}

// ---------------------------------------------------------------- the cart
const CART = { wood: '#b8844f', woodSh: '#7f5537', woodRim: '#f2c07e', dark: '#6a4630', iron: '#4b4256', crust: '#d8964c', crustSh: '#a55f36', crustRim: '#f8cc86' };
const LOAVES = [
  ['bag', -30, -197, 78, 15, -0.2, 1.0],
  ['boule', 70, -197, 33, 26, 0, 0.7],
  ['bag', 28, -207, 72, 14, 0.32, 1.25],
  ['boule', -72, -195, 28, 22, 0.1, 0.8],
  ['bun', 8, -192, 18, 15, 0, 1.4],
  ['bun', 108, -191, 16, 13, 0, 1.1],
];
const FLYBUN = [-104, -193];
const GRIP = [-222, -57];

function cartXf(g, x, y, s, lift, tilt) {
  g.translate(x, y);
  g.scale(s, s);
  g.translate(0, -lift);
  g.translate(-78, -42);
  g.rotate(tilt);
  g.translate(78, 42);
}
function cartPt(x, y, s, lift, tilt, p) {
  const dx = p[0] + 78;
  const dy = p[1] + 42;
  const c = Math.cos(tilt);
  const sn = Math.sin(tilt);
  return [x + s * (-78 + c * dx - sn * dy), y + s * (-42 + sn * dx + c * dy - lift)];
}
function loaf(kit, g, kind, x, y, a, b, rot, seed, light) {
  if (kind === 'bag') {
    shape(kit, g, ellPts(x, y, a, b, 14, rot, 0.75), { base: CART.crust, shade: CART.crustSh, rim: CART.crustRim, light, sd: 7, rw: 3 }, 2.4, seed);
    for (let i = -2; i <= 2; i++) {
      const cx = x + Math.cos(rot) * i * a * 0.33;
      const cy = y + Math.sin(rot) * i * a * 0.33 - 2;
      kit.ink(g, [[cx - 8 * Math.cos(rot + 0.6), cy - 8 * Math.sin(rot + 0.6), 1], [cx, cy, 3.4], [cx + 8 * Math.cos(rot + 0.6), cy + 8 * Math.sin(rot + 0.6), 1]], '#f6d79e');
    }
  } else {
    shape(kit, g, ellPts(x, y, a, b, 12, rot, 0.7), { base: CART.crust, shade: CART.crustSh, rim: CART.crustRim, light, sd: kind === 'bun' ? 5 : 8, rw: 3 }, 2.4, seed);
    if (kind === 'boule') {
      kit.ink(g, [[x - a * 0.5, y - b * 0.35, 1], [x, y - b * 0.55, 3.4], [x + a * 0.5, y - b * 0.35, 1]], '#f6d79e');
      kit.ink(g, [[x - a * 0.4, y + b * 0.05, 1], [x + a * 0.1, y - b * 0.15, 3], [x + a * 0.45, y + b * 0.1, 1]], '#f6d79e');
    } else {
      g.fillStyle = 'rgba(255,236,200,0.7)';
      g.beginPath();
      g.ellipse(x + a * 0.25, y - b * 0.45, a * 0.28, b * 0.16, -0.3, 0, Math.PI * 2);
      g.fill();
    }
  }
}
function cart(kit, g, x, y, s, o) {
  const { roll = 0, lift = 0, tilt = 0, jig = 0, bun = true, light = LIGHT, sun = SUN_STREET } = o;
  // shadows: the box's long shadow, and a dark patch under each wheel that fades as the wheel leaves the ground
  castShadow(g, x - 6 * s, y, 128 * s, 210 * s * sun.len, sun.dir, 0.28);
  for (const wx of [-78, 78]) {
    const p = cartPt(x, y, s, lift, tilt, [wx, -1]);
    const hgt = (y - p[1]) / s;
    contactShadow(g, p[0], y, 30 * s * (1 + hgt / 40), 0.6 * kit.clamp(1 - hgt / 30));
  }
  g.save();
  cartXf(g, x, y, s, lift, tilt);
  // handle: from the back of the box down to a grip at the baker's waist, well below the snout
  kit.ink(g, [[-118, -104, 12], [-170, -80, 11], [GRIP[0] - 10, GRIP[1] + 4, 10]], INK, { taper: false });
  kit.ink(g, [[-118, -104, 7], [-170, -80, 6.5], [GRIP[0] - 10, GRIP[1] + 4, 6]], CART.dark, { taper: false });
  kit.ink(g, [[-150, -92, 2], [-196, -70, 1.6]], kit.css(CART.woodRim, 0.7));
  shape(kit, g, ellPts(GRIP[0] - 11, GRIP[1] + 4, 7.5, 7, 9), { base: CART.dark, shade: '#4a2e22', rim: CART.woodRim, light, sd: 3, rw: 2 }, 2.2, 302);
  // box
  const box = [[-130, -181], [-116, -183], [118, -186], [131, -184], [128, -170], [123, -100], [119, -89], [-115, -87], [-122, -97], [-127, -168]];
  shape(kit, g, box, { base: CART.wood, shade: CART.woodSh, rim: CART.woodRim, light, sd: 16, rw: 4 }, 3.4, 301);
  const r = kit.rng(77);
  for (const py of [-158, -134, -111]) {
    kit.ink(g, [[-122, py + r() * 2, 1], [-40, py - 1 + r() * 2, 2.4], [40, py + r() * 2, 2.2], [122, py - 2 + r() * 2, 1]], CART.woodSh);
  }
  for (const px of [-112, 112]) kit.ink(g, [[px, -180, 4], [px + 1, -134, 5], [px, -92, 4]], CART.dark, { taper: false });
  g.fillStyle = CART.iron;
  for (const px of [-120, 108]) g.fillRect(px, -182, 12, 9);
  // bread, piled; every loaf settles a beat after the box moves
  LOAVES.forEach(([kind, lx, ly, a, b, rot, amp], i) => loaf(kit, g, kind, lx, ly + jig * amp, a, b, rot + jig * amp * 0.004, 310 + i, light));
  if (bun) loaf(kit, g, 'bun', FLYBUN[0], FLYBUN[1], 17, 15, 0, 330, light);
  // axle beam and brackets
  kit.ink(g, [[-100, -88, 9], [0, -86, 10], [100, -88, 9]], CART.dark, { taper: false });
  for (const wx of [-78, 78]) {
    kit.ink(g, [[wx - 14, -88, 6], [wx, -44, 6]], CART.iron, { taper: false });
    kit.ink(g, [[wx + 14, -88, 6], [wx, -44, 6]], CART.iron, { taper: false });
    g.save();
    g.translate(wx, -42);
    ring(kit, g, 41, 11, INK, 400 + wx);
    ring(kit, g, 40, 7, CART.iron, 410 + wx);
    ring(kit, g, 34, 6, CART.wood, 420 + wx);
    for (let k = 0; k < 6; k++) {
      const a = roll + (k / 6) * Math.PI * 2;
      kit.ink(g, [[0, 0, 7], [Math.cos(a) * 17, Math.sin(a) * 17, 6], [Math.cos(a) * 32, Math.sin(a) * 32, 5]], INK, { taper: false });
      kit.ink(g, [[0, 0, 4.5], [Math.cos(a) * 17, Math.sin(a) * 17, 3.6], [Math.cos(a) * 32, Math.sin(a) * 32, 3]], CART.woodSh, { taper: false });
    }
    ring(kit, g, 29, 2, INK, 430 + wx);
    // the iron tyre catches the sun on its upper right
    g.strokeStyle = 'rgba(255,214,170,0.55)';
    g.lineWidth = 2.5;
    g.beginPath();
    g.arc(0, 0, 41, -1.4, -0.2);
    g.stroke();
    shape(kit, g, ellPts(0, 0, 8, 8, 8), { base: CART.iron, rim: '#9a8ea8', light, rw: 2 }, 2, 440 + wx);
    g.restore();
  }
  const pts = { handle: kit.at(g, GRIP[0], GRIP[1]), back: kit.at(g, -128, -130) };
  g.restore();
  return pts;
}

function bunShadow(kit, g, x, y, bs, air, sun) {
  const k = air * 0.35;
  castShadow(g, x + sun.dir[0] * k, y + sun.dir[1] * k, 15 * bs * (1 + air / 260), 24 * bs * sun.len, sun.dir, 0.42 / (1 + air / 90));
  contactShadow(g, x, y, 15 * bs, 0.5 * kit.clamp(1 - air / 6));
}
function bunDraw(kit, g, x, y, bs, { rot = 0, squash = 1, light = LIGHT } = {}) {
  g.save();
  g.translate(x, y);
  g.scale(bs * (1 + (1 - squash) * 0.7), bs * squash);
  g.translate(0, -15);
  const pts = { side: kit.at(g, -13, -9.6), top: kit.at(g, 0, -15) };
  g.rotate(rot);
  loaf(kit, g, 'bun', 0, 0, 17, 15, 0, 330, light);
  g.restore();
  return pts;
}

// ---------------------------------------------------------------- the pigeon
const PG = { body: '#a5a4bd', bodySh: '#77769c', rim: '#ffe6cc', head: '#8f8eae', neck: '#6f9c8c', neck2: '#94729e', wing: '#b6b4ca', wingSh: '#8584a6', bar: '#4f4a66', tail: '#6c6a8a', beak: '#3d3540', cere: '#f1ebf0', eye: '#ff9a3c', foot: '#e2818a' };
const WINGS = {
  up: [[10, -52], [2, -92], [-14, -132], [-36, -156], [-46, -146], [-40, -112], [-30, -72], [-14, -48]],
  mid: [[10, -52], [-18, -74], [-58, -90], [-100, -86], [-98, -72], [-60, -58], [-16, -44]],
  down: [[10, -52], [-2, -20], [-16, 10], [-30, 30], [-42, 22], [-36, -10], [-24, -42]],
};
function pigeon(kit, g, x, y, s, o) {
  const { air = 0, wing = 'fold', legs = 'down', pk = 0, target = null, tilt = 0, light = LIGHT, bob = 0, sun = SUN_STREET } = o;
  const k = air * 0.3;
  castShadow(g, x - 8 * s + sun.dir[0] * k, y + sun.dir[1] * k, 44 * s * (1 + air / 400), 80 * s * sun.len, sun.dir, 0.3 / (1 + air / 140));
  contactShadow(g, x, y, 26 * s, 0.5 * kit.clamp(1 - air / 5));
  g.save();
  g.translate(x, y - air);
  g.scale(s, s);
  g.rotate(tilt + 0.32 * pk);
  const wingShape = (name, far) => {
    const pts = WINGS[name].map(([px, py]) => (far ? [px - 8, py - 6] : [px, py]));
    shape(kit, g, pts, { base: far ? PG.wingSh : PG.wing, shade: PG.wingSh, rim: far ? null : PG.rim, light, sd: 8, rw: 2 }, 2.4, far ? 501 : 502);
    const tip = pts[3];
    const base = pts[1];
    for (let i = 0; i < 4; i++) {
      const u = 0.55 + i * 0.12;
      kit.ink(g, [[kit.lerp(base[0], tip[0], u) + i * 2, kit.lerp(base[1], tip[1], u), 3], [kit.lerp(base[0], tip[0], u + 0.1), kit.lerp(base[1], tip[1], u + 0.1) + 4, 1]], PG.bar);
    }
  };
  if (wing !== 'fold') wingShape(wing, true);
  shape(kit, g, [[-30, -46], [-62, -48], [-84, -46], [-86, -36], [-60, -32], [-30, -30]], { base: PG.tail, shade: PG.bar, light, sd: 4 }, 2.2, 503);
  if (legs !== 'tuck') {
    const fwd = legs === 'forward' ? 12 : 0;
    for (const [lx, c] of [[-6, '#c56a76'], [5, PG.foot]]) {
      kit.ink(g, [[lx, -20, 5], [lx + fwd * 0.6, -9, 4.5], [lx + fwd, -1, 4]], c, { taper: false });
      kit.ink(g, [[lx + fwd - 4, 0, 3], [lx + fwd + 10, 0, 2.6]], c, { taper: false });
    }
  }
  shape(kit, g, [[30, -56], [12, -64], [-14, -62], [-38, -50], [-46, -40], [-30, -24], [-4, -17], [22, -24], [35, -40]], { base: PG.body, shade: PG.bodySh, rim: PG.rim, light, sd: 10, rw: 3 }, 2.8, 504);
  if (wing === 'fold') {
    shape(kit, g, [[20, -54], [-8, -58], [-44, -48], [-66, -40], [-34, -33], [8, -38]], { base: PG.wing, shade: PG.wingSh, rim: PG.rim, light, sd: 6, rw: 2 }, 2.4, 505);
    kit.ink(g, [[-6, -50, 1], [-20, -46, 4.5], [-34, -42, 1]], PG.bar);
    kit.ink(g, [[-18, -43, 1], [-32, -39, 4.5], [-46, -37, 1]], PG.bar);
  }
  const H0 = [42, -66 + bob];
  const ang = pk * 1.05;
  let T = null;
  if (target) {
    const p = g.getTransform().invertSelf().transformPoint(new DOMPoint(target[0], target[1]));
    T = [p.x, p.y];
  }
  const off = [25 * Math.cos(ang) - 2 * Math.sin(ang), 25 * Math.sin(ang) + 2 * Math.cos(ang)];
  const H = T ? [kit.lerp(H0[0], T[0] - off[0], pk), kit.lerp(H0[1], T[1] - off[1], pk)] : H0;
  kit.ink(g, [[22, -46, 26], [(22 + H[0]) / 2, (-46 + H[1]) / 2, 22], [H[0], H[1], 18]], INK, { taper: false });
  kit.ink(g, [[22, -46, 21], [(22 + H[0]) / 2, (-46 + H[1]) / 2, 17], [H[0], H[1], 13]], PG.neck, { taper: false });
  kit.ink(g, [[24, -44, 9], [(22 + H[0]) / 2 - 2, (-46 + H[1]) / 2 + 3, 7], [H[0] - 4, H[1] + 6, 2]], PG.neck2);
  g.save();
  g.translate(H[0], H[1]);
  g.rotate(ang);
  kit.ink(g, [[9, -5, 2], [25, 2, 3], [9, 4, 2]], PG.beak, { taper: false });
  g.fillStyle = PG.beak;
  g.beginPath();
  g.moveTo(9, -5);
  g.lineTo(25, 2);
  g.lineTo(9, 4);
  g.fill();
  shape(kit, g, ellPts(0, 0, 13, 12, 10), { base: PG.head, shade: PG.bodySh, rim: PG.rim, light, sd: 5, rw: 2 }, 2.4, 506);
  g.fillStyle = PG.cere;
  g.beginPath();
  g.ellipse(11, -4, 4, 2.6, 0.3, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = PG.eye;
  g.beginPath();
  g.arc(4, -3, 3.6, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = INK;
  g.beginPath();
  g.arc(4.6, -3, 1.8, 0, Math.PI * 2);
  g.fill();
  const beak = kit.at(g, 25, 2);
  g.restore();
  if (wing !== 'fold') wingShape(wing, false);
  g.restore();
  return { beak };
}

// ---------------------------------------------------------------- town painting
// A row of houses painted in gouache: walls in vertical strokes, light at the top and dark at the foot,
// a warm edge on the side toward the sun; roofs with their tiles and eaves; every window its own.
// Returns the tops of the chimneys, so smoke can rise from them.
function paintTown(kit, g, x0, x1, base, seed, { sunX = 1e9 } = {}) {
  const r = kit.rng(seed);
  const L = LK(kit);
  const walls = L.houseWalls;
  const ROOFS = ['#7b6577', '#686784', '#86696e', '#5f6682', '#735f72'];
  const SHUT = ['#6d8686', '#8a6d78', '#7a7c98', '#8c7a62'];
  const chim = [];
  for (let x = x0; x < x1; ) {
    const w = 72 + r() * 110;
    const h = 96 + r() * 165;
    const kind = ['gable', 'eave', 'eave', 'flat', 'gable', 'eave'][Math.floor(r() * 6)];
    const pitch = kind === 'gable' ? 26 + r() * 34 : kind === 'eave' ? 20 + r() * 22 : 10;
    const col = kit.jit(walls[Math.floor(r() * walls.length)], r, 14);
    const roof = kit.jit(ROOFS[Math.floor(r() * ROOFS.length)], r, 12);
    const top = base - h;
    const lit = x + w / 2 < sunX ? 1 : -1;
    const yTop = kind === 'gable' ? top - pitch : top;
    // the wall, with its gable
    const wallP = new Path2D();
    wallP.moveTo(x, base);
    wallP.lineTo(x, top);
    if (kind === 'gable') wallP.lineTo(x + w / 2, top - pitch);
    wallP.lineTo(x + w, top);
    wallP.lineTo(x + w, base);
    wallP.closePath();
    g.fillStyle = kit.css(col);
    g.fill(wallP);
    g.save();
    g.clip(wallP);
    const grd = g.createLinearGradient(0, yTop, 0, base);
    grd.addColorStop(0, 'rgba(255,232,204,0.24)');
    grd.addColorStop(0.45, 'rgba(255,232,204,0)');
    grd.addColorStop(1, 'rgba(72,56,112,0.28)');
    g.fillStyle = grd;
    g.fillRect(x, yTop, w, base - yTop);
    const n = Math.round((w * (base - yTop)) / 520);
    for (let i = 0; i < n; i++) {
      const sx = x + r() * w;
      const sy = yTop + r() * (base - yTop);
      const Ls = 18 + r() * 46;
      const c2 = kit.mix(col, r() < 0.5 ? '#ffe2bf' : '#5a4c7c', 0.12 + r() * 0.16);
      const wob = (r() - 0.5) * 4;
      const bw = 5 + r() * 7;
      // quiet patches of wall are left alone
      if (Math.sin(sx * 0.031 + seed) + Math.cos(sy * 0.023 + seed * 0.7) > 1.05) continue;
      kit.stroke(g, [[sx, sy], [sx + wob, sy + Ls * 0.5], [sx + wob * 0.4, sy + Ls]], { width: bw, color: c2, alpha: 0.22, r, bristles: 3 });
    }
    // the edge toward the sun is warm, the far edge cool
    const ex = lit > 0 ? x + w : x;
    const eg = g.createLinearGradient(ex, 0, ex - lit * 16, 0);
    eg.addColorStop(0, 'rgba(255,212,158,0.62)');
    eg.addColorStop(1, 'rgba(255,212,158,0)');
    g.fillStyle = eg;
    g.fillRect(lit > 0 ? x + w - 16 : x, yTop, 16, base - yTop);
    const fx = lit > 0 ? x : x + w;
    const sgd = g.createLinearGradient(fx, 0, fx + lit * 20, 0);
    sgd.addColorStop(0, 'rgba(70,54,110,0.24)');
    sgd.addColorStop(1, 'rgba(70,54,110,0)');
    g.fillStyle = sgd;
    g.fillRect(lit > 0 ? x : x + w - 20, yTop, 20, base - yTop);
    if (kind !== 'gable') {
      const eav = g.createLinearGradient(0, top, 0, top + 14);
      eav.addColorStop(0, 'rgba(58,42,98,0.42)');
      eav.addColorStop(1, 'rgba(58,42,98,0)');
      g.fillStyle = eav;
      g.fillRect(x, top, w, 14);
    }
    g.restore();
    // the roof
    const rd = kit.css(kit.mix(roof, '#3a2e48', 0.4), 0.45);
    if (kind === 'gable') {
      // the shade the overhang throws on the gable wall
      kit.ink(g, [[x - 2, top + 9, 6], [x + w / 2, top - pitch + 8, 7]], 'rgba(58,42,98,0.3)');
      kit.ink(g, [[x + w / 2, top - pitch + 8, 7], [x + w + 2, top + 9, 6]], 'rgba(58,42,98,0.3)');
      kit.ink(g, [[x - 10, top + 6, 10], [x + w / 2, top - pitch - 4, 12]], kit.css(roof), { taper: false });
      kit.ink(g, [[x + w / 2, top - pitch - 4, 12], [x + w + 10, top + 6, 10]], kit.css(roof), { taper: false });
      // tile ends along the verge
      for (let u = 0.06; u < 0.98; u += 0.07 + r() * 0.03) {
        for (const side of [-1, 1]) {
          const px = x + w / 2 + side * (w / 2 + 10) * u;
          const py = top - pitch - 4 + (pitch + 10) * u;
          g.fillStyle = rd;
          g.fillRect(px - 1.5, py - 2, 3, 6);
        }
      }
      // the slope that faces the sun catches it
      const ls = lit > 0 ? [[x + w / 2, top - pitch - 9, 2.6], [x + w + 10, top + 1, 1.2]] : [[x + w / 2, top - pitch - 9, 2.6], [x - 10, top + 1, 1.2]];
      kit.ink(g, ls, 'rgba(255,214,168,0.75)');
      if (pitch > 36 && r() < 0.6) {
        g.fillStyle = kit.css(L.roofShade, 0.75);
        g.beginPath();
        g.arc(x + w / 2, top - pitch * 0.42, 5 + r() * 2, 0, Math.PI * 2);
        g.fill();
      }
    } else if (kind === 'eave') {
      const rp = new Path2D();
      rp.moveTo(x - 9, top + 2);
      rp.lineTo(x + w + 9, top + 2);
      rp.lineTo(x + w + 2, top - pitch);
      rp.lineTo(x - 2, top - pitch);
      rp.closePath();
      g.fillStyle = kit.css(roof);
      g.fill(rp);
      g.save();
      g.clip(rp);
      const rg = g.createLinearGradient(0, top - pitch, 0, top);
      rg.addColorStop(0, 'rgba(255,222,186,0.3)');
      rg.addColorStop(1, 'rgba(60,44,96,0.2)');
      g.fillStyle = rg;
      g.fillRect(x - 10, top - pitch, w + 20, pitch + 4);
      // the courses of tiles run down the slope; each row has a lit lip
      g.lineWidth = 1.3;
      g.strokeStyle = rd;
      for (let tx = x - 8; tx < x + w + 9; tx += 6 + r() * 3) {
        g.beginPath();
        g.moveTo(tx + (tx - (x + w / 2)) * -0.02, top - pitch);
        g.lineTo(tx, top + 2);
        g.stroke();
      }
      for (let ry = top - pitch + 6; ry < top; ry += 6 + r() * 2) {
        g.fillStyle = 'rgba(255,226,200,0.16)';
        g.fillRect(x - 9, ry, w + 18, 1.6);
        g.fillStyle = 'rgba(50,36,80,0.18)';
        g.fillRect(x - 9, ry + 1.6, w + 18, 1.2);
      }
      g.restore();
      g.fillStyle = kit.css(kit.mix(roof, '#3a2e48', 0.35));
      g.fillRect(x - 9, top - 1, w + 18, 4);
      g.fillStyle = 'rgba(255,214,168,0.6)';
      g.fillRect(x - 2, top - pitch - 1, w + 4, 2.5);
    } else {
      g.fillStyle = kit.css(roof);
      g.fillRect(x - 5, top - 10, w + 10, 10);
      g.fillStyle = 'rgba(255,214,168,0.55)';
      g.fillRect(x - 5, top - 10, w + 10, 2);
      g.fillStyle = 'rgba(58,42,98,0.3)';
      g.fillRect(x, top, w, 5);
    }
    // the chimney
    if (r() < 0.5) {
      const cxh = x + w * (0.18 + r() * 0.6);
      const roofY = kind === 'gable' ? top - pitch * (1 - Math.abs(cxh + 6 - (x + w / 2)) / (w / 2)) : kind === 'eave' ? top - pitch * 0.55 : top - 10;
      const ch = 24 + r() * 16;
      g.fillStyle = kit.css(kit.mix(col, L.roofShade, 0.4));
      g.fillRect(cxh, roofY - ch, 13, ch + 8);
      g.fillStyle = 'rgba(255,210,160,0.5)';
      g.fillRect(lit > 0 ? cxh + 10 : cxh, roofY - ch, 3, ch + 6);
      g.fillStyle = kit.css(kit.mix(col, L.roofShade, 0.65));
      g.fillRect(cxh - 2, roofY - ch - 5, 17, 6);
      chim.push([cxh + 6.5, roofY - ch - 5]);
    }
    // windows: each house has its own size and kind; each window is a little different
    const floors = Math.max(1, Math.floor((h - 36) / 50));
    const ww0 = 11 + r() * 8;
    const asp = 1.3 + r() * 0.45;
    const arch = r() < 0.3;
    const shut = r() < 0.35;
    const shutCol = SHUT[Math.floor(r() * SHUT.length)];
    const cols = Math.max(1, Math.floor((w - 14) / (ww0 + 24)));
    const doorAt = h > 120 && r() < 0.6 ? Math.floor(r() * cols) : -1;
    for (let i = 0; i < floors; i++) {
      const fsc = i === 0 ? 1.08 : i === floors - 1 && floors > 2 ? 0.8 : 1;
      for (let j = 0; j < cols; j++) {
        const v = r();
        const jx = (r() - 0.5) * 6;
        const js = 0.84 + r() * 0.3;
        const ww = ww0 * fsc * js;
        const wh = ww * asp * (0.9 + r() * 0.2);
        const cxw = x + (w / cols) * (j + 0.5) + jx;
        if (i === 0 && j === doorAt) {
          const dw = Math.max(16, ww * 1.3);
          const dh = Math.min(h * 0.4, dw * 2.1);
          g.fillStyle = kit.css(kit.mix('#5e4456', col, 0.25));
          g.beginPath();
          g.roundRect(cxw - dw / 2, base - dh, dw, dh, [dw / 2, dw / 2, 0, 0]);
          g.fill();
          g.fillStyle = 'rgba(255,210,160,0.4)';
          g.fillRect(lit > 0 ? cxw + dw / 2 - 2 : cxw - dw / 2, base - dh + dw / 2, 2, dh - dw / 2);
          g.fillStyle = 'rgba(232,214,200,0.55)';
          g.fillRect(cxw - dw / 2 - 4, base - 3, dw + 8, 3);
          continue;
        }
        const wy = base - 30 - i * 50 - wh;
        if (wy < top + 10 || v < 0.14) continue;
        if (shut && v > 0.4) {
          g.fillStyle = kit.css(kit.jit(shutCol, r, 10), 0.9);
          g.fillRect(cxw - ww / 2 - ww * 0.48, wy, ww * 0.44, wh);
          g.fillRect(cxw + ww / 2 + ww * 0.04, wy, ww * 0.44, wh);
          g.fillStyle = 'rgba(50,36,80,0.25)';
          for (let sy = wy + 3; sy < wy + wh - 2; sy += 4) {
            g.fillRect(cxw - ww / 2 - ww * 0.48, sy, ww * 0.44, 1);
            g.fillRect(cxw + ww / 2 + ww * 0.04, sy, ww * 0.44, 1);
          }
        }
        const lit2 = v > 0.68;
        g.fillStyle = lit2 ? kit.css(kit.mix(L.windows, L.windowsBright, (v - 0.68) * 2.5), 0.95) : kit.css(kit.mix(L.roofShade, '#9a96b8', 0.25 + r() * 0.35), 0.9);
        g.beginPath();
        g.roundRect(cxw - ww / 2, wy, ww, wh, arch ? [ww / 2, ww / 2, 1, 1] : 1.5);
        g.fill();
        if (lit2) {
          const gl = g.createRadialGradient(cxw, wy + wh / 2, 1, cxw, wy + wh / 2, ww * 1.6);
          gl.addColorStop(0, 'rgba(255,220,150,0.28)');
          gl.addColorStop(1, 'rgba(255,220,150,0)');
          g.fillStyle = gl;
          g.fillRect(cxw - ww * 1.6, wy + wh / 2 - ww * 1.6, ww * 3.2, ww * 3.2);
        } else {
          g.strokeStyle = 'rgba(255,236,214,0.35)';
          g.lineWidth = 1.2;
          g.beginPath();
          g.moveTo(cxw - ww * 0.3, wy + wh * 0.75);
          g.lineTo(cxw + ww * 0.2, wy + wh * 0.25);
          g.stroke();
        }
        g.fillStyle = 'rgba(60,46,84,0.45)';
        g.fillRect(cxw - 0.6, wy + (arch ? ww / 2 : 1), 1.2, wh - (arch ? ww / 2 : 2));
        g.fillRect(cxw - ww / 2, wy + wh * 0.5, ww, 1.2);
        g.fillStyle = 'rgba(236,220,206,0.6)';
        g.fillRect(cxw - ww / 2 - 2, wy + wh, ww + 4, 2.5);
      }
    }
    x += w + 2 + r() * 12;
  }
  return chim;
}

// Cobbles: small and tight far off, big near the lens; a worn lane where wheels and feet go, and quiet
// smoothed patches where the stones dissolve into one wash.
function paintStones(kit, g, y0, y1, w, seed, { lane = null, hMax = 40, quiet = 3 } = {}) {
  const r = kit.rng(seed);
  const CB = LK(kit).cobble;
  g.fillStyle = kit.css(CB.gap);
  g.fillRect(0, y0, w, y1 - y0);
  let y = y0;
  while (y < y1) {
    const u = (y - y0) / (y1 - y0);
    const h = 5 + hMax * Math.pow(u, 1.35);
    let x = -r() * h * 2;
    while (x < w) {
      const sw = h * (1.15 + r() * 1.1);
      const hh = h * (0.72 + r() * 0.25);
      const cx = x + sw / 2 + (r() - 0.5) * 2;
      const cy = y + h / 2 + (r() - 0.5) * 2;
      const rot = (r() - 0.5) * 0.2;
      const col = kit.mix(kit.jit(CB.stone, r, 18), r() < 0.3 ? CB.dark : CB.light, r() * 0.4);
      g.beginPath();
      for (let i = 0; i <= 10; i++) {
        const a = (i / 10) * Math.PI * 2;
        const rr = 1 + (r() - 0.5) * 0.12;
        const px = Math.cos(a) * (sw / 2 - 1.5) * rr;
        const py = Math.sin(a) * (hh / 2 - 1) * rr;
        g.lineTo(cx + px * Math.cos(rot) - py * Math.sin(rot), cy + px * Math.sin(rot) + py * Math.cos(rot));
      }
      g.closePath();
      g.fillStyle = kit.css(col);
      g.fill();
      if (r() < 0.7) {
        g.beginPath();
        g.ellipse(cx - sw * 0.06, cy - hh * 0.2, sw * (0.2 + r() * 0.15), hh * 0.13, rot, 0, Math.PI * 2);
        g.fillStyle = kit.css(CB.sheen, 0.16 + r() * 0.22);
        g.fill();
      }
      x += sw + 1 + r() * 2.5 * (0.3 + u);
    }
    y += h * 0.86 + 0.5 + u * 1.5;
  }
  const worn = kit.mix(CB.stone, CB.light, 0.45);
  // the lane: lighter, the stones polished smooth
  if (lane !== null) {
    const lg = g.createLinearGradient(0, lane - 40, 0, lane + 40);
    lg.addColorStop(0, kit.css(worn, 0));
    lg.addColorStop(0.5, kit.css(worn, 0.38));
    lg.addColorStop(1, kit.css(worn, 0));
    g.fillStyle = lg;
    g.fillRect(0, lane - 40, w, 80);
    for (let i = 0; i < w / 70; i++) {
      const x = r() * w;
      kit.stroke(g, [[x, lane + (r() - 0.5) * 30], [x + 60 + r() * 80, lane + (r() - 0.5) * 30]], { width: 8 + r() * 10, color: kit.mix(worn, '#ffe6cc', 0.2), alpha: 0.12, r, bristles: 3 });
    }
  }
  // quiet places: the stones melt into a flat, worn wash
  for (let i = 0; i < quiet; i++) {
    const px = ((i + 0.3 + r() * 0.5) / quiet) * w;
    const py = y0 + (0.35 + r() * 0.55) * (y1 - y0);
    const rx = 140 + r() * 220;
    g.save();
    g.translate(px, py);
    g.scale(1, 0.22);
    const qg = g.createRadialGradient(0, 0, 0, 0, 0, rx);
    qg.addColorStop(0, kit.css(worn, 0.7));
    qg.addColorStop(0.6, kit.css(worn, 0.45));
    qg.addColorStop(1, kit.css(worn, 0));
    g.fillStyle = qg;
    g.beginPath();
    g.arc(0, 0, rx, 0, Math.PI * 2);
    g.fill();
    g.restore();
    for (let k = 0; k < 6; k++) {
      const sx = px + (r() - 0.5) * rx * 1.2;
      const sy = py + (r() - 0.5) * rx * 0.25;
      kit.stroke(g, [[sx, sy], [sx + 40 + r() * 60, sy + (r() - 0.5) * 4]], { width: 6 + r() * 8, color: kit.mix(worn, '#ffe6cc', 0.15), alpha: 0.14, r, bristles: 3 });
    }
  }
  // distance: the far rows go into the morning air; the nearest darken
  const hz = g.createLinearGradient(0, y0, 0, y0 + (y1 - y0) * 0.5);
  hz.addColorStop(0, 'rgba(204,196,218,0.5)');
  hz.addColorStop(1, 'rgba(204,196,218,0)');
  g.fillStyle = hz;
  g.fillRect(0, y0, w, (y1 - y0) * 0.5);
  const dk = g.createLinearGradient(0, y0 + (y1 - y0) * 0.7, 0, y1);
  dk.addColorStop(0, 'rgba(70,54,104,0)');
  dk.addColorStop(1, 'rgba(70,54,104,0.22)');
  g.fillStyle = dk;
  g.fillRect(0, y0 + (y1 - y0) * 0.7, w, (y1 - y0) * 0.3);
}

// Chimney smoke: a soft ribbon that leans with the breeze, widening and thinning as it rises.
function smoke(kit, g, t, sx, sy, sc, seed) {
  const r = kit.rng(seed);
  const d = kit.twos(t);
  const speed = 0.16 + r() * 0.06;
  const ph = r();
  const lean = 0.7 + r() * 0.5;
  const N = 18;
  for (let k = 0; k < N; k++) {
    const a = (k / N + d * speed + ph) % 1;
    const x = sx + (a * a * 120 * lean + Math.sin(a * 5 + seed + d * 1.3) * 6 * a) * sc;
    const y = sy - a * 160 * sc;
    const rad = (5 + a * 30) * sc;
    const al = 0.38 * Math.min(1, a * 7) * (1 - a) ** 1.3;
    const grd = g.createRadialGradient(x, y, 0, x, y, rad);
    grd.addColorStop(0, `rgba(222,214,230,${al})`);
    grd.addColorStop(0.55, `rgba(214,206,226,${al * 0.55})`);
    grd.addColorStop(1, 'rgba(214,206,226,0)');
    g.fillStyle = grd;
    g.beginPath();
    g.ellipse(x, y, rad * 1.15, rad, 0, 0, Math.PI * 2);
    g.fill();
  }
}
// Tint only what is already painted on a layer: distance seen through the morning air.
function haze(g, w, h, color) {
  g.save();
  g.globalCompositeOperation = 'source-atop';
  g.fillStyle = color;
  g.fillRect(0, 0, w, h);
  g.restore();
}
// A layer of mist: long soft banks, kept well inside the layer so no edge shows.
function mist(kit, w, h, seed, alpha = 0.5) {
  const L = kit.layer(w, h);
  const r = kit.rng(seed);
  for (let i = 0; i < 40; i++) {
    const x = r() * w;
    const y = h * (0.42 + r() * 0.16);
    const rx = 180 + r() * 380;
    L.g.save();
    L.g.translate(x, y);
    L.g.scale(1, Math.min(0.12 + r() * 0.08, (h * 0.4) / rx));
    const grd = L.g.createRadialGradient(0, 0, 0, 0, 0, rx);
    const a = alpha * (0.25 + r() * 0.35);
    grd.addColorStop(0, `rgba(236,230,240,${a})`);
    grd.addColorStop(0.6, `rgba(236,228,236,${a * 0.5})`);
    grd.addColorStop(1, 'rgba(236,228,236,0)');
    L.g.fillStyle = grd;
    L.g.beginPath();
    L.g.arc(0, 0, rx, 0, Math.PI * 2);
    L.g.fill();
    L.g.restore();
  }
  return L.canvas;
}
function glowOver(g, x, y, rad, a) {
  const grd = g.createRadialGradient(x, y, 0, x, y, rad);
  grd.addColorStop(0, `rgba(255,226,160,${a})`);
  grd.addColorStop(0.4, `rgba(255,214,160,${a * 0.45})`);
  grd.addColorStop(1, 'rgba(255,210,170,0)');
  g.fillStyle = grd;
  g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
}

// A street seen from the side: sky, a far row of roofs in the haze, the near row of houses with a
// pavement, and the cobbled road in front. Every layer is wide enough for the whole camera move.
function street(kit, seed, W) {
  const sun = [1560, 470];
  const sky = kit.layer(Math.max(2000, W > 1920 ? 2000 : 1920), 700);
  paintSky(kit, sky.g, sky.canvas.width, 640, sun, seed);
  paintClouds(kit, sky.g, [[360, 210, 760, 150], [1120, 130, 700, 130], [1780, 300, 460, 90]], sun);
  const far = kit.layer(W, 840);
  paintFarBank(kit, far.g, W, 610, seed + 1);
  far.g.fillStyle = '#8f88a2';
  far.g.fillRect(0, 640, W, 200);
  const farCh = paintTown(kit, far.g, -20, W + 20, 650, seed + 2);
  haze(far.g, W, 840, 'rgba(196,190,214,0.45)');
  const near = kit.layer(W, 1080);
  near.g.save();
  near.g.translate(0, 808);
  near.g.scale(1.3, 1.3);
  const nearCh = paintTown(kit, near.g, -20, W / 1.3 + 20, 0, seed + 3).map(([x, y]) => [x * 1.3, 808 + y * 1.3]);
  near.g.restore();
  haze(near.g, W, 1080, 'rgba(200,192,214,0.12)');
  // pavement and kerb
  near.g.fillStyle = '#a89cac';
  near.g.fillRect(0, 806, W, 22);
  kit.mottle(near.g, 0, 806, W, 20, () => [190, 176, 186], { n: W / 6, size: 24, alpha: 0.25, r: kit.rng(seed + 4) });
  near.g.fillStyle = 'rgba(255,226,190,0.45)';
  near.g.fillRect(0, 805, W, 3);
  near.g.fillStyle = '#6c6378';
  near.g.fillRect(0, 826, W, 6);
  const lamps = [520, 1500, 2350].filter((lx) => lx < W);
  for (const lx of lamps) {
    castShadow(near.g, lx, 814, 8, 60, SUN_STREET.dir, 0.3);
    lampPost(kit, near.g, lx, 812, 470, 0.45);
  }
  const road = kit.layer(W, 260);
  paintStones(kit, road.g, 0, 260, W, seed + 5, { lane: 143, hMax: 40, quiet: Math.round(W / 700) });
  kit.tooth(road.g, W, 260, seed + 6, 0.05);
  for (const lx of lamps) castShadow(road.g, lx - 40, -8, 9, 420, SUN_STREET.dir, 0.26);
  return { sun, sky: sky.canvas, far: far.canvas, near: near.canvas, road: road.canvas, farCh, nearCh, mist: mist(kit, W, 360, seed + 7, 0.7) };
}

// ---------------------------------------------------------------- shots
// For checking stills: DBG zooms a shot ({ town: [x, y, zoom] }), DBGT shifts its clock. Both off for the film.
const DBG = null;
const DBGT = null;
const dbg = (g, k) => {
  const v = DBG && DBG[k];
  if (!v) return;
  g.translate(960, 540);
  g.scale(v[2], v[2]);
  g.translate(-v[0], -v[1]);
};
const dbgT = (k, t) => (DBGT && DBGT[k] !== undefined ? t + DBGT[k] : t);

export default {
  // 1. The town in the mist at first light; the baker passes along the near street.
  town(kit, scene) {
    const sun = [1000, 640];
    const sky = kit.layer(1920, 760);
    paintSky(kit, sky.g, 1920, 700, sun, 3);
    paintClouds(kit, sky.g, [[280, 200, 780, 150], [1480, 170, 820, 160], [1820, 360, 360, 80]], sun);
    // the far town and its houses, standing in fog
    const back = kit.layer(1920, 1080);
    paintFarBank(kit, back.g, 1920, 690, 4);
    haze(back.g, 1920, 1080, 'rgba(206,198,220,0.4)');
    const chA = paintTown(kit, back.g, -20, 1940, 782, 12, { sunX: sun[0] });
    haze(back.g, 1920, 1080, 'rgba(200,192,216,0.32)');
    const fogG = back.g.createLinearGradient(0, 760, 0, 900);
    fogG.addColorStop(0, 'rgba(214,206,226,0)');
    fogG.addColorStop(0.35, 'rgba(214,206,226,0.85)');
    fogG.addColorStop(1, 'rgba(206,198,220,0.95)');
    back.g.fillStyle = fogG;
    back.g.fillRect(0, 760, 1920, 140);
    // a nearer row seen down the side street, between the two near rows
    const mid = kit.layer(1920, 1080);
    mid.g.save();
    mid.g.translate(0, 868);
    mid.g.scale(1.12, 1.12);
    const chM = paintTown(kit, mid.g, 560 / 1.12, 1420 / 1.12, 0, 18, { sunX: sun[0] / 1.12 }).map(([x, y]) => [x * 1.12, 868 + y * 1.12]);
    mid.g.restore();
    haze(mid.g, 1920, 1080, 'rgba(204,196,220,0.36)');
    const mfog = mid.g.createLinearGradient(0, 800, 0, 870);
    mfog.addColorStop(0, 'rgba(214,206,226,0)');
    mfog.addColorStop(1, 'rgba(214,206,226,0.9)');
    mid.g.fillStyle = mfog;
    mid.g.fillRect(500, 800, 960, 70);
    // the near street: two rows of houses, the pavement and the cobbles
    const front = kit.layer(1920, 1080);
    const rowB = [[0, -10, 450, 21], [1290, 0, 440, 22]];
    const chB = [];
    for (const [ox, x0, x1, sd] of rowB) {
      front.g.save();
      front.g.translate(ox, 866);
      front.g.scale(1.5, 1.5);
      const ch = paintTown(kit, front.g, x0, x1, 0, sd, { sunX: (sun[0] - ox) / 1.5 });
      front.g.restore();
      for (const [cx, cy] of ch) chB.push([ox + cx * 1.5, 866 + cy * 1.5]);
    }
    front.g.fillStyle = '#a89cac';
    front.g.fillRect(0, 862, 1920, 20);
    front.g.fillStyle = 'rgba(255,226,190,0.4)';
    front.g.fillRect(0, 861, 1920, 3);
    paintStones(kit, front.g, 880, 1080, 1920, 14, { lane: 1000, hMax: 30, quiet: 3 });
    kit.tooth(front.g, 1920, 1080, 15, 0.05);
    castShadow(front.g, 1180, 874, 8, 330, SUN_TOWN.dir, 0.3);
    lampPost(kit, front.g, 1180, 872, 560, 0.5);
    // the foreground, close to the lens and a little soft: a door jamb and its step, a bollard and the kerb
    const fgS = kit.layer(1920, 1080);
    const f = fgS.g;
    const fr = kit.rng(19);
    f.fillStyle = '#4c4462';
    f.fillRect(-10, 360, 98, 730);
    for (let i = 0; i < 40; i++) {
      const sx = fr() * 86;
      const sy = 360 + fr() * 700;
      kit.stroke(f, [[sx, sy], [sx + (fr() - 0.5) * 3, sy + 40 + fr() * 50]], { width: 8 + fr() * 6, color: kit.mix('#4c4462', fr() < 0.5 ? '#7a6e8e' : '#3a3250', 0.4), alpha: 0.35, r: fr, bristles: 3 });
    }
    f.fillStyle = 'rgba(255,208,160,0.5)';
    f.fillRect(82, 360, 6, 730);
    f.fillStyle = '#5a5070';
    f.beginPath();
    f.roundRect(-10, 1016, 330, 80, 8);
    f.fill();
    f.fillStyle = 'rgba(255,218,176,0.55)';
    f.fillRect(-10, 1016, 328, 4);
    f.fillStyle = 'rgba(40,28,64,0.3)';
    f.fillRect(-10, 1036, 330, 50);
    f.fillStyle = '#463e5a';
    f.beginPath();
    f.roundRect(1714, 905, 66, 190, [30, 30, 4, 4]);
    f.fill();
    f.fillStyle = 'rgba(255,208,160,0.45)';
    f.fillRect(1768, 925, 6, 150);
    f.fillStyle = '#524866';
    f.beginPath();
    f.roundRect(1400, 1056, 540, 40, 6);
    f.fill();
    f.fillStyle = 'rgba(255,218,176,0.4)';
    f.fillRect(1400, 1056, 540, 3);
    const fg = kit.layer(1920, 1080);
    fg.g.filter = 'blur(3px)';
    fg.g.drawImage(fgS.canvas, 0, 0);
    fg.g.filter = 'none';
    const mistA = mist(kit, 2400, 400, 16, 0.85);
    const mistB = mist(kit, 2400, 360, 17, 0.55);

    const s = 0.52;
    const gy = 1000;
    const vL = 150;
    const S = 50;
    const dAt = (tw) => vL * tw;
    stepCues(kit, dAt, scene.duration, S, 0);
    rattleCues(kit, dAt, scene.duration);
    return (g, t0, dur) => {
      const t = dbgT('town', t0);
      const tw = kit.twos(t);
      dbg(g, 'town');
      const z = 1 + 0.03 * kit.smooth(t / dur);
      g.translate(960, 640);
      g.scale(z, z);
      g.translate(-960, -640);
      g.drawImage(sky.canvas, 0, 0);
      // the edge of the sky warms from grey-blue to pale gold
      glowOver(g, sun[0], sun[1] + 30, 900, 0.1 + 0.32 * kit.smooth(t / dur));
      g.drawImage(back.canvas, 0, 0);
      for (const [i, [cx, cy]] of chA.entries()) smoke(kit, g, t, cx, cy, 0.7, 60 + i);
      g.drawImage(mistA, -200 + t * 14, 510);
      g.drawImage(mid.canvas, 0, 0);
      for (const [i, [cx, cy]] of chM.entries()) smoke(kit, g, t, cx, cy, 0.85, 70 + i);
      g.drawImage(front.canvas, 0, 0);
      for (const [i, [cx, cy]] of chB.entries()) smoke(kit, g, t, cx, cy, 1.1, 80 + i);
      g.drawImage(mistB, -300 + t * 9, 640);
      const d = dAt(tw);
      const hx = 370 + d * s;
      const cx = hx + GAP * s;
      const rat = 1.6 * (0.5 - 0.5 * Math.cos((2 * Math.PI * d) / 34));
      const cp = cart(kit, g, cx, gy, s, { roll: d / 42, lift: rat, sun: SUN_TOWN });
      kit.prop('推车', { x: cx, y: gy, s, points: cp });
      const hp = hedgehog(kit, g, hx, gy, s, { d, S, grip: cp.handle, sun: SUN_TOWN });
      kit.actor('刺猬', { x: hx, y: gy, s, facing: 'right', points: hp });
      g.drawImage(fg.canvas, 0, 0);
    };
  },

  // 2. Tracking beside the baker; the front wheel rides up a raised stone and throws a bun off the back.
  track(kit, scene) {
    const W = 2700;
    const st = street(kit, 40, W);
    const s = 1.05;
    const gy = 965;
    const vL = 130;
    const vs = vL * s;
    const S = 50;
    const cx0 = 1080;
    const dur = scene.duration;
    const tb = scene.events.bump;
    const tland = scene.events.land;
    // the wheel checks as it meets the stone, then rolls on: a dip in speed just before each wheel goes over
    const dip = (t, t0, depth, wd) => {
      const a = (t - t0) / wd;
      return Math.abs(a) < 1 ? depth * (0.5 + 0.5 * Math.cos(Math.PI * a)) : 0;
    };
    const d1 = table((t) => vL * (1 - dip(t, tb - 0.1, 0.6, 0.16)), dur + 0.2);
    const dS = d1(tb);
    const solve = (fn, target) => {
      for (let i = 0; i < (dur + 0.2) * 240; i++) if (fn(i / 240) >= target) return i / 240;
      return dur;
    };
    const t2a = solve(d1, dS + 156);
    const dRaw = table((t) => vL * (1 - dip(t, tb - 0.1, 0.6, 0.16) - dip(t, t2a - 0.08, 0.35, 0.14)), dur + 0.2);
    const dAt = (tw) => dRaw(tw);
    const t2 = solve(dRaw, dS + 156);
    const climb = (dw) => (Math.abs(dw) < 34 ? 14 * (0.5 + 0.5 * Math.cos((Math.PI * dw) / 34)) : 0);
    const bumpAt = (tw) => {
      const d = dAt(tw);
      const hf = climb(d - dS);
      const hr = climb(d - dS - 156);
      let lift = 1.6 * (0.5 - 0.5 * Math.cos((2 * Math.PI * d) / 34)) + hr;
      let tilt = (hr - hf) / 156;
      const a = tw - tb;
      if (a >= 0 && a < 0.4) {
        lift += 18 * Math.sin((Math.PI * a) / 0.4);
        tilt -= 0.05 * Math.sin((Math.PI * a) / 0.4);
      }
      const b = tw - t2;
      if (b >= 0 && b < 0.3) {
        lift += 8 * Math.sin((Math.PI * b) / 0.3);
        tilt += 0.03 * Math.sin((Math.PI * b) / 0.3);
      }
      let jig = a > 0 ? -12 * Math.exp(-a * 4.5) * Math.sin(a * 17) : 0;
      if (b > 0) jig += -5 * Math.exp(-b * 5) * Math.sin(b * 17);
      return { lift, tilt, jig };
    };
    // the stone sits right under the front wheel at the moment of the jolt
    const stoneX = cx0 + dS * s + 78 * s;
    // the bun leaves the pile on the next drawing, with the cart already rising, and flies back over the baker
    const tL = tb + 1 / 12;
    const T = tland - tL;
    const pL = bumpAt(tL);
    const [bx0, by0] = cartPt(cx0 + dAt(tL) * s, gy, s, pL.lift, pL.tilt, FLYBUN);
    const air0 = gy - (by0 + 15 * s);
    const G = 3600;
    const vy = (0.5 * G * T * T - air0) / T;
    const xLand = cx0 + dAt(tland) * s - 540 * s;
    const vx = (xLand - bx0) / T;
    // it squashes on the stones for a drawing, then hops once, low, and rolls to a stop
    const tB0 = Math.ceil(tland * 12 + 0.5) / 12;
    const Tb = 2 / 12;
    const ttap = tB0 + Tb;
    const vxb = 0.25 * vx;
    const Troll = 0.4;
    const vr = 0.12 * vx;
    const bunAt = (t) => {
      const tau = t - tL;
      if (tau < T) return { x: bx0 + vx * tau, air: Math.max(0, air0 + vy * tau - 0.5 * G * tau * tau), rot: -9 * tau };
      if (t < tB0) return { x: xLand, air: 0, rot: -9 * T };
      if (t < ttap) {
        const u = t - tB0;
        return { x: xLand + vxb * u, air: Math.max(0, 0.5 * G * u * (Tb - u)), rot: -9 * T - 4 * u };
      }
      const u = Math.min(t - ttap, Troll);
      const dx = vr * (u - (u * u) / (2 * Troll));
      return { x: xLand + vxb * Tb + dx, air: 0, rot: -9 * T - 4 * Tb + dx / (15 * s) };
    };
    stepCues(kit, dAt, dur, S, 0);
    rattleCues(kit, dAt, dur, [tb, tland, t2, ttap]);
    kit.cue('bump2', t2, 'thump', { minor: true });
    kit.cue('tap', ttap, 'tap', { minor: true });
    return (g, t0) => {
      const t = dbgT('track', t0);
      const tw = kit.twos(t);
      const cam = vs * t;
      dbg(g, 'track');
      g.drawImage(st.sky, -cam * 0.04 - 20, 0);
      g.drawImage(st.far, -cam * 0.45, 0);
      for (const [i, [cx, cy]] of st.farCh.entries()) {
        const sx = cx - cam * 0.45;
        if (sx > -200 && sx < 2100) smoke(kit, g, t, sx, cy, 0.6, 140 + i);
      }
      g.drawImage(st.mist, -cam * 0.6 + t * 10, 440);
      g.drawImage(st.near, -cam, 0);
      for (const [i, [cx, cy]] of st.nearCh.entries()) {
        const sx = cx - cam;
        if (sx > -200 && sx < 2100) smoke(kit, g, t, sx, cy, 1.0, 160 + i);
      }
      g.drawImage(st.road, -cam, 822);
      g.save();
      g.translate(-cam, 0);
      // the raised stone in the road
      castShadow(g, stoneX, gy + 2, 18 * s, 20, SUN_STREET.dir, 0.35);
      shape(kit, g, [[stoneX - 19 * s, gy + 3], [stoneX - 13 * s, gy - 9 * s], [stoneX, gy - 14 * s], [stoneX + 13 * s, gy - 8 * s], [stoneX + 19 * s, gy + 3]], { base: '#9a90a2', shade: '#6c6380', rim: '#f0d0b0', light: LIGHT, sd: 5, rw: 2 }, 2.2, 600);
      const d = dAt(tw);
      const cx = cx0 + d * s;
      const hx = cx - GAP * s;
      const p = bumpAt(tw);
      const flying = t >= tL;
      const b = flying ? bunAt(t) : null;
      if (b) bunShadow(kit, g, b.x, gy, s, b.air, SUN_STREET);
      const cp = cart(kit, g, cx, gy, s, { roll: d / 42, lift: p.lift, tilt: p.tilt, jig: p.jig, bun: !flying });
      kit.prop('推车', { x: cx, y: gy, s, points: cp });
      const hp = hedgehog(kit, g, hx, gy, s, { d, S, grip: cp.handle });
      kit.actor('刺猬', { x: hx, y: gy, s, facing: 'right', points: hp });
      if (b) {
        const e1 = t - tland;
        const e2 = t - ttap;
        let squash = 1;
        if (e1 > 0 && t < tB0 + 0.02) squash = 1 - 0.2 * Math.sin((Math.PI * e1) / (tB0 + 0.02 - tland));
        if (e2 > 0) squash = 1 - 0.1 * Math.exp(-e2 * 10) * Math.cos(e2 * 26);
        const bp = bunDraw(kit, g, b.x, gy - b.air, s, { rot: b.rot, squash });
        kit.prop('面包', { x: b.x, y: gy, s, air: b.air, ballistic: true, from: '推车', points: bp });
      }
      g.restore();
    };
  },

  // 3. A pigeon comes down by the bun and pecks it; the baker stops, looks back over his shoulder, and goes on.
  pigeon(kit, scene) {
    const st = street(kit, 70, 1920);
    const s = 0.9;
    const gy = 945;
    const vL = 140;
    const S = 50;
    const tLand = scene.events.land;
    const tPeck = scene.events.peck;
    const dur = scene.duration;
    const vfun = (t) => vL * (t < 1.15 ? 1 : t < 1.65 ? 1 - kit.smooth((t - 1.15) / 0.5) : t < 3.0 ? 0 : kit.smooth((t - 3.0) / 0.45));
    const dRaw = table(vfun, dur + 0.2);
    const dStop = dRaw(2.5);
    // phase the stride so that both feet are planted when the baker stands still
    const phi = (((-(dStop / (2 * S)) % 0.5) + 0.5) % 0.5);
    const dAt = (tw) => dRaw(tw);
    stepCues(kit, dAt, dur, S, phi);
    rattleCues(kit, dAt, dur, [tLand, tPeck]);
    for (let k = 1; k < 0.68 * 12 * tLand; k++) if (k % 2 === 1) kit.cue(`flap${k}`, k / 12, 'flap', { minor: true });
    kit.cue('coo', 1.45, 'coo', { minor: true });
    kit.cue('peck2', 2.58, 'peck', { minor: true });
    const bunX = 610;
    const bunY = 1002;
    const bunS = 1.05;
    const pgX = 512;
    const pgY = 1008;
    const pgS = 0.95;
    const peckAt = (tw) => {
      const one = (a, b, c) => (tw < a ? 0 : tw < b ? kit.smooth((tw - a) / (b - a)) : tw < c ? 1 : Math.max(0, 1 - (tw - c) / 0.17));
      return Math.max(one(tPeck - 0.17, tPeck - 0.006, tPeck + 0.24), one(2.42, 2.58, 2.66) * 0.9);
    };
    return (g, t0, dd) => {
      const t = dbgT('pigeon', t0);
      const tw = kit.twos(t);
      dbg(g, 'pigeon');
      const z = 1 + 0.025 * kit.smooth(t / dd);
      g.translate(900, 700);
      g.scale(z, z);
      g.translate(-900, -700);
      g.drawImage(st.sky, 0, 0);
      g.drawImage(st.far, 0, 0);
      for (const [i, [cx, cy]] of st.farCh.entries()) smoke(kit, g, t, cx, cy, 0.6, 240 + i);
      g.drawImage(st.mist, -120 + t * 10, 440);
      g.drawImage(st.near, 0, 0);
      for (const [i, [cx, cy]] of st.nearCh.entries()) smoke(kit, g, t, cx, cy, 1.0, 260 + i);
      g.drawImage(st.road, 0, 822);
      // the baker: walking on, stopping, a beat, the look back, a beat, and on again
      const d = dAt(tw);
      const hx = 960 + d * s;
      const cx = hx + GAP * s;
      const rat = d > 0 ? 1.6 * (0.5 - 0.5 * Math.cos((2 * Math.PI * d) / 34)) : 0;
      const cp = cart(kit, g, cx, gy, s, { roll: d / 42, lift: rat });
      kit.prop('推车', { x: cx, y: gy, s, points: cp });
      const turn = Math.min(kit.smooth((tw - 1.9) / 0.25), 1 - kit.smooth((tw - 2.65) / 0.25));
      const hp = hedgehog(kit, g, hx, gy, s, { d, S, phi, turn, grip: cp.handle });
      kit.actor('刺猬', { x: hx, y: gy, s, facing: 'right', points: hp });
      // the bun where it fell
      bunShadow(kit, g, bunX, bunY, bunS, 0, SUN_STREET);
      const bp = bunDraw(kit, g, bunX, bunY, bunS, { rot: -3.7 });
      kit.prop('面包', { x: bunX, y: bunY, s: bunS, points: bp });
      // the pigeon
      let px = pgX;
      let air = 0;
      let wing = 'fold';
      let legs = 'down';
      let tilt = 0;
      if (tw < tLand) {
        const tau = tw / tLand;
        const pp = 1 - (1 - tau) ** 1.6;
        px = kit.lerp(-170, pgX, pp);
        air = 470 * (1 - pp) ** 1.25;
        if (tau < 0.62) wing = Math.floor(tw * 12) % 2 ? 'down' : 'up';
        else if (tau < 0.88) wing = 'mid';
        else wing = 'up';
        legs = tau < 0.7 ? 'tuck' : 'forward';
        tilt = -0.1 - 0.22 * kit.smooth((tau - 0.75) / 0.25);
      } else if (tw < tLand + 0.26) {
        wing = Math.floor(tw * 12) % 2 ? 'mid' : 'up';
        tilt = -0.12;
      } else if (tw < tLand + 0.42) {
        wing = 'mid';
      }
      const bob = tw > tLand + 0.5 && tw < tPeck - 0.2 ? (Math.floor(tw * 6) % 2) * 2 : 0;
      const pk = tw >= tLand ? peckAt(tw) : 0;
      const pp = pigeon(kit, g, px, pgY, pgS, { air, wing, legs, tilt, pk, target: bp.side, bob });
      kit.actor('鸽子', { x: px, y: pgY, s: pgS, facing: 'right', points: pp });
    };
  },
};
