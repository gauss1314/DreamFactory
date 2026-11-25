import { cel, glitter, groundShadow, lerpPt, line, paintBridge, paintClouds, paintFarBank, paintRiver, paintRoad, paintSky, paintSlope, path, reeds } from '/runtime/painters.js';

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
      kit.actor('鹈鹕', { x: px + pan, y, s, facing: 'right' });
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
      // tracking shot: the camera follows, so on the ground the rider moves right as fast as the road scrolls
      kit.actor('鹈鹕', { x: 780 + nearX, y: 884, s: 1, facing: 'right' });
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

  /**
   * Toward the sunset, seen from the side: the embankment runs across the frame and up toward the sun
   * on the right; the rider goes the way it faces, rings the bell, and the egrets lift from the reeds.
   */
  sunset(kit, scene) {
    const plate = kit.layer(1920, 1080);
    const sun = [1500, 560];
    paintSky(kit, plate.g, 1920, 620, sun, 41);
    paintClouds(kit, plate.g, [[320, 210, 760, 240], [960, 130, 520, 150], [1640, 260, 640, 190], [1260, 430, 420, 90]], sun);
    paintFarBank(kit, plate.g, 1920, 610, 45);
    paintRiver(kit, plate.g, 1920, 622, 860, sun[0], 46);
    const g = plate.g;
    // the road climbs gently toward the sun, like the first shot, so the rider rides the way it faces
    const roadTop = (x) => 842 - x * 0.05;
    // the river side of the embankment, catching the low sun
    paintSlope(kit, g, 1920, (x) => roadTop(x) - 60, 60, 47, { lit: 0.9 });
    paintRoad(kit, g, 1920, roadTop, () => 30, 48);
    // the near slope, backlit: warm at the crest, violet below
    for (let x = 0; x < 1920; x += 3) {
      const y0 = roadTop(x) + 30;
      const grd = g.createLinearGradient(0, y0, 0, 1080);
      grd.addColorStop(0, kit.css('#c9a46a'));
      grd.addColorStop(0.35, kit.css('#8c7a6a'));
      grd.addColorStop(1, kit.css('#5e5468'));
      g.fillStyle = grd;
      g.fillRect(x, y0, 3, 1080 - y0);
    }
    kit.mottle(g, 0, 780, 1920, 300, (x, y) => kit.mix('#a08a68', '#6a5f70', kit.clamp((y - roadTop(x)) / 260)), { n: 380, size: 110, alpha: 0.13, r: kit.rng(52), angle: -0.1 });
    kit.grass(g, [0, 1920], (x) => roadTop(x) + 34, { n: 900, len: 18, colors: ['#e0b878', '#b89a6a', '#9a8a7a'], lean: 0.2, r: kit.rng(53), width: 1.6 });
    kit.tooth(g, 1920, 1080, 49, 0.05);
    const birds = Array.from({ length: 8 }, (_, i) => {
      const br = kit.rng(60 + i);
      // the first egret goes on the event itself, the rest follow within a third of a second
      return { x: 1240 + i * 62 + br() * 30, y: 690 + (i % 3) * 20 + br() * 16, vx: 70 + br() * 90, vy: -(130 + br() * 80), delay: i === 0 ? 0 : 0.05 + br() * 0.3, ph: br(), s: 0.65 + br() * 0.35 };
    });
    return (g2, t, dur) => {
      g2.drawImage(plate.canvas, 0, 0);
      glitter(kit, g2, t, sun[0], 640, 840, 170, 50, 0, (x) => roadTop(x) - 66);
      // reeds on the river side of the embankment, where the egrets hide
      reeds(kit, g2, t, [[1180, 1760, 790, 60, 150, 70]], 51, { backlit: true });
      // the rider follows the road to the right, toward the sun
      const x = 240 + t * 150;
      const y = roadTop(x) + 16;
      const s = 0.5;
      // backlit: the shadow falls toward us and behind
      groundShadow(g2, x - 30 * s, y + 4, s);
      pelican(kit, g2, x, y, s, { ...ride(kit, t, { bellAt: scene.events.bell }), light: -0.1 });
      kit.actor('鹈鹕', { x, y, s, facing: 'right' });
      // the egrets lift at the event, toward the sun
      const d = kit.twos(t);
      for (const [i, b] of birds.entries()) {
        const k = d - scene.events.birds - b.delay;
        if (k < 0) continue;
        const bx = b.x + b.vx * k + 40 * k * k;
        const by = b.y + b.vy * k - 15 * k * k;
        // a wingbeat about three times a second, drawn on twos
        const phase = 0.5 + 0.5 * Math.sin((k * 3.2 + b.ph) * Math.PI * 2);
        egret(kit, g2, bx, by, b.s * 1.1 * (1 - k * 0.07), phase, 70 + i);
      }
      // foreground reeds, backlit, at both corners
      reeds(kit, g2, t, [[-30, 300, 1110, 160, 400, 50], [1720, 1960, 1110, 120, 300, 30]], 54, { backlit: true });
    };
  },
};
