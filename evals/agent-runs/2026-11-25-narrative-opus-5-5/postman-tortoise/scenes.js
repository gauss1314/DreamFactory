import {
  paintSky, paintClouds, paintFarBank, paintRiver, glitter, paintHouses, paintWall, paintArchBridge,
  paintCobbles, paintPuddle, ripples, rain, lampPost, path, cel, line, groundShadow,
} from '/runtime/painters.js';

const INK = '#3b2a2e';

// ---------- the tortoise postman (side view, facing right; origin on the ground under the shell) ----------
const C = 90; // body travel per full gait cycle, in the tortoise's own units
// diagonal pairs move together: near-front with far-back, far-front with near-back
const LEGS = [
  { home: 60, off: 0, far: false },
  { home: 40, off: 0.5, far: true },
  { home: -66, off: 0.5, far: false },
  { home: -86, off: 0, far: true },
];
const frac = (v) => v - Math.floor(v);
/** Foot position relative to the body: planted feet move back exactly as far as the body moves on. */
function foot(home, u) {
  if (u < 0.75) return [home + 0.375 * C - u * C, 0];
  const w = (u - 0.75) / 0.25;
  return [home - 0.375 * C + w * 0.75 * C, 13 * Math.sin(Math.PI * w)];
}

const COL = {
  skin: '#b9b27c', skinShade: '#7d7396', skinRim: '#f3dfac',
  shell: '#7d8a4c', shellShade: '#4b4f72', shellRim: '#e9cf8e',
  plastron: '#d9c58a',
  leaf: '#6c9a56', leafShade: '#3e6458', leafRim: '#cde59c', vein: '#4a7a4e',
  cap: '#3e5c94', capShade: '#2a3468', capRim: '#a2bce6',
  letter: '#f4ebd7', letterShade: '#c6b9cc', seal: '#c4473a',
};

function leg(kit, g, L, bob, light, far, seed) {
  const [fx, lift] = L.f;
  const hx = L.home;
  const hy = -42 + bob;
  const mx = (hx + fx) / 2;
  const my = (hy - lift - 9) / 2;
  const { P, q } = path(kit, [
    [hx - 17, hy - 8], [hx + 17, hy - 8], [mx + 16, my], [fx + 18, -10 - lift], [fx + 22, -2 - lift],
    [fx + 2, 1 - lift], [fx - 17, -1 - lift], [fx - 18, -10 - lift], [mx - 16, my],
  ]);
  const base = far ? kit.css(kit.mix(COL.skin, COL.skinShade, 0.4)) : COL.skin;
  cel(g, P, { base, shade: COL.skinShade, rim: far ? null : COL.skinRim, light, sd: 8, rw: 3 });
  line(kit, g, q, 3.4, seed);
  // claws
  for (let k = 0; k < 3; k++) kit.ink(g, [[fx + 8 + k * 5, -4 - lift, 2.2], [fx + 12 + k * 5, -lift, 0.8]], INK);
}

function lotusLeaf(kit, g, light, seed) {
  // the stem, stuck into the shell
  kit.ink(g, [[0, 4, 7], [-5, -60, 6], [4, -118, 5]], '#56743c');
  g.save();
  g.translate(4, -122);
  const { P, q } = path(kit, [
    [-150, 20], [-112, -4], [-56, -20], [0, -26], [56, -20], [112, -4], [150, 20],
    [126, 25], [90, 15], [46, 24], [0, 14], [-46, 24], [-90, 15], [-126, 25],
  ]);
  cel(g, P, { base: COL.leaf, shade: COL.leafShade, rim: COL.leafRim, light, sd: 14, rw: 4 });
  g.save();
  g.clip(P);
  for (const [ex, ey] of [[-150, 22], [-100, 14], [-48, 22], [0, 16], [48, 22], [100, 14], [150, 22]]) {
    kit.ink(g, [[0, -22, 2.6], [ex * 0.5, ey * 0.5 - 12, 1.8], [ex, ey, 0.6]], COL.vein);
  }
  // rain beaded on the leaf
  for (const [dx, dy, r0] of [[-70, -6, 5], [30, -14, 4], [92, 4, 4.5], [-24, -16, 3]]) {
    g.fillStyle = 'rgba(40,70,70,0.45)';
    g.beginPath();
    g.ellipse(dx + 1, dy + 2, r0, r0 * 0.7, 0, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = 'rgba(240,250,235,0.85)';
    g.beginPath();
    g.ellipse(dx - 1, dy - 1, r0 * 0.45, r0 * 0.35, 0, 0, Math.PI * 2);
    g.fill();
  }
  g.restore();
  line(kit, g, q, 3.2, seed + 5);
  g.restore();
}

function head(kit, g, light, { letter, slide, blink, clipX, hx, hy, ang, seed }) {
  // the letter, held by its edge in the beak, drawn first so the beak overlaps it
  if (letter && slide < 90) {
    g.save();
    if (Number.isFinite(clipX)) {
      g.beginPath();
      g.rect(-2000, -2000, clipX + 2000, 4000);
      g.clip();
    }
    g.translate(hx, hy);
    g.rotate(ang);
    const x0 = 30 + slide;
    const { P, q } = path(kit, [[x0, 0], [x0 + 29, -1], [x0 + 58, 0], [x0 + 58, 18], [x0 + 58, 36], [x0 + 29, 37], [x0, 36], [x0, 18]]);
    cel(g, P, { base: COL.letter, shade: COL.letterShade, light, sd: 5, rw: 2 });
    kit.ink(g, [[x0 + 2, 2, 1.6], [x0 + 29, 19, 1.8], [x0 + 56, 2, 1.4]], INK, { taper: true });
    g.fillStyle = COL.seal;
    g.beginPath();
    g.arc(x0 + 29, 19, 4, 0, Math.PI * 2);
    g.fill();
    line(kit, g, q, 2.4, seed + 9);
    g.restore();
  }
  g.save();
  g.translate(hx, hy);
  g.rotate(ang);
  const H = path(kit, [[-20, -15], [2, -21], [24, -17], [38, -6], [43, 4], [34, 14], [10, 18], [-16, 14]]);
  cel(g, H.P, { base: COL.skin, shade: COL.skinShade, rim: COL.skinRim, light, sd: 7, rw: 3 });
  line(kit, g, H.q, 3.2, seed + 3);
  // eye
  if (blink) {
    kit.ink(g, [[13, -5, 1.5], [18, -3, 2.4], [23, -5, 1.5]], INK);
  } else {
    g.fillStyle = '#2a2030';
    g.beginPath();
    g.ellipse(18, -5, 4.2, 5.4, 0, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = '#fff4dc';
    g.beginPath();
    g.arc(19.5, -7, 1.6, 0, Math.PI * 2);
    g.fill();
  }
  kit.ink(g, [[42, 5, 1.2], [33, 7, 2.2], [24, 6, 1]], INK);
  g.fillStyle = INK;
  g.fillRect(37, -3, 2, 2);
  // the postman's cap
  const K = path(kit, [[-16, -13], [-11, -29], [5, -38], [23, -33], [30, -20], [12, -15]]);
  cel(g, K.P, { base: COL.cap, shade: COL.capShade, rim: COL.capRim, light, sd: 6, rw: 2.5 });
  line(kit, g, K.q, 2.8, seed + 4);
  const V = path(kit, [[24, -22], [46, -19], [45, -14], [26, -16]]);
  cel(g, V.P, { base: COL.capShade, shade: null, light });
  line(kit, g, V.q, 2.2, seed + 6);
  g.fillStyle = '#f2c14e';
  g.beginPath();
  g.arc(10, -28, 3, 0, Math.PI * 2);
  g.fill();
  g.restore();
}

/**
 * d: distance walked (own units), phi: gait phase, neck 0..1 stretch, push: extra reach,
 * lookUp 0..1, leaf: leaf tilt in radians, letter/slide/clipX: the letter and the mail slot.
 */
function tortoise(kit, g, x, y, s, o = {}) {
  const { d = 0, phi = 0, neck = 0, push = 0, lookUp = 0, leaf = 0, light = [1, -0.45], letter = true, slide = 0,
    clipX = Infinity, blink = false, seed = 1 } = o;
  const u0 = d / C + phi;
  const bob = -2.4 * Math.sin(2 * Math.PI * u0 * 2) ** 2;
  g.save();
  g.translate(x, y);
  g.scale(s, s);
  const legs = LEGS.map((L) => ({ ...L, f: foot(L.home, frac(u0 + L.off)) }));
  for (const [i, L] of legs.entries()) if (L.far) leg(kit, g, L, bob, light, true, seed + 20 + i);
  // belly plate
  const B = path(kit, [[-100, -44 + bob], [0, -46 + bob], [100, -44 + bob], [88, -26 + bob], [0, -22 + bob], [-88, -26 + bob]]);
  cel(g, B.P, { base: COL.plastron, shade: COL.skinShade, light, sd: 6 });
  // tail
  const T = path(kit, [[-104, -50 + bob], [-128, -34 + bob], [-100, -34 + bob]]);
  cel(g, T.P, { base: COL.skin, shade: COL.skinShade, light, sd: 4 });
  line(kit, g, T.q, 2.6, seed + 30);
  // neck and head
  const step = Math.sin(2 * Math.PI * u0 * 2);
  const hx = 146 + 45 * neck + push - 14 * lookUp + 2 * step;
  const hy = -70 + bob - 55 * neck - 34 * lookUp;
  const ang = -0.95 * lookUp;
  const N = path(kit, [
    [80, -92 + bob], [(80 + hx) / 2, (-92 + bob + hy - 15) / 2 - 2], [hx - 14, hy - 15],
    [hx - 12, hy + 15], [(94 + hx) / 2, (-40 + bob + hy + 15) / 2 + 2], [94, -40 + bob],
  ]);
  cel(g, N.P, { base: COL.skin, shade: COL.skinShade, rim: COL.skinRim, light, sd: 7, rw: 3 });
  line(kit, g, N.q, 3, seed + 31);
  const mxn = (100 + hx) / 2;
  const myn = (-66 + bob + hy) / 2;
  kit.ink(g, [[mxn - 4, myn - 8, 1], [mxn, myn, 1.8], [mxn - 2, myn + 8, 1]], INK);
  head(kit, g, light, { letter, slide, blink, clipX, hx, hy, ang, seed });
  for (const [i, L] of legs.entries()) if (!L.far) leg(kit, g, L, bob, light, false, seed + 40 + i);
  // shell
  g.save();
  g.translate(0, bob);
  const S = path(kit, [[-112, -40], [-104, -82], [-70, -118], [-15, -136], [40, -130], [84, -104], [104, -62], [106, -40], [60, -33], [0, -31], [-60, -33]]);
  cel(g, S.P, { base: COL.shell, shade: COL.shellShade, rim: COL.shellRim, light, sd: 16, rw: 5 });
  g.save();
  g.clip(S.P);
  kit.ink(g, [[-100, -54, 2], [-50, -50, 2.6], [0, -48, 2.6], [50, -50, 2.6], [100, -56, 2]], INK, { taper: false });
  kit.ink(g, [[-74, -102, 1.6], [-20, -119, 2.4], [36, -115, 2.4], [80, -92, 1.6]], INK);
  for (const [a, b] of [[[-50, -110], [-56, -52]], [[6, -122], [2, -49]], [[58, -108], [64, -53]]]) {
    kit.ink(g, [[a[0], a[1], 1.4], [(a[0] + b[0]) / 2 + 3, (a[1] + b[1]) / 2, 2.4], [b[0], b[1], 1.4]], INK);
  }
  for (const mx of [-86, -60, -30, 0, 30, 60, 86]) kit.ink(g, [[mx, -50, 1.8], [mx + 2, -38, 1]], INK);
  // a dry brush of light on the dome
  kit.ink(g, [[-30, -122, 1], [10, -128, 5], [46, -118, 1]], 'rgba(255,240,200,0.35)');
  g.restore();
  line(kit, g, S.q, 4, seed + 50);
  g.restore();
  // the lotus-leaf umbrella, planted in the shell
  g.save();
  g.translate(-10, -128 + bob);
  g.rotate(leaf);
  lotusLeaf(kit, g, light, seed + 60);
  g.restore();
  g.restore();
}

/** Footfall moments: a diagonal pair lands each time its gait phase passes a whole number. */
function stepCues(kit, dist, dur, phi) {
  let pa = null;
  let pb = null;
  let k = 0;
  for (let f = 0; f <= Math.round(dur * 24); f++) {
    const t = f / 24;
    const u = dist(kit.twos(t)) / C + phi;
    const a = Math.floor(u);
    const b = Math.floor(u + 0.5);
    if ((pa !== null && a > pa) || (pb !== null && b > pb)) kit.cue(`step${++k}`, t, 'step', { minor: true });
    pa = a;
    pb = b;
  }
}

const SPEED = 116; // own units per second
const BOX = [-7, 34]; // where the post box sits, relative to the numbers it is drawn with

/** A straight-edged shape for made things (wood, boards): { P, q } like path(), without the rounding. */
function poly(pts) {
  const P = new Path2D();
  P.moveTo(pts[0][0], pts[0][1]);
  for (const v of pts.slice(1)) P.lineTo(v[0], v[1]);
  P.closePath();
  const q = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    for (let k = 0; k < 6; k++) q.push([a[0] + ((b[0] - a[0]) * k) / 6, a[1] + ((b[1] - a[1]) * k) / 6]);
  }
  return { P, q };
}
const DBG = {}; // close-up framing for checking details, e.g. { side: [zoom, cx, cy] }
function dbg(g, key) {
  const v = DBG[key];
  if (!v) return;
  g.translate(960, 540);
  g.scale(v[0], v[0]);
  g.translate(-v[1], -v[2]);
}

// ---------- shots ----------
export default {
  wide(kit) {
    const W = 1920;
    const plate = kit.layer(W, 1080);
    const p = plate.g;
    const sun = [1010, 468];
    paintSky(kit, p, W, 560, sun, 3);
    paintClouds(kit, p, [[280, 120, 720, 150], [900, 70, 620, 120], [1520, 170, 560, 150], [1800, 330, 360, 90], [600, 300, 420, 80]], sun);
    paintFarBank(kit, p, W, 556, 4);
    paintRiver(kit, p, W, 560, 792, sun[0], 5);
    paintHouses(kit, p, -20, 880, 560, 11, { reflect: 0.5 });
    paintHouses(kit, p, 1620, 1980, 560, 12, { reflect: 0.5 });
    paintArchBridge(kit, p, 1120, 1610, 470, 560, 7);
    paintWall(kit, p, 790, 832, 9);
    paintCobbles(kit, p, 832, 1080, W, 13);
    paintPuddle(kit, p, 930, 1012, 130, 20, 1);
    paintPuddle(kit, p, 1380, 958, 90, 14, 2);
    kit.grass(p, [0, W], 834, { n: 160, len: 16, colors: ['#5e7050', '#7d8a4c', '#4e5a50'], lean: 0.15, r: kit.rng(8), width: 1.6 });
    lampPost(kit, p, 1650, 948, 560, 0);
    kit.tooth(p, W, 1080);

    const dist = (tt) => SPEED * tt;
    stepCues(kit, dist, 4, 0.1);
    return (g, t) => {
      const c = 1 + 0.025 * (t / 4);
      g.save();
      dbg(g, 'wide');
      g.translate(960, 620);
      g.scale(c, c);
      g.translate(-960, -620);
      g.drawImage(plate.canvas, 0, 0);
      glitter(kit, g, t, sun[0], 575, 785, 360, 17);
      ripples(kit, g, t, 930, 1012, 130, 20, 21, 1.8);
      ripples(kit, g, t, 1380, 958, 90, 14, 22, 1.4);
      const tt = kit.twos(t);
      const s = 0.42;
      const x = 250 + dist(tt) * s;
      const y = 972;
      groundShadow(g, x, y, s, 300, 'rgba(60,45,95,0.5)');
      tortoise(kit, g, x, y, s, { d: dist(tt), phi: 0.1, leaf: 0.025 * Math.sin(2 * Math.PI * (dist(tt) / C) * 2), light: [1, -0.45] });
      kit.actor('乌龟', { x, y, s, facing: 'right' });
      rain(kit, g, t, 0.55, 31);
      g.restore();
    };
  },

  side(kit, scene) {
    const W = 1920;
    const plate = kit.layer(W, 1080);
    const p = plate.g;
    const sun = [1260, 392];
    paintSky(kit, p, W, 430, sun, 5);
    paintClouds(kit, p, [[380, 110, 640, 130], [1100, 60, 520, 100], [1700, 150, 480, 120]], sun);
    paintFarBank(kit, p, W, 426, 6);
    paintRiver(kit, p, W, 430, 642, sun[0], 8);
    paintHouses(kit, p, -40, 1100, 430, 14, { reflect: 0.45 });
    paintHouses(kit, p, 1430, 1980, 430, 15, { reflect: 0.45 });
    paintWall(kit, p, 640, 700, 16);
    paintCobbles(kit, p, 700, 1080, W, 18);
    paintPuddle(kit, p, 470, 1012, 170, 24, 3);
    // the foot of the stone bridge: a parapet rising to the right, and its end post
    {
      const st = kit.layer(W, 1080);
      paintWall(kit, st.g, 500, 930, 41);
      const para = new Path2D();
      para.moveTo(1440, 912);
      para.lineTo(1440, 742);
      para.lineTo(1920, 548);
      para.lineTo(1920, 912);
      para.closePath();
      p.save();
      p.clip(para);
      p.drawImage(st.canvas, 0, 0);
      p.fillStyle = 'rgba(40,30,70,0.18)';
      p.fillRect(1440, 540, 480, 380);
      p.restore();
      kit.ink(p, [[1440, 740, 9], [1700, 634, 10], [1920, 546, 9]], '#7a7590', { taper: false });
      kit.ink(p, [[1440, 735, 3], [1700, 629, 3], [1920, 541, 3]], 'rgba(255,214,170,0.55)', { taper: false });
      const post = new Path2D();
      post.rect(1404, 690, 76, 222);
      p.save();
      p.clip(post);
      p.drawImage(st.canvas, 0, -120);
      p.restore();
      p.fillStyle = '#5a5672';
      p.fillRect(1396, 676, 92, 18);
      p.fillStyle = 'rgba(255,214,170,0.45)';
      p.fillRect(1396, 676, 92, 3);
      p.fillStyle = 'rgba(40,30,70,0.25)';
      p.fillRect(1404, 694, 14, 218);
    }
    // the little wooden post box on its post (drawn 7 px left and 34 px lower than its numbers)
    {
      const light = [1, -0.45];
      p.save();
      p.translate(BOX[0], BOX[1]);
      const postP = poly([[1138, 788], [1168, 788], [1171, 874], [1135, 874]]);
      cel(p, postP.P, { base: '#7e4f3e', shade: '#4e3448', light, sd: 8 });
      line(kit, p, postP.q, 3, 70);
      const side = poly([[1053, 636], [1085, 644], [1085, 792], [1053, 784]]);
      cel(p, side.P, { base: '#6e4648', shade: null, light });
      line(kit, p, side.q, 3, 71);
      const front = poly([[1085, 644], [1238, 644], [1238, 792], [1085, 792]]);
      cel(p, front.P, { base: '#a2603e', shade: '#6a4250', rim: '#e8b07c', light, sd: 12, rw: 4 });
      p.save();
      p.clip(front.P);
      for (const yy of [680, 718, 756]) kit.ink(p, [[1086, yy, 1.4], [1160, yy + 1, 2], [1237, yy, 1.4]], 'rgba(70,40,50,0.5)');
      p.restore();
      line(kit, p, front.q, 3.4, 72);
      // a painted envelope on the front
      p.strokeStyle = 'rgba(244,232,205,0.9)';
      p.lineWidth = 3;
      p.strokeRect(1132, 694, 62, 40);
      p.beginPath();
      p.moveTo(1132, 694);
      p.lineTo(1163, 716);
      p.lineTo(1194, 694);
      p.stroke();
      const roofSide = poly([[1044, 634], [1078, 646], [1161, 598], [1130, 588]]);
      cel(p, roofSide.P, { base: '#4a3e5c', shade: null, light });
      line(kit, p, roofSide.q, 3, 73);
      const roof = poly([[1076, 648], [1161, 597], [1248, 648]]);
      cel(p, roof.P, { base: '#6a5476', shade: '#46395a', rim: '#d9a88e', light, sd: 8 });
      line(kit, p, roof.q, 3.2, 74);
      // the slot in the side face
      p.fillStyle = '#24192a';
      p.beginPath();
      p.moveTo(1062, 706);
      p.lineTo(1072, 709);
      p.lineTo(1072, 776);
      p.lineTo(1062, 773);
      p.closePath();
      p.fill();
      p.restore();
    }
    const fg = kit.layer(W, 1080);
    kit.grass(fg.g, [0, 240], 1084, { n: 90, len: 110, colors: ['#4e5a50', '#5c6845', '#6a6a48'], lean: 0.25, r: kit.rng(77), width: 4 });
    kit.grass(fg.g, [1740, 1920], 1084, { n: 70, len: 90, colors: ['#4e5a50', '#5c6845', '#6a6a48'], lean: -0.2, r: kit.rng(78), width: 4 });
    p.save();
    p.filter = 'blur(4px)';
    p.drawImage(fg.canvas, 0, 0);
    p.restore();
    kit.tooth(p, W, 1080);

    // walking, slowing to a stop with every foot planted
    const v0 = SPEED;
    const tConst = 1.6;
    const tSlow = 0.7;
    const D = v0 * (tConst + tSlow / 2);
    const dist = (tt) => (tt < tConst ? v0 * tt : tt < tConst + tSlow ? v0 * tConst + v0 * ((tt - tConst) - (tt - tConst) ** 2 / (2 * tSlow)) : D);
    const phi = frac(0.6 - D / C);
    const s = 1.15;
    const xStop = 760;
    const x0 = xStop - D * s;
    const slotWorld = 1066 + BOX[0];
    const clipX = (slotWorld - xStop) / s;
    const post = scene.events.post; // the letter drops in
    const stopAt = tConst + tSlow;
    stepCues(kit, dist, stopAt + 0.05, phi);

    return (g, t) => {
      const c = 1 + 0.02 * (t / 4);
      g.save();
      dbg(g, 'side');
      g.translate(900, 760);
      g.scale(c, c);
      g.translate(-900, -760);
      g.drawImage(plate.canvas, 0, 0);
      glitter(kit, g, t, sun[0], 445, 636, 420, 18);
      ripples(kit, g, t, 470, 1012, 170, 24, 23, 1.6);
      const tt = kit.twos(t);
      const d = dist(tt);
      const x = x0 + d * s;
      const y = 905;
      // reach: hold after stopping, stretch, push the letter in, hold, draw back
      const out = kit.smooth((tt - 2.55) / 0.35);
      const back = kit.smooth((tt - 3.4) / 0.5);
      const neck = out * (1 - back);
      const push = 12 * kit.smooth((tt - 2.88) / 0.12) * (1 - back);
      const slide = tt >= post ? 18 + (tt - post) * 700 : 0;
      // the leaf sways with the gait, swings on when the body stops, and nods as the neck shoots out
      const sinceStop = Math.max(0, tt - stopAt);
      const sinceReach = Math.max(0, tt - 2.55);
      const leaf = (tt < stopAt ? 0.025 * Math.sin(2 * Math.PI * (d / C + phi) * 2) : 0)
        + 0.07 * Math.exp(-sinceStop * 3.2) * Math.sin(sinceStop * 10) * (tt >= stopAt ? 1 : 0)
        + 0.04 * Math.exp(-sinceReach * 4) * Math.sin(sinceReach * 11) * (tt >= 2.55 ? 1 : 0);
      groundShadow(g, x, y, s, 300, 'rgba(60,45,95,0.5)');
      tortoise(kit, g, x, y, s, { d, phi, neck, push, leaf, light: [1, -0.45], slide, clipX, letter: true, blink: tt > 2.3 && tt < 2.42 });
      kit.actor('乌龟', { x, y, s, facing: 'right' });
      // the slot's flap: pushed open by the letter, snaps shut once it drops
      const front = 146 + 45 * neck + push + 88;
      const open = tt < post ? kit.clamp((front - clipX) / 20) : 0;
      const a = open * 0.9;
      g.save();
      g.translate(BOX[0], BOX[1]);
      g.fillStyle = '#7a4c48';
      g.beginPath();
      g.moveTo(1060, 704);
      g.lineTo(1074, 707);
      g.lineTo(1074 - 70 * Math.sin(a), 707 + 70 * Math.cos(a));
      g.lineTo(1060 - 70 * Math.sin(a), 704 + 70 * Math.cos(a));
      g.closePath();
      g.fill();
      g.strokeStyle = INK;
      g.lineWidth = 2;
      g.stroke();
      g.restore();
      rain(kit, g, t, 0.4, 32);
      g.restore();
    };
  },

  lamp(kit, scene) {
    const W = 1920;
    const plate = kit.layer(W, 1080);
    const p = plate.g;
    const sun = [1560, 520];
    paintSky(kit, p, W, 560, sun, 7);
    paintClouds(kit, p, [[300, 150, 620, 120], [1150, 90, 560, 110], [1700, 260, 420, 90]], sun);
    paintFarBank(kit, p, W, 556, 9);
    paintRiver(kit, p, W, 560, 722, sun[0], 10);
    paintHouses(kit, p, -30, 1980, 560, 19, { reflect: 0.5 });
    paintWall(kit, p, 720, 762, 20);
    paintCobbles(kit, p, 762, 1080, W, 24);
    paintPuddle(kit, p, 1060, 1010, 220, 28, 4);
    kit.tooth(p, W, 1080);
    // evening deepens: a cool wash over the whole plate
    p.fillStyle = 'rgba(38,30,78,0.28)';
    p.fillRect(0, 0, W, 1080);

    const on0 = scene.events.lamp;
    const lampOn = (t) => {
      const k = t - on0;
      if (k < 0) return 0;
      if (k < 0.08) return (0.55 * k) / 0.08;
      if (k < 0.16) return 0.55 - (0.3 * (k - 0.08)) / 0.08;
      if (k < 0.26) return 0.25 + (0.75 * (k - 0.16)) / 0.1;
      return 1;
    };
    const lx = 1086;
    const ly = 242;
    const ground = 960;
    const tx = 700;
    const ty = 950;
    const s = 1;
    const body = kit.layer(W, 1080);
    // a drop runs off the leaf's left edge and falls clear of the shell
    const dripT = 2.2;
    const dripX = tx + (-10 + 4 - 150) * s;
    const dripY0 = ty + (-128 - 122 + 22) * s;
    const fall = Math.sqrt((2 * (ty - dripY0)) / 2600);
    kit.cue('drip', dripT, 'drip', { minor: true });
    kit.cue('splash', dripT + fall, 'splash', { minor: true });

    return (g, t) => {
      const c = 1 + 0.035 * (t / 4);
      g.save();
      dbg(g, 'lamp');
      g.translate(820, 640);
      g.scale(c, c);
      g.translate(-820, -640);
      g.drawImage(plate.canvas, 0, 0);
      const on = lampOn(t);
      const tt = kit.twos(t);
      if (on > 0) {
        g.save();
        g.globalCompositeOperation = 'screen';
        g.translate(lx, ground + 10);
        g.scale(1, 0.24);
        const pool = g.createRadialGradient(0, 0, 20, 0, 0, 640);
        pool.addColorStop(0, `rgba(255,196,120,${0.55 * on})`);
        pool.addColorStop(1, 'rgba(255,170,110,0)');
        g.fillStyle = pool;
        g.fillRect(-700, -700, 1400, 1400);
        g.restore();
        // the lamp shows in the puddle
        g.save();
        g.beginPath();
        g.ellipse(1060, 1010, 220, 28, 0, 0, Math.PI * 2);
        g.clip();
        const ref = g.createLinearGradient(lx - 40, 0, lx + 40, 0);
        ref.addColorStop(0, 'rgba(255,220,150,0)');
        ref.addColorStop(0.5, `rgba(255,226,160,${0.75 * on})`);
        ref.addColorStop(1, 'rgba(255,220,150,0)');
        g.fillStyle = ref;
        g.fillRect(lx - 40, 982, 80, 60);
        g.restore();
      }
      const rip = 1 - kit.smooth((t - 1.0) / 1.8);
      if (rip > 0) {
        g.save();
        g.globalAlpha = rip;
        ripples(kit, g, t, 1060, 1010, 220, 28, 25, 1.6);
        g.restore();
      }
      // the drop's splash on the stones
      const since = tt - (dripT + fall);
      if (since >= 0 && since < 0.5) {
        g.strokeStyle = `rgba(235,235,250,${0.6 * (1 - since / 0.5)})`;
        g.lineWidth = 2;
        g.beginPath();
        g.ellipse(dripX, ty, 6 + since * 60, (6 + since * 60) * 0.22, 0, 0, Math.PI * 2);
        g.stroke();
      }
      groundShadow(g, tx - 40 * on, ty, s, 300, 'rgba(50,36,90,0.55)');
      // the tortoise: notices, then lifts its head to the light; warm light falls on it
      const look = kit.smooth((tt - 1.25) / 0.6);
      const leaf = 0.03 * Math.exp(-Math.max(0, tt - 1.25) * 3) * Math.sin(Math.max(0, tt - 1.25) * 10) * (tt > 1.25 ? 1 : 0);
      body.g.clearRect(0, 0, W, 1080);
      tortoise(kit, body.g, tx, ty, s, { d: 0, phi: 0.6, neck: 0.3 * look, lookUp: look, leaf, letter: false, light: [0.55, -0.85], blink: tt > 2.9 && tt < 3.05 });
      if (on > 0) {
        body.g.save();
        body.g.globalCompositeOperation = 'source-atop';
        const warm = body.g.createRadialGradient(lx, ly, 40, lx, ly, 900);
        warm.addColorStop(0, `rgba(255,214,140,${0.55 * on})`);
        warm.addColorStop(1, `rgba(255,170,100,${0.12 * on})`);
        body.g.fillStyle = warm;
        body.g.fillRect(0, 0, W, 1080);
        body.g.restore();
      }
      g.drawImage(body.canvas, 0, 0);
      kit.actor('乌龟', { x: tx, y: ty, s, facing: 'right' });
      lampPost(kit, g, 1000, ground, 190, on);
      if (on > 0) {
        g.save();
        g.globalCompositeOperation = 'screen';
        const halo = g.createRadialGradient(lx, ly, 10, lx, ly, 300);
        halo.addColorStop(0, `rgba(255,236,180,${0.85 * on})`);
        halo.addColorStop(0.25, `rgba(255,200,130,${0.35 * on})`);
        halo.addColorStop(1, 'rgba(255,180,110,0)');
        g.fillStyle = halo;
        g.fillRect(lx - 300, ly - 300, 600, 600);
        g.beginPath();
        g.moveTo(lx - 18, ly + 20);
        g.lineTo(lx + 18, ly + 20);
        g.lineTo(lx + 420, ground + 40);
        g.lineTo(lx - 560, ground + 40);
        g.closePath();
        const cone = g.createLinearGradient(0, ly, 0, ground);
        cone.addColorStop(0, `rgba(255,214,150,${0.16 * on})`);
        cone.addColorStop(1, `rgba(255,200,140,${0.04 * on})`);
        g.fillStyle = cone;
        g.fill();
        g.restore();
      }
      // the drop, falling under gravity, on twos
      const df = tt - dripT;
      if (df >= 0 && df < fall) {
        const yy = dripY0 + 0.5 * 2600 * df * df;
        g.fillStyle = 'rgba(225,235,250,0.85)';
        g.beginPath();
        g.ellipse(dripX, yy, 3, 6, 0, 0, Math.PI * 2);
        g.fill();
      }
      rain(kit, g, t, 0.35 * (1 - kit.smooth((t - 0.4) / 2.2)), 33);
      g.restore();
    };
  },
};
