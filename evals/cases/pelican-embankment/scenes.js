// "Pelican on the embankment": the character and the three shots.
// A shot is build(kit, scene) -> draw(g, t, dur): build paints its plates once; draw composes a frame
// from the time t into the shot alone.

const INK = '#3b2a2e';
const C = {
  feather: '#fbf4e6', featherShade: '#c9b9c9', featherRim: '#fff3d6',
  bill: '#f2a33a', billShade: '#c9762c', pouch: '#f6c36b', pouchShade: '#d8934a',
  tip: '#4a4a62', tipShade: '#34344a', foot: '#f08a3c', footShade: '#c0602a', eye: '#2a1e24',
  frame: '#2f7f8a', frameShade: '#1f5763', frameRim: '#7fc0bf', tire: '#3a3040', rim: '#cfc6c0',
  basket: '#b07d4a', basketShade: '#7d5434', fish: '#8fa3b8', fishShade: '#5f7190', seat: '#5a3a36',
};

// ---------- cel helpers ----------
function path(kit, pts, closed = true) {
  const p = kit.spline(closed ? [...pts, pts[0], pts[1]] : pts, 8);
  const q = closed ? p.slice(0, -8) : p;
  const P = new Path2D();
  P.moveTo(q[0][0], q[0][1]);
  for (const v of q) P.lineTo(v[0], v[1]);
  if (closed) P.closePath();
  return { P, q };
}

/** Flat colour, one hard shadow away from the light, a thin rim toward it. */
function cel(g, P, { base, shade, rim, light = [1, -0.4], sd = 10, rw = 3 }) {
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

function line(kit, g, q, w, seed, closed = true) {
  const r = kit.rng(seed);
  const pts = (closed ? [...q, q[0]] : q).filter((_, i, a) => i % 3 === 0 || i === a.length - 1);
  kit.ink(g, pts.map(([x, y]) => [x, y, w * (0.7 + 0.6 * r())]), INK, { taper: !closed });
}

// ---------- the pelican on its bicycle, in profile facing right ----------
// Origin at the ground under the bottom bracket, units in pixels at scale 1.
function wheel(kit, g, cx, cy, R, spin, light) {
  g.beginPath();
  g.arc(cx, cy, R, 0, Math.PI * 2);
  g.lineWidth = 11;
  g.strokeStyle = C.tire;
  g.stroke();
  g.beginPath();
  g.arc(cx, cy, R - 7, 0, Math.PI * 2);
  g.lineWidth = 2.5;
  g.strokeStyle = C.rim;
  g.stroke();
  g.lineWidth = 1.2;
  g.strokeStyle = 'rgba(70,60,70,0.75)';
  for (let k = 0; k < 16; k++) {
    const a = spin + (k / 16) * Math.PI * 2;
    g.beginPath();
    g.moveTo(cx + Math.cos(a) * 6, cy + Math.sin(a) * 6);
    g.lineTo(cx + Math.cos(a + 0.18) * (R - 8), cy + Math.sin(a + 0.18) * (R - 8));
    g.stroke();
  }
  g.beginPath();
  g.arc(cx, cy, 7, 0, Math.PI * 2);
  g.fillStyle = C.rim;
  g.fill();
  // warm rim on the tyre where the low sun catches it
  g.beginPath();
  g.arc(cx, cy, R + 3, light - 0.9, light + 0.9);
  g.lineWidth = 2;
  g.strokeStyle = 'rgba(255,214,150,0.55)';
  g.stroke();
}

function tube(g, a, b, w, col, shadeCol) {
  g.lineCap = 'round';
  g.beginPath();
  g.moveTo(a[0], a[1]);
  g.lineTo(b[0], b[1]);
  g.lineWidth = w + 3;
  g.strokeStyle = INK;
  g.stroke();
  g.lineWidth = w;
  g.strokeStyle = col;
  g.stroke();
  if (shadeCol) {
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const l = Math.hypot(dx, dy) || 1;
    const ox = (dy / l) * w * 0.25;
    const oy = (-dx / l) * w * 0.25;
    g.beginPath();
    g.moveTo(a[0] - ox, a[1] - oy);
    g.lineTo(b[0] - ox, b[1] - oy);
    g.lineWidth = w * 0.4;
    g.strokeStyle = shadeCol;
    g.stroke();
  }
}

/** Two-bone leg from hip to foot, knee bending forward. */
function leg(hip, foot, L1, L2) {
  const dx = foot[0] - hip[0];
  const dy = foot[1] - hip[1];
  const d = Math.min(L1 + L2 - 0.5, Math.hypot(dx, dy));
  const a = Math.atan2(dy, dx);
  const k = Math.acos((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d));
  return [hip[0] + Math.cos(a - k) * L1, hip[1] + Math.sin(a - k) * L1];
}

function drawLeg(kit, g, hip, foot, shade, seed) {
  const knee = leg(hip, foot, 72, 70);
  for (const [a, b, w] of [[hip, knee, 15], [knee, foot, 11]]) {
    g.lineCap = 'round';
    g.beginPath();
    g.moveTo(a[0], a[1]);
    g.lineTo(b[0], b[1]);
    g.lineWidth = w + 4;
    g.strokeStyle = INK;
    g.stroke();
    g.lineWidth = w;
    g.strokeStyle = shade ? C.footShade : C.foot;
    g.stroke();
  }
  // webbed foot flat on the pedal
  const { P, q } = path(kit, [[foot[0] - 14, foot[1] - 4], [foot[0] + 8, foot[1] - 9], [foot[0] + 34, foot[1] - 4], [foot[0] + 36, foot[1] + 4], [foot[0] - 10, foot[1] + 5]]);
  cel(g, P, { base: shade ? C.footShade : C.foot, shade: C.footShade, light: [1, -0.6], sd: 4 });
  line(kit, g, q, 2.2, seed);
}

/**
 * pose: { crank (radians), bob, jolt, pouch (swing, -1..1), bell (0..1 wing lifted to the bell),
 *         crest (sway), spin (wheel angle), light (radians, direction the sun comes from) }
 */
export function pelican(kit, g, x, y, s, pose) {
  const { crank = 0, bob = 0, jolt = 0, pouch = 0, bell = 0, crest = 0, spin = 0, light = -0.4 } = pose;
  const L = [Math.cos(light), Math.sin(light)];
  g.save();
  g.translate(x, y);
  g.scale(s, s);

  const R = 86;
  const rear = [-150, -R];
  const front = [152, -R];
  const bb = [-18, -84];
  const seatTop = [-62, -228];
  const headTop = [98, -222];
  const headBot = [112, -178];
  const p1 = [bb[0] + Math.cos(crank) * 32, bb[1] + Math.sin(crank) * 32];
  const p2 = [bb[0] - Math.cos(crank) * 32, bb[1] - Math.sin(crank) * 32];

  // far leg and pedal first
  const lift = -bob - jolt;
  const SIT = 24; // the body rests on the saddle
  const hip = [-48, -242 + lift];
  drawLeg(kit, g, [hip[0] + 6, hip[1] - 2], [p2[0], p2[1] - 6], true, 21);

  // wheels and frame
  wheel(kit, g, rear[0], rear[1], R, spin, light);
  wheel(kit, g, front[0], front[1], R, spin, light);
  tube(g, bb, rear, 7, C.frame, C.frameShade);
  tube(g, seatTop, rear, 6, C.frame, C.frameShade);
  tube(g, bb, seatTop, 9, C.frame, C.frameShade);
  tube(g, [seatTop[0] + 4, seatTop[1] + 14], headTop, 9, C.frame, C.frameShade);
  tube(g, bb, headBot, 10, C.frame, C.frameShade);
  tube(g, headTop, headBot, 12, C.frame, C.frameShade);
  tube(g, headBot, front, 7, C.frame, C.frameShade);
  // chainring and crank
  g.beginPath();
  g.arc(bb[0], bb[1], 20, 0, Math.PI * 2);
  g.fillStyle = '#8a8088';
  g.fill();
  g.lineWidth = 2.5;
  g.strokeStyle = INK;
  g.stroke();
  tube(g, bb, p1, 5, '#9a9098');
  g.fillStyle = '#5a5058';
  g.fillRect(p1[0] - 13, p1[1] - 4, 26, 7);
  // saddle and handlebar
  const saddle = path(kit, [[-92, -238], [-40, -244], [-30, -236], [-80, -228]]);
  cel(g, saddle.P, { base: C.seat, shade: '#3a2426', light: L, sd: 3 });
  line(kit, g, saddle.q, 2.4, 31);
  tube(g, headTop, [92, -258], 6, '#8a8088');
  tube(g, [92, -258], [58, -262], 6, '#8a8088');
  // the bell on the bar
  g.beginPath();
  g.arc(80, -270, 8, Math.PI, 0);
  g.fillStyle = '#e8d070';
  g.fill();
  g.lineWidth = 2;
  g.strokeStyle = INK;
  g.stroke();

  // basket with a fish
  const fish = path(kit, [[148, -262], [152, -292], [162, -312], [170, -318], [178, -312], [182, -290], [178, -262]]);
  cel(g, fish.P, { base: C.fish, shade: C.fishShade, rim: '#e8eef2', light: L, sd: 6, rw: 2 });
  line(kit, g, fish.q, 2.2, 41);
  const fin = path(kit, [[166, -316], [150, -344], [160, -340], [170, -326], [182, -342], [190, -344], [176, -314]]);
  cel(g, fin.P, { base: C.fish, shade: C.fishShade, light: L, sd: 4 });
  line(kit, g, fin.q, 2, 43);
  kit.ink(g, [[156, -300, 1.2], [166, -296, 1.6], [176, -300, 1.2]], 'rgba(60,70,100,0.7)');
  const basket = path(kit, [[122, -262], [200, -266], [194, -206], [128, -204]]);
  cel(g, basket.P, { base: C.basket, shade: C.basketShade, light: L, sd: 12 });
  g.save();
  g.clip(basket.P);
  g.strokeStyle = 'rgba(90,58,36,0.6)';
  g.lineWidth = 2;
  for (let k = 0; k < 6; k++) {
    g.beginPath();
    g.moveTo(122, -255 + k * 10);
    g.lineTo(200, -258 + k * 10);
    g.stroke();
  }
  g.restore();
  line(kit, g, basket.q, 2.6, 42);

  // body: a big tilted oval of feathers, rising and falling with the stroke
  g.translate(0, lift + SIT);
  const body = path(kit, [[-128, -300], [-98, -340], [-30, -360], [28, -350], [52, -318], [30, -276], [-40, -262], [-104, -272]]);
  cel(g, body.P, { base: C.feather, shade: C.featherShade, rim: C.featherRim, light: L, sd: 16, rw: 4 });
  // a few feather marks
  const fr = kit.rng(7);
  g.strokeStyle = 'rgba(150,130,160,0.55)';
  g.lineWidth = 1.6;
  for (let k = 0; k < 7; k++) {
    const fx = -100 + fr() * 120;
    const fy = -320 + fr() * 40;
    g.beginPath();
    g.moveTo(fx, fy);
    g.quadraticCurveTo(fx - 8, fy + 6, fx - 16, fy + 4);
    g.stroke();
  }
  line(kit, g, body.q, 3, 8);
  // tail feathers
  const tail = path(kit, [[-120, -306], [-160, -300], [-168, -290], [-122, -282]]);
  cel(g, tail.P, { base: C.feather, shade: C.featherShade, light: L, sd: 6 });
  line(kit, g, tail.q, 2.4, 9);

  // neck in an S, head, crest
  const neckBack = [[20, -350], [10, -392], [26, -428], [48, -452]];
  const neckFront = [[62, -446], [52, -414], [40, -384], [54, -332]];
  const neck = path(kit, [...neckBack, ...neckFront]);
  cel(g, neck.P, { base: C.feather, shade: C.featherShade, rim: C.featherRim, light: L, sd: 9, rw: 3 });
  line(kit, g, neck.q, 2.8, 11);
  const head = path(kit, [[40, -452], [56, -474], [84, -476], [96, -458], [86, -440], [60, -436]]);
  cel(g, head.P, { base: C.feather, shade: C.featherShade, rim: C.featherRim, light: L, sd: 6, rw: 3 });
  line(kit, g, head.q, 2.6, 12);
  for (let k = 0; k < 3; k++) {
    const a = -2.5 + k * 0.25 + crest * 0.25;
    kit.ink(g, [[46, -470, 4], [46 + Math.cos(a) * 22, -470 + Math.sin(a) * 22, 1.2]], '#e9c98a');
  }

  // pouch first (it hangs under the bill), swinging behind the head's motion
  const sag = 26 + pouch * 9;
  const swing = pouch * 10;
  const pouchShape = path(kit, [[74, -440], [118, -430 + sag * 0.5 + swing * 0.3], [170, -416 + sag * 0.6], [214, -402], [200, -398], [150, -394 + sag * 0.2 + swing], [100, -404 + sag * 0.6 + swing], [70, -426]]);
  cel(g, pouchShape.P, { base: C.pouch, shade: C.pouchShade, light: L, sd: 8 });
  line(kit, g, pouchShape.q, 2.4, 13);
  // upper bill, long and hooked
  const bill = path(kit, [[86, -458], [140, -446], [212, -420], [228, -410], [218, -404], [140, -428], [84, -440]]);
  cel(g, bill.P, { base: C.bill, shade: C.billShade, rim: '#ffd9a0', light: L, sd: 5, rw: 2 });
  line(kit, g, bill.q, 2.6, 14);
  kit.ink(g, [[92, -448, 1.5], [150, -436, 1.8], [205, -415, 1]], 'rgba(120,70,40,0.8)');
  // eye with a catchlight
  g.beginPath();
  g.ellipse(76, -459, 5.5, 6, 0, 0, Math.PI * 2);
  g.fillStyle = C.eye;
  g.fill();
  g.beginPath();
  g.arc(78, -461, 1.8, 0, Math.PI * 2);
  g.fillStyle = '#fff6e0';
  g.fill();
  kit.ink(g, [[66, -464, 1.2], [76, -468, 2], [86, -464, 1.2]], INK);

  // near wing: folded along the body, the hand reaching forward to the bar (or up to the bell)
  const wristY = -312 - bell * 16;
  const grip = lerpPt([60, -262 - lift - SIT], [82, -278 - lift - SIT], bell);
  const [gx, gy] = grip;
  const wing = path(kit, [[16, -338], [-12, -350], [-70, -338], [-142, -304], [-150, -292], [-96, -290], [-30, -288],
    [6, wristY + 30], [gx - 22, gy + 8], [gx - 4, gy + 10], [gx + 10, gy + 2], [gx + 6, gy - 10], [gx - 14, gy - 14], [12, wristY - 2], [2, -322]]);
  cel(g, wing.P, { base: '#ece3d9', shade: '#b4a7bb', rim: C.featherRim, light: L, sd: 9, rw: 3 });
  // dark primaries at the folded tip
  const tips = path(kit, [[-96, -296], [-142, -304], [-152, -292], [-118, -284]]);
  cel(g, tips.P, { base: C.tip, shade: C.tipShade, light: L, sd: 4 });
  line(kit, g, wing.q, 2.8, 15);
  // the hand's feathers: three short separations at the grip
  for (let k = 0; k < 3; k++) kit.ink(g, [[gx - 26 + k * 7, gy - 8 + k * 2, 1.6], [gx - 6 + k * 5, gy + 2 + k * 2, 0.8]], 'rgba(120,100,130,0.8)');
  kit.ink(g, [[-20, -330, 1.4], [-60, -318, 2], [-100, -302, 1.2]], 'rgba(120,100,130,0.7)');

  // near leg on top
  g.translate(0, -lift - SIT);
  drawLeg(kit, g, hip, [p1[0], p1[1] - 6], false, 22);
  g.restore();
}

function lerpPt(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

/** A ground shadow under the bike: soft-edged, violet, flattened. */
function groundShadow(g, x, y, s, len = 330) {
  g.save();
  g.translate(x, y);
  g.scale(s, s * 0.18);
  const grd = g.createRadialGradient(0, 0, 10, 0, 0, len * 0.6);
  grd.addColorStop(0, 'rgba(70,50,100,0.45)');
  grd.addColorStop(1, 'rgba(70,50,100,0)');
  g.fillStyle = grd;
  g.beginPath();
  g.ellipse(0, 0, len * 0.6, len * 0.6, 0, 0, Math.PI * 2);
  g.fill();
  g.restore();
}

/** The pose at time t: pedalling on twos, bob twice a revolution, pouch following behind. */
function ride(kit, t, { cadence = 1.2, jolts = [], bellAt = [] } = {}) {
  const d = kit.twos(t);
  const crank = (d / cadence) * Math.PI * 2;
  const bob = 3 * Math.abs(Math.sin(crank));
  let jolt = 0;
  let wobble = 0;
  for (const j of jolts) {
    const u = d - j;
    if (u >= 0 && u < 1.2) {
      jolt += 16 * Math.exp(-u * 7) * Math.sin(u * 16);
      wobble += Math.exp(-u * 3.2) * Math.sin(u * 13 - 0.6);
    }
  }
  let bell = 0;
  for (const b of bellAt) bell = Math.max(bell, kit.smooth((d - b + 0.25) / 0.2) * (1 - kit.smooth((d - b - 0.45) / 0.25)));
  // the pouch lags the body by a quarter turn
  const pouch = 0.35 * Math.sin(crank * 2 - 1.2) + wobble;
  const crest = 0.5 * Math.sin(crank * 2 - 1.8) + wobble * 0.8;
  return { crank, bob, jolt: Math.max(0, jolt), pouch, crest, bell, spin: crank * 1.9 };
}

// ---------- painted plates ----------
const SKY = [[0, '#3d4f8a'], [0.42, '#8a86b8'], [0.75, '#f2b98a'], [1, '#ffd99a']];
const CLOUD = { light: '#ffe2b8', half: '#e6a58f', shadow: '#8f7aa6' };

function paintSky(kit, g, w, horizon, sun, seed) {
  const r = kit.rng(seed);
  for (let y = 0; y < horizon; y += 2) {
    g.fillStyle = kit.css(kit.ramp(SKY, y / horizon));
    g.fillRect(0, y, w, 2);
  }
  kit.mottle(g, 0, 0, w, horizon, (x, y) => kit.ramp(SKY, y / horizon), { n: Math.round(w / 3), size: 70, alpha: 0.12, r, angle: 0 });
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

function paintClouds(kit, g, specs, sun) {
  for (const [i, [cx, cy, cw, ch]] of specs.entries()) {
    const dx = sun[0] - cx;
    const dy = sun[1] - cy;
    const l = Math.hypot(dx, dy) || 1;
    // farther from the sun, the cloud sits more in shadow
    const near = kit.clamp(1 - l / 1800);
    kit.cloud(g, cx, cy, cw, ch, {
      light: kit.mix(CLOUD.half, CLOUD.light, 0.5 + 0.5 * near),
      half: kit.mix(CLOUD.shadow, CLOUD.half, 0.6 + 0.4 * near),
      shadow: kit.mix('#6d6194', CLOUD.shadow, 0.5 + 0.5 * near),
      lx: dx / l, ly: dy / l, r: kit.rng(100 + i * 17), lobes: 7 + (i % 4),
    });
  }
}

function paintFarBank(kit, g, w, y0, seed) {
  const r = kit.rng(seed);
  // distant hills
  g.beginPath();
  g.moveTo(0, y0);
  for (let x = 0; x <= w; x += 40) g.lineTo(x, y0 - 30 - 26 * Math.sin(x / 260 + 1) - 14 * Math.sin(x / 97) - r() * 6);
  g.lineTo(w, y0 + 10);
  g.lineTo(0, y0 + 10);
  g.fillStyle = kit.css('#9a92bd');
  g.fill();
  // the town: roofs and a few lit windows
  for (let x = 20; x < w; x += 26 + r() * 50) {
    const bw = 18 + r() * 40;
    const bh = 10 + r() * 34;
    g.fillStyle = kit.css(kit.jit('#6f6f9e', r, 14));
    g.fillRect(x, y0 - bh, bw, bh + 12);
    if (r() < 0.45) {
      g.fillStyle = kit.css('#ffcf86', 0.85);
      g.fillRect(x + bw * 0.3, y0 - bh * 0.6, 3, 3);
    }
  }
  g.fillStyle = kit.css('#5f6595');
  g.fillRect(0, y0, w, 14);
}

function paintBridge(kit, g, x0, x1, y, h) {
  g.strokeStyle = kit.css('#56588a', 0.95);
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
    g.fillStyle = kit.css('#56588a');
    g.fillRect(px - 4, y, 8, 26);
  }
}

function paintRiver(kit, g, w, y0, y1, sunX, seed) {
  const r = kit.rng(seed);
  for (let y = y0; y < y1; y += 2) {
    const u = (y - y0) / (y1 - y0);
    // the water mirrors the sky, upside down, a little darker
    g.fillStyle = kit.css(kit.mix(kit.ramp(SKY, 1 - u * 0.75), '#4a4f80', 0.18 + u * 0.25));
    g.fillRect(0, y, w, 2);
  }
  for (let i = 0; i < w / 9; i++) {
    const y = y0 + r() * (y1 - y0);
    const u = (y - y0) / (y1 - y0);
    const x = r() * w;
    const L = 40 + r() * 160 * (0.4 + u);
    const lightStroke = r() < 0.6;
    const col = lightStroke ? kit.mix(kit.ramp(SKY, 1 - u * 0.6), '#fff1d0', 0.25) : kit.mix(kit.ramp(SKY, 0.35), '#6a6a98', 0.3);
    kit.stroke(g, [[x, y], [x + L * 0.5, y + (r() - 0.5) * 1.2], [x + L, y]], { width: 2 + u * 3, color: col, alpha: 0.22, r, bristles: 3 });
  }
}

/** Glitter under the sun: on twos, each glint has its own phase. */
function glitter(kit, g, t, sunX, y0, y1, spread, seed, ox = 0, below = () => Infinity, onWater = () => true) {
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
    g.fillStyle = kit.css('#ffe2a0', 0.85);
    g.fillRect(x, y, 6 + u * 16, 2);
  }
}

function paintSlope(kit, g, w, topAt, h, seed, { lit = 0.5 } = {}) {
  const r = kit.rng(seed);
  const top = (x) => topAt(x);
  // the big shape: lit at the crest, cooling and going violet toward the foot
  for (let x = 0; x < w; x += 3) {
    const y0 = top(x);
    const grd = g.createLinearGradient(0, y0, 0, y0 + h);
    grd.addColorStop(0, kit.css(kit.mix('#a3964f', '#d2c067', lit)));
    grd.addColorStop(0.45, kit.css(kit.mix('#8a8650', '#a69a58', lit * 0.6)));
    grd.addColorStop(1, kit.css('#6a6458'));
    g.fillStyle = grd;
    g.fillRect(x, y0, 3, h);
  }
  // broad patches of colour so the slope is not one gradient
  kit.mottle(g, 0, top(w / 2) - 40, w, h + 80, (x, y) => {
    const u = kit.clamp((y - top(x)) / h);
    return kit.mix(kit.mix('#c9b45e', '#94904f', u), '#7d6d98', u * 0.3);
  }, { n: Math.round(w * h / 9000), size: 120, alpha: 0.12, r, angle: -0.2 });
  // strokes down the slope: fewer, light, each its own length; quiet patches left alone
  for (let i = 0; i < w * h / 2600; i++) {
    const x = r() * w;
    const y = top(x) + r() * h;
    const u = (y - top(x)) / h;
    if (Math.sin(x * 0.004 + y * 0.01) > 0.55) continue;
    const col = kit.mix(kit.mix('#d8c878', '#9a925a', u), '#8a7aa0', u * 0.25);
    const L = 10 + r() * 26 * (0.5 + u);
    kit.stroke(g, [[x, y], [x + 4 + r() * 6, y + L * 0.5], [x + 6 + r() * 8, y + L]], { width: 4 + u * 7, color: col, alpha: 0.3, r, bristles: 3 });
  }
}

function paintRoad(kit, g, w, topAt, depth, seed) {
  const r = kit.rng(seed);
  for (let x = 0; x < w; x += 2) {
    const top = topAt(x);
    g.fillStyle = kit.css(kit.mix('#e3c9a1', '#b89a86', 0.3));
    g.fillRect(x, top, 2, depth(x));
  }
  for (let i = 0; i < w * 1.2; i++) {
    const x = r() * w;
    const y = topAt(x) + r() * depth(x);
    g.fillStyle = kit.css(kit.jit(r() < 0.6 ? '#e3c9a1' : '#9e8478', r, 20), 0.7);
    g.fillRect(x, y, 1.5 + r() * 4, 1 + r() * 2);
  }
  // the near verge catches the light
  for (let x = 0; x < w; x += 2) {
    g.fillStyle = 'rgba(255,226,170,0.5)';
    g.fillRect(x, topAt(x), 2, 2);
  }
}

/** Reeds with plumed heads, each blade drawn as its own curve; sway on twos. */
function reeds(kit, g, t, specs, seed, { backlit = false } = {}) {
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
      const col = backlit ? kit.mix('#5b4a5e', '#3e3550', r()) : kit.mix('#8a7d4a', '#b29a5a', r());
      kit.ink(g, [[x, base, 4], [x + sway * 0.4, base - hgt * 0.55, 3], [tipX, tipY, 1.4]], kit.css(col));
      if (r() < 0.55) {
        // the plume
        const pc = backlit ? '#ffd9a8' : '#efe0c0';
        for (let k = 0; k < 6; k++) {
          const a = -1.9 + (k / 6) * 0.9 + sway * 0.004;
          kit.ink(g, [[tipX, tipY, 2.5], [tipX + Math.cos(a) * 26, tipY + Math.sin(a) * 26 + 10, 0.8]], kit.css(pc, 0.8));
        }
      }
    }
  }
}

/**
 * An egret in flight, seen from the side: broad rounded wings with fingered tips, the neck folded
 * back in an S, legs trailing. phase 0 = wings fully down, 1 = fully up.
 */
function egret(kit, g, x, y, s, phase, seed) {
  const r = kit.rng(seed);
  g.save();
  g.translate(x, y);
  g.scale(s, s);
  const tipY = -78 + phase * 128;
  const tipX = -8 + r() * 10;
  const wing = (dx, col, shadeCol) => {
    const pts = [[-12 + dx, -4], [-4 + dx, -10 + tipY * 0.25], [tipX + 6 + dx, tipY * 0.85], [tipX + dx, tipY],
      [tipX - 10 + dx, tipY * 0.94], [tipX - 18 + dx, tipY * 0.84], [tipX - 26 + dx, tipY * 0.7], [-30 + dx, tipY * 0.35], [-26 + dx, 2]];
    const { P, q } = path(kit, pts);
    cel(g, P, { base: col, shade: shadeCol, light: [0.6, -0.8], sd: 6 });
    line(kit, g, q, 1.8, seed + dx);
  };
  wing(10, '#e6dcd8', '#bfb2c2');
  // legs trailing behind
  kit.ink(g, [[-30, 4, 2], [-62, 12, 1.4], [-72, 14, 1]], '#3b2a2e');
  // body
  const body = path(kit, [[-34, 2], [-16, -8], [14, -9], [28, -2], [16, 7], [-14, 8]]);
  cel(g, body.P, { base: '#fffaf0', shade: '#d9cbd2', rim: '#fff3d6', light: [0.6, -0.8], sd: 5, rw: 2 });
  line(kit, g, body.q, 2, seed + 1);
  // neck folded back in an S, small head, long yellow bill
  const neck = path(kit, [[20, -6], [32, -14], [30, -22], [40, -26], [46, -20], [38, -14], [28, 0]]);
  cel(g, neck.P, { base: '#fffaf0', shade: '#d9cbd2', light: [0.6, -0.8], sd: 3 });
  line(kit, g, neck.q, 1.6, seed + 2);
  kit.ink(g, [[46, -23, 3], [62, -20, 2], [74, -18, 0.8]], '#e8b04a');
  g.beginPath();
  g.arc(43, -24, 1.6, 0, Math.PI * 2);
  g.fillStyle = '#2a1e24';
  g.fill();
  wing(0, '#fffaf0', '#cdbfca');
  g.restore();
}

// ---------- shots ----------
export default {
  /** Wide: the embankment at the last of the light, a small pelican riding along the top. */
  wide(kit, scene) {
    const PW = 2240;
    const sky = kit.layer(PW, 1080);
    const sun = [1580, 520];
    paintSky(kit, sky.g, PW, 600, sun, 1);
    paintClouds(kit, sky.g, [[360, 230, 760, 260], [1080, 150, 560, 170], [1520, 330, 520, 160], [2000, 210, 700, 230], [720, 420, 380, 90]], sun);
    paintFarBank(kit, sky.g, PW, 585, 5);
    paintBridge(kit, sky.g, 1240, 1720, 572, 34);
    paintRiver(kit, sky.g, PW, 598, 760, sun[0], 6);
    const roadTop = (x) => 812 - x * 0.06;
    paintSlope(kit, sky.g, PW, (x) => roadTop(x) - 70, 70, 7, { lit: 0.7 });
    paintRoad(kit, sky.g, PW, roadTop, () => 26, 8);
    paintSlope(kit, sky.g, PW, (x) => roadTop(x) + 26, 400, 9, { lit: 0.35 });
    kit.grass(sky.g, [0, PW], (x) => roadTop(x) + 28, { n: 900, len: 16, colors: ['#d2c067', '#b3a25a', '#a0965a', '#b8a28e'], lean: 0.25, r: kit.rng(10), width: 1.6 });
    kit.tooth(sky.g, PW, 1080, 12, 0.05);
    return (g, t, dur) => {
      const pan = kit.smooth(t / dur) * 200;
      g.drawImage(sky.canvas, -pan, 0);
      glitter(kit, g, t, sun[0], 606, 750, 120, 13, pan, (x) => roadTop(x + pan) - 78);
      const px = 300 + t * 120;
      const s = 0.25;
      const y = roadTop(px + pan) + 14;
      groundShadow(g, px - pan * 0 - 6, y + 2, s);
      pelican(kit, g, px, y, s, { ...ride(kit, t, {}), light: -0.25 });
      reeds(kit, g, t, [[-20, 460, 1110, 140, 330, 70], [1700, 1960, 1110, 90, 220, 30]], 14);
    };
  },

  /** Side tracking shot: pedalling, the pouch swinging, one jolt over a stone. */
  side(kit, scene) {
    const SPAN = 5600;
    const far = kit.layer(SPAN, 760);
    const sun = [2600, 420];
    paintSky(kit, far.g, SPAN, 470, sun, 21);
    paintClouds(kit, far.g, [[300, 200, 760, 220], [1150, 130, 560, 160], [1950, 250, 640, 190], [2750, 170, 780, 240], [3550, 230, 600, 170], [4350, 160, 700, 210], [5150, 220, 620, 180]], sun);
    paintFarBank(kit, far.g, SPAN, 470, 25);
    paintBridge(kit, far.g, 3000, 3700, 458, 40);
    paintRiver(kit, far.g, SPAN, 484, 760, sun[0], 26);
    const near = kit.layer(SPAN * 2, 360);
    const top = () => 40;
    paintSlope(kit, near.g, SPAN * 2, () => 0, 40, 27, { lit: 0.8 });
    paintRoad(kit, near.g, SPAN * 2, top, () => 120, 28);
    paintSlope(kit, near.g, SPAN * 2, () => 160, 200, 29, { lit: 0.4 });
    kit.tooth(far.g, SPAN, 760, 30, 0.05);
    const jolts = [scene.events.jolt];
    return (g, t, dur) => {
      const farX = 600 + t * 40;
      g.drawImage(far.canvas, -farX, 0);
      glitter(kit, g, t, sun[0] - farX, 500, 740, 160, 31, 0);
      // the near ground moves fast, on ones: the camera is tracking
      const nearX = 200 + t * 520;
      g.drawImage(near.canvas, -nearX, 720);
      const pose = ride(kit, t, { jolts });
      groundShadow(g, 780, 885, 1, 360);
      // the stone the front wheel hits
      const stoneX = 780 + 152 + (3.0 - t) * 520;
      if (stoneX > -40 && stoneX < 2000) {
        g.beginPath();
        g.ellipse(stoneX, 880, 11, 7, 0, 0, Math.PI * 2);
        g.fillStyle = '#8f7a86';
        g.fill();
        g.lineWidth = 2;
        g.strokeStyle = '#3b2a2e';
        g.stroke();
      }
      pelican(kit, g, 780, 884, 1, { ...pose, light: -0.35 });
      // the near verge, blurred by speed
      g.save();
      g.filter = 'blur(6px)';
      const r = kit.rng(32);
      for (let i = 0; i < 90; i++) {
        const x = ((r() * 6000 - t * 1100) % 2400 + 2400) % 2400 - 240;
        const hgt = 60 + r() * 140;
        kit.ink(g, [[x, 1100, 9], [x + 10, 1100 - hgt * 0.6, 6], [x + 24 + r() * 20, 1100 - hgt, 2]], kit.css(kit.mix('#6f6a3c', '#a2914e', r())));
      }
      g.restore();
    };
  },

  /** Toward the sunset: the bell, the egrets lifting from the reeds, the rider getting small. */
  sunset(kit, scene) {
    const plate = kit.layer(1920, 1080);
    const sun = [1210, 545];
    paintSky(kit, plate.g, 1920, 610, sun, 41);
    paintClouds(kit, plate.g, [[320, 220, 760, 240], [960, 130, 520, 150], [1620, 250, 640, 200], [1280, 420, 420, 90]], sun);
    paintFarBank(kit, plate.g, 1920, 600, 45);
    paintRiver(kit, plate.g, 1920, 612, 1080, sun[0], 46);
    const g = plate.g;
    // land on the near side: the embankment and the fields below it, a wedge from the left edge to the sun
    const crest = (u) => [lerp(-60, 1150, u), lerp(1180, 640, u)];
    g.beginPath();
    g.moveTo(-10, 612);
    g.lineTo(1140, 612);
    g.lineTo(1160, 642);
    g.lineTo(1150, 1090);
    g.lineTo(-10, 1090);
    g.closePath();
    const land = g.createLinearGradient(0, 1080, 900, 620);
    land.addColorStop(0, '#6e6170');
    land.addColorStop(0.5, '#a08a68');
    land.addColorStop(1, '#d9b47a');
    g.fillStyle = land;
    g.fill();
    // the far side of the embankment drops to the water, catching the low sun
    g.beginPath();
    g.moveTo(1160, 642);
    g.lineTo(1150, 1090);
    g.lineTo(1330, 1090);
    g.lineTo(1172, 640);
    g.closePath();
    g.fillStyle = kit.css('#d9b27a');
    g.fill();
    {
      const tr = kit.rng(54);
      for (let x = -20; x < 1130; x += 14 + tr() * 22) {
        const hgt = 10 + tr() * 26 * (x < 700 ? 1 : 0.5);
        const w = 14 + tr() * 22;
        g.beginPath();
        g.ellipse(x, 616 - hgt * 0.5, w * 0.5, hgt * 0.55, 0, 0, Math.PI * 2);
        g.fillStyle = kit.css(kit.jit('#7a6f92', tr, 10));
        g.fill();
      }
      g.fillStyle = kit.css('#857a8e');
      g.fillRect(0, 612, 1140, 8);
    }
    kit.mottle(g, 0, 620, 1150, 470, (x, y) => kit.mix(kit.mix('#b8996a', '#7a6a72', kit.clamp((y - 640) / 440)), '#d0a86a', kit.clamp(x / 1400) * 0.4), { n: 500, size: 90, alpha: 0.14, r: kit.rng(52), angle: -0.4 });
    // road on the crest
    g.beginPath();
    g.moveTo(600, 1090);
    g.lineTo(1150, 642);
    g.lineTo(1166, 642);
    g.lineTo(900, 1090);
    g.closePath();
    const rd = g.createLinearGradient(0, 1080, 1150, 640);
    rd.addColorStop(0, '#b89a86');
    rd.addColorStop(1, '#ffe2b0');
    g.fillStyle = rd;
    g.fill();
    const r = kit.rng(47);
    for (let i = 0; i < 1800; i++) {
      const u = r();
      const y = 1080 - u * 440;
      const xl = 600 + u * 550;
      const xr = 900 + u * 266;
      const x = xl + r() * (xr - xl);
      g.fillStyle = kit.css(kit.jit(r() < 0.5 ? '#e3c9a1' : '#9e8478', r, 18), 0.6);
      g.fillRect(x, y, (1 - u) * 4 + 1, (1 - u) * 2 + 0.6);
    }
    // grass on the near slope, lit along the crest
    {
      const gr = kit.rng(53);
      const roadLeft = (y) => 600 + ((1090 - y) / 448) * 550;
      const roadRight = (y) => 900 + ((1090 - y) / 448) * 266;
      const landRight = (y) => 1160 - ((y - 642) / 448) * 10;
      for (let i = 0; i < 900; i++) {
        const y = 650 + gr() * 440;
        const x = gr() * landRight(y);
        if (x > roadLeft(y) - 6 && x < roadRight(y) + 6) continue;
        const u = (y - 640) / 440;
        kit.grass(g, [x, x + 1], y, { n: 1, len: 8 + 26 * u, colors: ['#9a8c5a', '#7d765a', '#b8a06a', '#8a7a86'], lean: 0.2, r: gr, width: 1 + u * 1.4 });
      }
    }
    kit.tooth(g, 1920, 1080, 48, 0.05);
    const roadAt = (u) => [lerp(750, 1158, u), lerp(1080, 642, u)];
    const birds = Array.from({ length: 8 }, (_, i) => {
      const br = kit.rng(60 + i);
      // the first egret goes on the event itself, the rest follow within a third of a second
      return { x: 1420 + i * 58 + br() * 30, y: 800 + (i % 3) * 26 + br() * 20, vx: 90 + br() * 90, vy: -(120 + br() * 80), delay: i === 0 ? 0 : 0.05 + br() * 0.3, ph: br(), s: 0.65 + br() * 0.35 };
    });
    return (g2, t, dur) => {
      g2.drawImage(plate.canvas, 0, 0);
      glitter(kit, g2, t, sun[0] + 40, 626, 1060, 160, 49, 0, (x) => Infinity, (x, y) => x > 1172 + ((y - 640) / 450) * 160);
      // reeds on the river side, where the egrets hide
      reeds(kit, g2, t, [[1430, 1900, 880, 70, 170, 70]], 50, { backlit: true });
      // the rider moves up the road toward the sun, getting smaller
      const u = 0.12 + (t / dur) * 0.34;
      const [x, y] = roadAt(u);
      const s = lerp(0.6, 0.3, (u - 0.12) / 0.34);
      groundShadow(g2, x - 10 * s, y + 2, s);
      pelican(kit, g2, x, y, s, { ...ride(kit, t, { bellAt: scene.events.bell }), light: -0.2 });
      // the egrets lift at 1.8 s into the shot
      const d = kit.twos(t);
      for (const [i, b] of birds.entries()) {
        const k = d - scene.events.birds - b.delay;
        if (k < 0) continue;
        const bx = b.x + b.vx * k + 40 * k * k;
        const by = b.y + b.vy * k + 30 * k * k * -0.5;
        // a wingbeat about three times a second, drawn on twos
        const phase = 0.5 + 0.5 * Math.sin((k * 3.2 + b.ph) * Math.PI * 2);
        egret(kit, g2, bx, by, b.s * 1.15 * (1 - k * 0.07), phase, 70 + i);
      }
      // foreground reeds, backlit, on the left
      reeds(kit, g2, t, [[-30, 380, 1110, 160, 420, 60]], 51, { backlit: true });
    };
  },
};

function lerp(a, b, t) {
  return a + (b - a) * t;
}
