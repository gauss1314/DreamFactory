import {
  paintSky, paintClouds, paintFarBank, paintBridge, paintRiver, glitter, paintSlope, paintRoad, reeds,
  path, cel, line, groundShadow,
} from '/runtime/painters.js';

const INK = '#3b2a2e';
const TAU = Math.PI * 2;
const LIGHT = [1, -0.45]; // the sun is ahead of the rider, low on the right
const C = {
  feather: '#fbf4e6', featherShade: '#c9b9c9', featherRim: '#fff1c9',
  bill: '#f2a33a', billShade: '#c8703e', pouch: '#f6c36b', pouchShade: '#d58f5c',
  tip: '#4a4a62', tipShade: '#34344c', foot: '#f08a3c', footShade: '#c0603a',
  frame: '#2f7f8a', frameDark: '#1f5763', frameLit: '#6cb8b0', basket: '#b07d4a', basketDark: '#7d5236',
};
const WHEEL_R = 70;
const GEAR = 2.2; // the wheel turns 2.2 times for each turn of the cranks

// ---------------------------------------------------------------- the bicycle and its rider

function tube(kit, g, a, b, w, col) {
  const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  kit.ink(g, [[a[0], a[1], w + 5], [m[0], m[1], w + 5], [b[0], b[1], w + 5]], INK, { taper: false });
  kit.ink(g, [[a[0], a[1], w], [m[0], m[1], w], [b[0], b[1], w]], col, { taper: false });
}

function wheel(kit, g, cx, cy, ang) {
  const R = WHEEL_R;
  // spokes spin too fast to read: a faint disc of them, drawn still
  g.beginPath();
  g.arc(cx, cy, R - 6, 0, TAU);
  g.fillStyle = 'rgba(240,222,214,0.10)';
  g.fill();
  g.lineWidth = 1;
  g.strokeStyle = 'rgba(232,214,214,0.32)';
  for (let i = 0; i < 18; i++) {
    const a = (i / 18) * TAU;
    g.beginPath();
    g.moveTo(cx + Math.cos(a) * 6, cy + Math.sin(a) * 6);
    g.lineTo(cx + Math.cos(a + 0.5) * (R - 7), cy + Math.sin(a + 0.5) * (R - 7));
    g.stroke();
  }
  // the reflector and the valve turn with the wheel, so the eye reads the spin
  const ra = ang;
  g.save();
  g.translate(cx + Math.cos(ra) * R * 0.55, cy + Math.sin(ra) * R * 0.55);
  g.rotate(ra);
  g.fillStyle = '#f08a3c';
  g.fillRect(-8, -3, 16, 6);
  g.restore();
  // tyre and rim
  g.beginPath();
  g.arc(cx, cy, R - 4, 0, TAU);
  g.lineWidth = 11;
  g.strokeStyle = '#3a2c36';
  g.stroke();
  g.beginPath();
  g.arc(cx, cy, R - 10, 0, TAU);
  g.lineWidth = 3;
  g.strokeStyle = '#b3aabd';
  g.stroke();
  // the sun catches the tyre's leading top edge (fixed: light does not turn with the wheel)
  g.beginPath();
  g.arc(cx, cy, R - 2, -1.25, -0.15);
  g.lineWidth = 2.5;
  g.strokeStyle = 'rgba(255,214,160,0.75)';
  g.stroke();
  const va = ang + Math.PI * 0.7;
  g.fillStyle = '#d9cfd6';
  g.fillRect(cx + Math.cos(va) * (R - 13) - 2, cy + Math.sin(va) * (R - 13) - 2, 4, 4);
  // hub
  g.beginPath();
  g.arc(cx, cy, 7, 0, TAU);
  g.fillStyle = '#9a93ac';
  g.fill();
  g.lineWidth = 2;
  g.strokeStyle = INK;
  g.stroke();
}

/** Two-bone leg: hip to pedal, the knee bends forward. */
function leg(kit, g, hip, foot, col, shade) {
  const L1 = 100;
  const L2 = 100;
  const dx = foot[0] - hip[0];
  const dy = foot[1] - hip[1];
  const d = Math.min(Math.hypot(dx, dy), L1 + L2 - 2);
  const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
  const ux = dx / d;
  const uy = dy / d;
  // knee forward: the perpendicular that points toward +x
  let px = -uy;
  let py = ux;
  if (px < 0) { px = -px; py = -py; }
  const knee = [hip[0] + ux * a + px * h, hip[1] + uy * a + py * h];
  kit.ink(g, [[hip[0], hip[1], 22], [knee[0], knee[1], 18], [foot[0], foot[1], 15]], INK, { taper: false });
  kit.ink(g, [[hip[0], hip[1], 16], [knee[0], knee[1], 12.5], [foot[0], foot[1], 10]], col, { taper: false });
  kit.ink(g, [[knee[0] - 2, knee[1] + 2, 3], [(knee[0] + foot[0]) / 2 - 3, (knee[1] + foot[1]) / 2, 3], [foot[0] - 3, foot[1] - 2, 1]], shade);
  // webbed foot flat on the pedal
  const F = path(kit, [[foot[0] - 8, foot[1] - 6], [foot[0] + 26, foot[1] - 2], [foot[0] + 30, foot[1] + 5], [foot[0] - 6, foot[1] + 6]]);
  cel(g, F.P, { base: col, shade, light: LIGHT, sd: 4 });
  line(kit, g, F.q, 2.6, 41);
}

/**
 * A pelican on a bicycle, side view, facing right. (X, Y) is the ground under the middle of the bike.
 * o.wheel: wheel turn (rad); o.crank: crank angle; o.frontLift/o.rearLift: a wheel riding over a stone;
 * o.bob: rider up/down; o.pouch, o.crest, o.tip: follow-through; o.flick: wing on the bell; o.look: head lift.
 */
function pelican(kit, g, X, Y, s, o = {}) {
  const { wheel: wa = 0, crank = 0, frontLift = 0, rearLift = 0, bob = 0, pouch = 0, crest = 0, tip = 0, flick = 0, look = 0 } = o;
  // the sun is low and ahead: the shadow stretches out behind the bike
  groundShadow(g, X - 90 * s, Y + 3 * s, s, 560, 'rgba(80,52,100,0.45)');
  g.save();
  g.translate(X, Y);
  g.scale(s, s);
  const ang = Math.atan2(frontLift - rearLift, 220);
  g.translate(0, -(frontLift + rearLift) / 2);
  g.translate(0, -70);
  g.rotate(-ang);
  g.translate(0, 70);

  const RA = [-110, -70];
  const FA = [110, -70];
  const BB = [-15, -62];
  const ST = [-55, -192];
  const HT = [80, -196];
  const HB = [88, -162];
  const pedal = (k) => [BB[0] + Math.cos(crank + k * Math.PI) * 32, BB[1] + Math.sin(crank + k * Math.PI) * 32];
  const P1 = pedal(0);
  const P2 = pedal(1);
  const hip = [-48, -224 - bob];

  // far side: leg and crank, darker in the shade of the body
  leg(kit, g, [hip[0] + 6, hip[1] - 2], [P2[0] + 4, P2[1] - 3], '#c7683a', '#9a4a34');
  kit.ink(g, [[BB[0], BB[1], 7], [(BB[0] + P2[0]) / 2, (BB[1] + P2[1]) / 2, 7], [P2[0], P2[1], 6]], '#3a3044', { taper: false });

  wheel(kit, g, RA[0], RA[1], wa);
  wheel(kit, g, FA[0], FA[1], wa);

  // chain and chainring
  g.strokeStyle = '#4a4052';
  g.lineWidth = 2.5;
  g.beginPath();
  g.moveTo(BB[0], BB[1] - 22);
  g.lineTo(RA[0], RA[1] - 10);
  g.moveTo(BB[0], BB[1] + 22);
  g.lineTo(RA[0], RA[1] + 10);
  g.stroke();
  g.beginPath();
  g.arc(BB[0], BB[1], 22, 0, TAU);
  g.fillStyle = '#8e8aa2';
  g.fill();
  g.lineWidth = 3;
  g.strokeStyle = INK;
  g.stroke();

  // frame
  tube(kit, g, BB, RA, 7, C.frame);
  tube(kit, g, ST, RA, 6, C.frame);
  tube(kit, g, BB, [ST[0] - 4, ST[1] - 6], 10, C.frame);
  tube(kit, g, BB, HB, 11, C.frame);
  tube(kit, g, [ST[0] + 4, ST[1] + 6], [HT[0] - 2, HT[1] + 10], 9, C.frame);
  tube(kit, g, HT, HB, 13, C.frameDark);
  tube(kit, g, HB, FA, 7, C.frame);
  // light along the top of the tubes facing the sun
  kit.ink(g, [[ST[0] + 8, ST[1] + 3, 2.5], [10, -190, 2.5], [HT[0] - 8, HT[1] + 6, 1.5]], C.frameLit);
  kit.ink(g, [[BB[0] + 6, BB[1] - 6, 2.5], [40, -112, 2.5], [HB[0] - 4, HB[1] + 2, 1.5]], C.frameLit);
  // mudguard over the front wheel
  kit.ink(g, [[FA[0] - 62, FA[1] - 40, 5], [FA[0], FA[1] - 78, 6], [FA[0] + 66, FA[1] - 30, 4]], C.frameDark);
  // saddle
  const SD = path(kit, [[-92, -206], [-58, -212], [-22, -206], [-30, -197], [-80, -196]]);
  cel(g, SD.P, { base: '#6a3a3a', shade: '#4a2a34', light: LIGHT, sd: 4 });
  line(kit, g, SD.q, 2.6, 12);

  // basket on the front
  const BK = path(kit, [[100, -252], [172, -256], [166, -192], [106, -190]]);
  cel(g, BK.P, { base: C.basket, shade: C.basketDark, rim: '#e0ab70', light: LIGHT, sd: 9, rw: 3 });
  g.save();
  g.clip(BK.P);
  g.strokeStyle = 'rgba(80,46,30,0.55)';
  g.lineWidth = 2;
  for (let y = -246; y < -190; y += 11) {
    g.beginPath();
    g.moveTo(98, y);
    g.lineTo(175, y - 2);
    g.stroke();
  }
  for (let x = 108; x < 172; x += 13) {
    g.beginPath();
    g.moveTo(x, -258);
    g.lineTo(x - 2, -188);
    g.stroke();
  }
  g.restore();
  line(kit, g, BK.q, 3, 13);
  kit.ink(g, [[HT[0], HT[1] + 8, 4], [100, -220, 4]], INK);

  // ---- the rider, who rides on the springs of its own weight
  g.save();
  g.translate(0, -bob);
  // folded tertials and tail, dark tips trailing
  const TL = path(kit, [[-100, -300], [-150, -282], [-178 - tip * 0.6, -266 + tip], [-150, -256], [-110, -262]]);
  cel(g, TL.P, { base: C.tip, shade: C.tipShade, rim: '#7a6c8a', light: LIGHT, sd: 6, rw: 3 });
  line(kit, g, TL.q, 3, 21);
  // body
  const BD = path(kit, [[-165, -264], [-130, -302], [-75, -340], [-5, -347], [45, -324], [64, -284], [42, -238], [-20, -218], [-95, -224], [-140, -244]]);
  cel(g, BD.P, { base: C.feather, shade: C.featherShade, rim: C.featherRim, light: LIGHT, sd: 22, rw: 5 });
  line(kit, g, BD.q, 4, 22);

  // neck, head, bill and pouch turn together about the base of the neck
  g.save();
  g.translate(25, -330);
  g.rotate(-look);
  g.translate(-25, 330);
  const NK = path(kit, [[-4, -328], [8, -372], [-3, -412], [10, -452], [58, -458], [52, -420], [44, -388], [60, -350], [52, -318]]);
  cel(g, NK.P, { base: C.feather, shade: C.featherShade, rim: C.featherRim, light: LIGHT, sd: 12, rw: 4 });
  line(kit, g, NK.q, 3.6, 23);
  const HD = path(kit, [[4, -468], [20, -492], [50, -494], [68, -476], [64, -452], [36, -442], [10, -448]]);
  cel(g, HD.P, { base: C.feather, shade: C.featherShade, rim: C.featherRim, light: LIGHT, sd: 9, rw: 4 });
  line(kit, g, HD.q, 3.4, 24);
  // crest: a few feathers at the back of the head, a beat behind
  for (let k = 0; k < 3; k++) {
    const c = crest * (1 + k * 0.4);
    kit.ink(g, [[14, -486 + k * 5, 5], [-6 - k * 4, -494 + k * 7 + c * 0.5, 3.5], [-24 - k * 5, -490 + k * 9 + c, 1]], k === 1 ? '#f1e2d2' : '#e8d6cc');
  }
  // the pouch hangs under the bill and swings after the body
  const sw = pouch;
  const PC = path(kit, [[70, -452], [140, -452], [214, -446], [198, -430], [150 - sw * 0.6, -404 + Math.abs(sw) * 0.2], [104 - sw * 0.3, -410], [68, -432]]);
  cel(g, PC.P, { base: C.pouch, shade: C.pouchShade, rim: '#ffe0a0', light: LIGHT, sd: 9, rw: 3 });
  line(kit, g, PC.q, 3, 25);
  const BL = path(kit, [[58, -482], [150, -474], [226, -462], [238, -452], [226, -446], [150, -452], [64, -452]]);
  cel(g, BL.P, { base: C.bill, shade: C.billShade, rim: '#ffd08a', light: LIGHT, sd: 5, rw: 2 });
  line(kit, g, BL.q, 3, 26);
  kit.ink(g, [[72, -463, 2], [150, -461, 2], [222, -454, 1]], '#b8622f');
  // eye
  g.beginPath();
  g.ellipse(46, -474, 6, 7, 0, 0, TAU);
  g.fillStyle = INK;
  g.fill();
  g.beginPath();
  g.arc(48, -476, 2, 0, TAU);
  g.fillStyle = '#fff6dc';
  g.fill();
  kit.ink(g, [[36, -483, 1], [46, -487, 2.4], [56, -483, 1]], INK);
  g.restore();

  // near wing reaching forward to the grip
  const WG = path(kit, [[-30, -326], [22, -318], [52, -284], [52, -250], [40, -238], [10, -262], [-50, -270], [-115, -268], [-148, -262], [-120, -292], [-70, -312]]);
  cel(g, WG.P, { base: '#f4ecdf', shade: C.featherShade, rim: C.featherRim, light: LIGHT, sd: 12, rw: 4 });
  line(kit, g, WG.q, 3.4, 27);
  // feather rows on the wing
  kit.ink(g, [[-120, -278, 1], [-70, -282, 2.4], [-20, -280, 2.4], [20, -282, 1]], '#c9b9c9');
  kit.ink(g, [[-105, -292, 1], [-60, -298, 2], [-20, -300, 1]], '#d8c8d2');
  // dark primaries wrapped round the grip; one flicks to the bell
  const HP = path(kit, [[32, -254], [58, -252], [62, -234], [44, -224], [28, -234]]);
  cel(g, HP.P, { base: C.tip, shade: C.tipShade, rim: '#7a6c8a', light: LIGHT, sd: 5, rw: 2 });
  line(kit, g, HP.q, 2.6, 28);
  kit.ink(g, [[50, -248, 6], [60 + flick * 4, -254 - flick * 8, 4.5], [66 + flick * 6, -260 - flick * 12, 1.5]], C.tip);
  g.restore();

  // handlebar and the bell (in front of the wing hand)
  kit.ink(g, [[HT[0], HT[1], 7], [76, -224, 7], [56, -230, 6], [34, -230, 6]], '#3a3044', { taper: false });
  g.beginPath();
  g.arc(64, -242, 7, Math.PI, 0);
  g.lineTo(71, -237);
  g.lineTo(57, -237);
  g.closePath();
  g.fillStyle = '#d9d2c4';
  g.fill();
  g.lineWidth = 2;
  g.strokeStyle = INK;
  g.stroke();

  // near crank and leg, in front of everything
  kit.ink(g, [[BB[0], BB[1], 8], [(BB[0] + P1[0]) / 2, (BB[1] + P1[1]) / 2, 8], [P1[0], P1[1], 7]], '#4a4052', { taper: false });
  g.beginPath();
  g.arc(BB[0], BB[1], 5, 0, TAU);
  g.fillStyle = '#b5aec2';
  g.fill();
  leg(kit, g, [hip[0], hip[1]], P1, C.foot, C.footShade);
  g.restore();
}

// ---------------------------------------------------------------- egrets

function egret(kit, g, x, y, e, dir, o) {
  g.save();
  g.translate(x, y);
  g.scale(e * dir, e);
  const W = '#fbfaf2';
  const SH = '#c6bdd8';
  if (o.standing) {
    const lean = o.lean || 0;
    kit.ink(g, [[-4, 4, 3], [-6, 24, 2.5], [-6, 44, 2]], '#2e2a36');
    kit.ink(g, [[6, 4, 3], [8, 24, 2.5], [9, 44, 2]], '#2e2a36');
    const B = path(kit, [[-24, -2], [-4, -14], [20, -16], [28, -8], [12, 6], [-14, 6]]);
    cel(g, B.P, { base: W, shade: SH, light: LIGHT, sd: 5 });
    line(kit, g, B.q, 2, o.seed);
    kit.ink(g, [[22, -12, 7], [32 + lean, -34, 6], [24 + lean, -50, 6], [32 + lean, -66, 7]], INK, { taper: false });
    kit.ink(g, [[22, -12, 5], [32 + lean, -34, 4], [24 + lean, -50, 4], [32 + lean, -66, 5]], W, { taper: false });
    kit.ink(g, [[34 + lean, -68, 3.5], [48 + lean, -66, 2.5], [60 + lean, -64, 1]], '#e8b340');
    g.restore();
    return;
  }
  const w = o.wing; // +1 wings up, -1 wings down
  const wingPts = (k) => [[-12, -4], [18, -6], [4 - 8 * k, -6 - 52 * w * k], [-26 - 8 * k, -8 - 60 * w * k]];
  // far wing, in shadow
  const FW = path(kit, wingPts(0.85).map(([a, b]) => [a + 4, b - 2]));
  cel(g, FW.P, { base: '#ddd6e4', shade: '#aea5c4', light: LIGHT, sd: 4 });
  line(kit, g, FW.q, 1.8, o.seed + 1);
  kit.ink(g, [[-22, 2, 2.4], [-48, 6, 2], [-66, 8, 1]], '#2e2a36');
  const B = path(kit, [[-34, 0], [-10, -10], [24, -9], [34, -3], [20, 6], [-16, 7]]);
  cel(g, B.P, { base: W, shade: SH, rim: '#fff1c9', light: LIGHT, sd: 5, rw: 2 });
  line(kit, g, B.q, 2, o.seed + 2);
  // neck folded back in flight, the bill forward
  kit.ink(g, [[26, -6, 7], [36, -16, 6], [30, -22, 6], [40, -26, 7]], INK, { taper: false });
  kit.ink(g, [[26, -6, 5], [36, -16, 4], [30, -22, 4], [40, -26, 5]], W, { taper: false });
  kit.ink(g, [[42, -27, 3.5], [56, -26, 2.5], [68, -24, 1]], '#e8b340');
  const NW = path(kit, wingPts(1));
  cel(g, NW.P, { base: W, shade: SH, rim: '#fff1c9', light: LIGHT, sd: 5, rw: 2 });
  line(kit, g, NW.q, 2, o.seed + 3);
  g.restore();
}

// ---------------------------------------------------------------- shared background bits

/** The near face of the embankment turns away from the low sun: cool it toward violet, deeper at the foot. */
function shadeFace(g, w, y0, y1) {
  const grd = g.createLinearGradient(0, y0, 0, y1);
  grd.addColorStop(0, 'rgba(110,84,140,0.06)');
  grd.addColorStop(0.5, 'rgba(100,76,136,0.26)');
  grd.addColorStop(1, 'rgba(84,62,120,0.42)');
  g.fillStyle = grd;
  g.fillRect(0, y0, w, y1 - y0);
}

function crestGrass(kit, g, x0, x1, baseY, seed, n, len) {
  kit.grass(g, [x0, x1], baseY, { n, len, colors: ['#d8c878', '#c9b45e', '#a69a58', '#8f8c4d'], lean: 0.25, r: kit.rng(seed), width: 2 });
}

// ---------------------------------------------------------------- shots
export default {
  // 1. Wide: the golden embankment and the river; the pelican small on the crest, riding toward the sun.
  wide(kit) {
    const sun = [1480, 450];
    const horizon = 560;
    const roadY = 782;
    const plate = kit.layer(1920, 1080);
    const p = plate.g;
    paintSky(kit, p, 1920, horizon, sun, 3);
    paintClouds(kit, p, [[300, 170, 520, 120], [820, 260, 360, 80], [1180, 120, 440, 110], [1750, 300, 300, 60], [560, 400, 240, 46]], sun);
    paintFarBank(kit, p, 1920, horizon, 5);
    paintBridge(kit, p, 140, 640, horizon - 6, 34);
    paintRiver(kit, p, 1920, horizon + 12, 742, sun[0], 6);
    // the far face of the embankment, down to the water
    paintSlope(kit, p, 1920, (x) => 738 + 3 * Math.sin(x / 300), roadY - 738, 7, { lit: 0.85 });
    paintRoad(kit, p, 1920, (x) => roadY - 8, () => 22, 8);
    // the near face, falling away into violet shadow
    paintSlope(kit, p, 1920, () => roadY + 14, 1080 - roadY - 14, 9, { lit: 0.55 });
    shadeFace(p, 1920, roadY + 20, 1080);
    crestGrass(kit, p, 0, 1920, roadY + 14, 10, 900, 16);
    kit.tooth(p, 1920, 1080, 11, 0.05);
    const x0 = 360;
    const v = 92;
    const s = 0.2;
    return (g, t, dur) => {
      const tt = kit.twos(t);
      const z = 1 + 0.03 * kit.smooth(t / dur);
      g.save();
      g.translate(700, 760);
      g.scale(z, z);
      g.translate(-700, -760);
      g.drawImage(plate.canvas, 0, 0);
      glitter(kit, g, t, sun[0], horizon + 14, 735, 220, 12);
      reeds(kit, g, t, [[880, 1320, 744, 30, 70, 40], [1500, 1700, 742, 26, 60, 22], [40, 380, 744, 24, 56, 26]], 13, { backlit: true });
      const x = x0 + v * tt;
      const dist = v * tt / s;
      const crank = dist / WHEEL_R / GEAR;
      pelican(kit, g, x, roadY, s, { wheel: dist / WHEEL_R, crank, bob: 3 * Math.sin(2 * crank), pouch: 4 * Math.sin(2 * crank - 0.8) });
      kit.actor('鹈鹕', { x, y: roadY, s, facing: 'right' });
      // near grass, stirring in the evening wind
      kit.grass(g, [0, 1920], 1066, { n: 260, len: 46, colors: ['#8f8c4d', '#7a7448', '#6d6c5a', '#9a8a6a'], lean: 0.2, r: kit.rng(14), sway: 0.12 * Math.sin(tt * 1.7), width: 3 });
      g.restore();
    };
  },

  // 2. Side tracking shot: pedalling, the pouch swinging; the front wheel rides over a stone.
  side(kit, scene) {
    const [tb1, tb2] = scene.events.bump;
    const v = 220 / (tb2 - tb1); // the rear wheel meets the stone one wheelbase after the front
    const SX = 820;
    const GY = 902;
    const s = 1;
    const sun = [1640, 430];
    const horizon = 600;
    const span = v * 5.2;
    const sky = kit.layer(1920, 760);
    paintSky(kit, sky.g, 1920, horizon, sun, 21);
    const clouds = kit.layer(2100, 600);
    paintClouds(kit, clouds.g, [[260, 150, 560, 130], [900, 260, 380, 80], [1400, 120, 500, 120], [1950, 330, 320, 64]], [sun[0] + 60, sun[1]]);
    const far = kit.layer(2400, 840);
    paintFarBank(kit, far.g, 2400, horizon, 22);
    paintRiver(kit, far.g, 2400, horizon + 12, 840, sun[0], 23);
    const bankW = Math.ceil(1920 + span * 0.55 + 200);
    const bank = kit.layer(bankW, 1080);
    paintSlope(kit, bank.g, bankW, (x) => 790 + 6 * Math.sin(x / 210), 70, 24, { lit: 0.8 });
    const roadW = Math.ceil(1920 + span + 300);
    const road = kit.layer(roadW, 1080);
    const R = road.g;
    paintRoad(kit, R, roadW, () => 848, () => 110, 25);
    // a few rounder stones lie loose on the gravel
    const rr = kit.rng(26);
    for (let i = 0; i < roadW / 60; i++) {
      const x = rr() * roadW;
      const y = 870 + rr() * 80;
      const w = 4 + rr() * 9;
      R.fillStyle = kit.css(kit.jit('#9e8478', rr, 20));
      R.beginPath();
      R.ellipse(x, y, w, w * 0.55, 0, 0, TAU);
      R.fill();
      R.fillStyle = 'rgba(255,226,180,0.5)';
      R.beginPath();
      R.ellipse(x + w * 0.25, y - w * 0.2, w * 0.4, w * 0.2, 0, 0, TAU);
      R.fill();
    }
    paintSlope(kit, R, roadW, () => 958, 122, 27, { lit: 0.5 });
    shadeFace(R, roadW, 962, 1080);
    crestGrass(kit, R, 0, roadW, 960, 28, Math.round(roadW / 3), 18);
    kit.tooth(R, roadW, 1080, 29, 0.05);
    // the stone the front wheel will meet: where the front tyre stands at tb1, plus the reach to its face
    const stoneX = v * tb1 + SX + 110 + 42;
    const ST = path(kit, [[stoneX - 22, GY + 2], [stoneX - 14, GY - 14], [stoneX + 4, GY - 18], [stoneX + 20, GY - 8], [stoneX + 22, GY + 3]]);
    R.fillStyle = 'rgba(80,52,100,0.4)';
    R.beginPath();
    R.ellipse(stoneX - 14, GY + 4, 30, 6, 0, 0, TAU);
    R.fill();
    cel(R, ST.P, { base: '#a89088', shade: '#7a6476', rim: '#f2d2a8', light: LIGHT, sd: 8, rw: 3 });
    line(kit, R, ST.q, 2.4, 30);

    const H = 16; // stone height
    const lift = (tt, t0) => {
      const u = (tt - t0) / 0.2;
      return u > 0 && u < 1 ? H * Math.sin(Math.PI * u) : 0;
    };
    // the rider: a brief check as the wheel hits, then a bounce up, settling
    const jolt = (tt, t0, a) => {
      const k = tt - t0;
      if (k < 0) return 0;
      if (k < 0.08) return -5 * a * Math.sin((Math.PI * k) / 0.08);
      const q = k - 0.08;
      return a * 22 * Math.exp(-q * 5.5) * Math.sin(q * 13);
    };
    const lag = (tt, t0, a) => {
      const k = tt - t0 - 0.16;
      return k < 0 ? 0 : a * Math.exp(-k * 3.2) * Math.sin(k * 10);
    };
    return (g, t) => {
      const tt = kit.twos(t);
      const cam = v * t;
      g.drawImage(sky.canvas, 0, 0);
      g.drawImage(clouds.canvas, -cam * 0.02, 0);
      g.drawImage(far.canvas, -cam * 0.06, 0);
      glitter(kit, g, t, sun[0], horizon + 14, 800, 260, 31);
      g.drawImage(bank.canvas, -cam * 0.55, 0);
      g.save();
      g.translate(-cam * 0.55, 0);
      // one fixed bed of reeds along the bank, carried with it (never re-seeded as it scrolls)
      reeds(kit, g, t, [[0, bankW, 812, 50, 150, Math.round(bankW / 26)]], 32, { backlit: true });
      g.restore();
      g.drawImage(road.canvas, -cam, 0);
      const fl = lift(tt, tb1);
      const rl = lift(tt, tb2);
      const hitch = -6 * (Math.exp(-Math.max(0, tt - tb1) * 3) * (tt > tb1 ? 1 : 0) * Math.min(1, (tt - tb1) * 12));
      const dist = v * tt;
      const crank = dist / WHEEL_R / GEAR + 0.6;
      const pedalBob = 2.5 * Math.sin(2 * crank);
      const bob = pedalBob + jolt(tt, tb1, 1) + jolt(tt, tb2, 0.45) + (fl + rl) * 0.3;
      const sway = 5 * Math.sin(2 * crank - 0.9);
      const pouch = sway + lag(tt, tb1, 26) + lag(tt, tb2, 12);
      const crest = 3 * Math.sin(2 * crank - 1.2) + lag(tt, tb1 + 0.04, 12) + lag(tt, tb2 + 0.04, 6);
      const tip = 2 * Math.sin(2 * crank - 1) + lag(tt, tb1 + 0.08, 8);
      pelican(kit, g, SX + hitch, GY, s, { wheel: dist / WHEEL_R, crank, frontLift: fl, rearLift: rl, bob, pouch, crest, tip });
      kit.actor('鹈鹕', { x: cam + SX + hitch, y: GY, s, facing: 'right' });
      // grass at the lens, passing faster than the road
      g.save();
      g.globalAlpha = 0.85;
      g.filter = 'blur(3px)';
      const fx = (cam * 1.35) % 2400;
      kit.grass(g, [-fx, 2400 - fx], 1090, { n: 70, len: 120, colors: ['#5c6845', '#6a6458', '#4e5640'], lean: 0.35, r: kit.rng(33), width: 6 });
      kit.grass(g, [2400 - fx, 4800 - fx], 1090, { n: 70, len: 120, colors: ['#5c6845', '#6a6458', '#4e5640'], lean: 0.35, r: kit.rng(33), width: 6 });
      g.restore();
    };
  },

  // 3. The end: two rings of the bell, egrets burst from the reeds, and it rides on into the sun.
  end(kit, scene) {
    const [b1, b2] = scene.events.bell;
    const te = scene.events.egrets;
    const sun = [1520, 470];
    const horizon = 548;
    const roadY = 890;
    const s = 0.56;
    const plate = kit.layer(1920, 1080);
    const p = plate.g;
    paintSky(kit, p, 1920, horizon, sun, 41);
    paintClouds(kit, p, [[260, 140, 520, 120], [760, 250, 330, 72], [1150, 150, 420, 100], [1800, 260, 340, 70], [420, 380, 220, 40]], sun);
    paintFarBank(kit, p, 1920, horizon, 42);
    paintRiver(kit, p, 1920, horizon + 12, 832, sun[0], 43);
    paintSlope(kit, p, 1920, (x) => 828 + 4 * Math.sin(x / 260), 40, 44, { lit: 0.85 });
    paintRoad(kit, p, 1920, () => 856, () => 64, 45);
    paintSlope(kit, p, 1920, () => 918, 162, 46, { lit: 0.5 });
    shadeFace(p, 1920, 922, 1080);
    crestGrass(kit, p, 0, 1920, 920, 47, 1100, 18);
    kit.tooth(p, 1920, 1080, 48, 0.05);

    // egrets standing in the reeds, each its own size, place and timing
    const er = kit.rng(49);
    const birds = Array.from({ length: 9 }, (_, i) => {
      const x = 900 + er() * 560;
      return {
        x, y: 812 + er() * 14, e: 0.5 + er() * 0.22, dir: er() < 0.7 ? 1 : -1,
        delay: i === 0 ? 0 : 0.04 + er() * 0.28, rate: 3.2 + er() * 0.9,
        vx: (er() < 0.75 ? 1 : -1) * (40 + er() * 70), vy: 90 + er() * 60, ay: 40 + er() * 60, lean: (er() - 0.5) * 6, seed: 60 + i * 5,
      };
    });
    for (const [i, b] of birds.entries()) kit.cue(`egret${i + 1}`, te + b.delay, 'wings', { minor: true, rate: b.rate });

    // speed: rolling, coasting through the bell and the birds, then pedalling on toward the sun
    const speed = (u) => (u < 0.6 ? 250 : u < 2.9 ? 250 - 34 * ((u - 0.6) / 2.3) : 216 + 90 * kit.smooth((u - 2.9) / 1.2));
    const pedalling = (u) => u < 0.6 || u >= 2.9;
    const motion = (u) => {
      let x = 0;
      let c = 0.4;
      const h = 1 / 240;
      for (let k = 0; k < u; k += h) {
        const d = Math.min(h, u - k);
        const vv = speed(k) * d;
        x += vv;
        if (pedalling(k)) c += vv / s / WHEEL_R / GEAR;
      }
      return { x, crank: c };
    };
    const x0 = 300;
    const press = (u) => Math.max(Math.exp(-(((u - b1) / 0.06) ** 2)), Math.exp(-(((u - b2) / 0.06) ** 2)));
    return (g, t, dur) => {
      const tt = kit.twos(t);
      const z = 1 + 0.025 * kit.smooth(t / dur);
      g.save();
      g.translate(1300, 820);
      g.scale(z, z);
      g.translate(-1300, -820);
      g.drawImage(plate.canvas, 0, 0);
      glitter(kit, g, t, sun[0], horizon + 14, 820, 240, 50);
      reeds(kit, g, t, [[820, 1560, 836, 60, 140, 70], [80, 520, 836, 40, 100, 34]], 51, { backlit: true });
      // standing birds sit among the reeds, the flying ones above them
      const flying = [];
      for (const b of birds) {
        const k = tt - (te + b.delay);
        if (k < 0) egret(kit, g, b.x, b.y, b.e, b.dir, { standing: true, lean: b.lean * Math.sin(tt * 2 + b.seed), seed: b.seed });
        else flying.push([b, k]);
      }
      reeds(kit, g, t, [[860, 1520, 846, 40, 90, 46]], 52, { backlit: true });
      for (const [b, k] of flying) {
        const x = b.x + b.vx * k + 20 * k * k * Math.sign(b.vx);
        const y = b.y - 30 - b.vy * k - b.ay * k * k;
        const wing = Math.sin(TAU * b.rate * k + Math.PI / 2);
        egret(kit, g, x, y, b.e * (1 - 0.08 * k), Math.sign(b.vx), { wing, seed: b.seed });
      }
      const m = motion(tt);
      const x = x0 + m.x;
      const looking = kit.smooth((tt - te - 0.1) / 0.3) * (1 - kit.smooth((tt - 2.7) / 0.4));
      const ped = pedalling(tt) ? 1 : 0;
      const bobBell = 3 * press(tt);
      pelican(kit, g, x, roadY, s, {
        wheel: m.x / s / WHEEL_R, crank: m.crank,
        bob: ped * 2.5 * Math.sin(2 * m.crank) - bobBell,
        pouch: ped * 4 * Math.sin(2 * m.crank - 0.8) + 6 * looking * Math.sin((tt - te) * 6) * Math.exp(-Math.max(0, tt - te) * 1.5),
        crest: 5 * looking + ped * 2 * Math.sin(2 * m.crank - 1),
        flick: press(tt), look: 0.2 * looking,
      });
      kit.actor('鹈鹕', { x, y: roadY, s, facing: 'right' });
      kit.grass(g, [0, 1920], 1068, { n: 240, len: 50, colors: ['#8f8c4d', '#7a7448', '#6d6c5a', '#9a8a6a'], lean: 0.2, r: kit.rng(53), sway: 0.12 * Math.sin(tt * 1.5 + 1), width: 3 });
      g.restore();
    };
  },
};
