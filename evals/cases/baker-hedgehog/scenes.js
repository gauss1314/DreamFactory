import { paintSky, paintClouds, paintFarBank, paintHouses, paintCobbles, path, cel, line, groundShadow, DEFAULT_LOOK } from '/runtime/painters.js';

// ---------------------------------------------------------------- palette
const INK = '#3b2a2e';
const C = {
  spine: '#735248', spineDark: '#4c3442', spineRim: '#b08a72', spineTip: '#ead8bc',
  fur: '#f1dcbc', furShade: '#c9a1a2', furRim: '#fff4dc',
  nose: '#2f2228', leg: '#7a5550', legFar: '#5c4050',
  hat: '#fbf6ee', hatShade: '#c9c2dc', hatRim: '#fffaf0',
  wood: '#b27b47', woodShade: '#7a5044', woodRim: '#eab97f', woodDark: '#5e3c34', woodFar: '#6a4a48',
  bread: '#d8954a', breadShade: '#a25f40', breadRim: '#f8cc88', crust: '#8a4c34',
  pg: '#a2a6bc', pgShade: '#6a6e92', pgRim: '#ece4ee', pgHead: '#8c92ae', neck: '#76a49a', neck2: '#a58cb8',
  wing: '#8e93ad', wingShade: '#5e6286', wingTip: '#4a4c6c', feet: '#d87a70', beak: '#4a3a3e', cere: '#efe6e0', eye: '#e8823a',
};
const LIGHT = [1, -0.45]; // the low sun is to the right, ahead of the baker

// ---------------------------------------------------------------- small helpers
function shape(kit, g, pts, colors, inkW, seed, sd = 10) {
  const { P, q } = path(kit, pts);
  cel(g, P, { ...colors, light: LIGHT, sd, rw: 3 });
  if (inkW) line(kit, g, q, inkW, seed);
  return { P, q };
}
function ellipsePts(cx, cy, rx, ry, rot = 0, n = 10, wob = 0, r = null) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const k = 1 + (r ? (r() - 0.5) * wob : 0);
    const x = Math.cos(a) * rx * k;
    const y = Math.sin(a) * ry * k;
    out.push([cx + x * Math.cos(rot) - y * Math.sin(rot), cy + x * Math.sin(rot) + y * Math.cos(rot)]);
  }
  return out;
}
const inPoly = (x, y, poly) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
};

/** Where paintHouses puts its chimneys: the same draws from the same seed. */
function chimneys(kit, x0, x1, base, seed) {
  const r = kit.rng(seed);
  const walls = (kit.look && kit.look.houseWalls) || DEFAULT_LOOK.houseWalls;
  const out = [];
  for (let x = x0; x < x1; ) {
    const w = 60 + r() * 120;
    const h = 70 + r() * 170;
    r(); // roof
    const pitch = 18 + r() * 40;
    kit.jit(walls[Math.floor(r() * walls.length)], r, 10);
    const ch = r() < 0.45 ? r() : -1;
    for (let i = 0; i < 24; i++) r();
    r(); // window size
    if (ch >= 0) out.push([x + w * (0.2 + ch * 0.5) + 6, base - h - (pitch * 0.5 + 22)]);
    x += w + 2 + r() * 14;
  }
  return out;
}

/** Morning mist: a soft band of long, horizontal, blurred strokes. */
function mistLayer(kit, w, h, seed, { color = '#e4dce6', n = 40, alpha = 0.22 } = {}) {
  const raw = kit.layer(w, h);
  const r = kit.rng(seed);
  for (let i = 0; i < n; i++) {
    const y = h * (0.15 + 0.7 * r());
    const x = r() * w;
    const L = 200 + r() * 520;
    kit.stroke(raw.g, [[x, y], [x + L * 0.5, y + (r() - 0.5) * 10], [x + L, y + (r() - 0.5) * 6]], { width: 24 + r() * 40, color, alpha, r, bristles: 4 });
  }
  const out = kit.layer(w, h);
  out.g.filter = 'blur(14px)';
  out.g.drawImage(raw.canvas, 0, 0);
  out.g.filter = 'none';
  return out;
}
function mistBand(g, y0, y1, a, color = [226, 218, 230]) {
  const grd = g.createLinearGradient(0, y0, 0, y1);
  grd.addColorStop(0, `rgba(${color},0)`);
  grd.addColorStop(0.7, `rgba(${color},${a})`);
  grd.addColorStop(1, `rgba(${color},${a * 0.6})`);
  g.fillStyle = grd;
  g.fillRect(0, y0, g.canvas.width, y1 - y0);
}

// ---------------------------------------------------------------- bread
function bunAt(kit, g, cx, cy, rad, rot, seed, sx = 1, sy = 1) {
  g.save();
  g.translate(cx, cy);
  g.rotate(rot);
  g.scale(sx, sy);
  const r = kit.rng(seed);
  shape(kit, g, ellipsePts(0, 0, rad, rad * 0.86, 0, 9, 0.08, r), { base: C.bread, shade: C.breadShade, rim: C.breadRim }, 2.6, seed, rad * 0.35);
  // the scored cross on top, and a dust of flour
  kit.ink(g, [[-rad * 0.42, -rad * 0.3, 2.2], [0, -rad * 0.42, 2.6], [rad * 0.4, -rad * 0.28, 1.8]], kit.css(C.crust, 0.8));
  g.fillStyle = 'rgba(255,248,236,0.55)';
  for (let i = 0; i < 6; i++) g.fillRect((r() - 0.5) * rad, -rad * (0.2 + r() * 0.5), 2, 2);
  g.restore();
}
function loafAt(kit, g, cx, cy, rx, ry, rot, seed, scores = 3) {
  const r = kit.rng(seed);
  shape(kit, g, ellipsePts(cx, cy, rx, ry, rot, 12, 0.06, r), { base: C.bread, shade: C.breadShade, rim: C.breadRim }, 2.6, seed, ry * 0.5);
  for (let i = 0; i < scores; i++) {
    const u = (i + 0.5) / scores - 0.5;
    const x = cx + Math.cos(rot) * rx * u * 1.4;
    const y = cy + Math.sin(rot) * rx * u * 1.4 - ry * 0.25;
    kit.ink(g, [[x - 7, y + 3, 1.6], [x, y - 1, 2.4], [x + 7, y - 4, 1.4]], kit.css(C.crust, 0.75));
  }
}
const PILE_BUN = [226, -152, 20]; // the bun that will be thrown, in cart coordinates
const CDX = 50; // the cart sits this far ahead of the baker's frame: room for his arms, and his nose clear of the box

// ---------------------------------------------------------------- hedgehog and cart
// One local frame for both, facing right, the ground at y = 0. 100 local units = one walk cycle.
const CYCLE = 100;
const STRIDE = 60;
const STANCE = 0.6;
function legPose(D, offset) {
  const u = (((D / CYCLE + offset) % 1) + 1) % 1;
  // in stance the foot moves back exactly as fast as the body moves forward: it stays planted
  if (u < STANCE) return { fx: STRIDE / 2 - (u / STANCE) * STRIDE, lift: 0 };
  const w = (u - STANCE) / (1 - STANCE);
  return { fx: -STRIDE / 2 + w * w * (3 - 2 * w) * STRIDE, lift: 12 * Math.sin(Math.PI * w) };
}
const bobOf = (D) => -2.6 * (0.5 - 0.5 * Math.cos((4 * Math.PI * D) / CYCLE));

const MANTLE = [[40, -126], [22, -150], [-14, -160], [-50, -145], [-76, -112], [-86, -76], [-78, -42], [-56, -24], [-22, -20], [8, -30], [22, -58], [32, -92]];
let SPINES = null;
function spines(kit) {
  if (SPINES) return SPINES;
  const r = kit.rng(31);
  const { q } = path(kit, MANTLE);
  const list = [];
  while (list.length < 95) {
    const x = -84 + r() * 124;
    const y = -158 + r() * 136;
    if (!inPoly(x, y, q)) continue;
    // spines lie back along the body, fanning from the shoulders
    const a = Math.atan2(y + 60, x - 10) - 0.75 + (r() - 0.5) * 0.3;
    const L = 16 + r() * 12;
    list.push([x, y, Math.cos(a) * L, Math.sin(a) * L, r()]);
  }
  list.sort((a, b) => b[1] - a[1] || a[0] - b[0]);
  // the spiky silhouette along the back
  const edge = [];
  const n = q.length;
  for (let i = 0; i < n; i += 3) {
    const [x, y] = q[i];
    if (x > 34 || (y > -34 && x > -60)) continue;
    const [x2, y2] = q[(i + 1) % n];
    const tx = x2 - x;
    const ty = y2 - y;
    const l = Math.hypot(tx, ty) || 1;
    // outward normal of a clockwise outline, swept a little toward the tail
    const nx = ty / l - 0.45;
    const ny = -tx / l;
    const m = Math.hypot(nx, ny);
    edge.push([x, y, (nx / m) * (13 + r() * 9), (ny / m) * (13 + r() * 9)]);
  }
  SPINES = { list, edge };
  return SPINES;
}

function wheel(kit, g, cx, cy, R, ang, far) {
  const col = far ? C.woodFar : C.woodDark;
  const pts = ellipsePts(cx, cy, R - 3.5, R - 3.5, 0, 16);
  kit.ink(g, [...pts, pts[0]].map(([x, y], i) => [x, y, 7 + Math.sin(i * 1.7) * 0.8]), col, { taper: false });
  for (let k = 0; k < 6; k++) {
    const a = ang + (k / 6) * Math.PI * 2;
    kit.ink(g, [[cx, cy, 4.5], [cx + Math.cos(a) * (R - 5), cy + Math.sin(a) * (R - 5), 3.5]], kit.css(far ? C.woodFar : C.woodShade), { taper: false });
  }
  g.beginPath();
  g.arc(cx, cy, 6, 0, Math.PI * 2);
  g.fillStyle = col;
  g.fill();
  if (!far) {
    // the lit rim of the tyre toward the sun
    g.beginPath();
    g.arc(cx, cy, R - 1.5, -1.3, 0.3);
    g.strokeStyle = 'rgba(255,220,170,0.55)';
    g.lineWidth = 2;
    g.stroke();
  }
}

/**
 * The baker and the cart, in local units, drawn at (x, y) with scale s.
 * o: D (distance walked), liftF / liftR (wheel lift on a stone), hop (cart jolt), pile (bread jiggle),
 *    bodyJolt, startle, look (0 ahead, 1 turning, 2 looking back), withBun, hatLag
 */
function baker(kit, g, x, y, s, o) {
  const { D, liftF = 0, liftR = 0, hop = 0, pile = 0, bodyJolt = 0, startle = 0, look = 0, withBun = true, hatLag = 0 } = o;
  g.save();
  g.translate(x, y);
  g.scale(s, s);
  groundShadow(g, 96, 2, 1, 560, 'rgba(80,60,120,0.32)');

  // ---- cart: rigid body pivoting on its rear axle
  const R = 30;
  const jig = 1.1 * Math.sin(D * 0.23) * Math.sin(D * 0.071);
  const rear = [162 + CDX, -R - liftR + hop + jig];
  const front = [287 + CDX, -R - liftF + hop + jig];
  const pitch = Math.atan2(front[1] - rear[1], front[0] - rear[0]);
  const toWorld = ([px, py]) => {
    const dx = px - 162;
    const dy = py + R;
    return [rear[0] + dx * Math.cos(pitch) - dy * Math.sin(pitch), rear[1] + dx * Math.sin(pitch) + dy * Math.cos(pitch)];
  };
  const ang = D / R;
  wheel(kit, g, rear[0] + 10, rear[1] - 5, R, ang + 0.4, true);
  wheel(kit, g, front[0] + 10, front[1] - 5, R, ang + 0.9, true);
  g.save();
  g.translate(rear[0], rear[1]);
  g.rotate(pitch);
  g.translate(-162, R);
  // far rail
  kit.ink(g, [[112, -66, 7], [88, -72, 6], [62, -76, 6]], C.woodFar);
  // bread heaped in the box: it lags the jolt by a drawing
  g.save();
  g.translate(0, pile);
  loafAt(kit, g, 168, -116, 46, 17, -0.12, 401);
  loafAt(kit, g, 270, -118, 52, 18, 0.1, 402, 4);
  loafAt(kit, g, 214, -132, 76, 9, -0.32, 403, 5);
  bunAt(kit, g, 136, -124, 17, 0.2, 404);
  bunAt(kit, g, 312, -128, 17, -0.3, 405);
  bunAt(kit, g, 246, -126, 18, 0.5, 406);
  if (withBun) bunAt(kit, g, PILE_BUN[0], PILE_BUN[1], PILE_BUN[2], 0.1, 407);
  g.restore();
  // the box
  shape(kit, g, [[116, -44], [334, -44], [348, -110], [104, -110]], { base: C.wood, shade: C.woodShade, rim: C.woodRim }, 3.2, 410, 12);
  for (const yy of [-66, -88]) kit.ink(g, [[112, yy + 1, 2.2], [230, yy, 2.8], [340, yy - 1, 1.8]], kit.css(C.woodShade, 0.85));
  shape(kit, g, [[100, -104], [352, -104], [354, -116], [98, -116]], { base: C.woodRim, shade: C.wood }, 2.4, 411, 4);
  for (const xx of [124, 228, 326]) kit.ink(g, [[xx, -48, 5], [xx + (xx - 228) * 0.03, -100, 4]], kit.css(C.woodDark, 0.6));
  g.restore();
  wheel(kit, g, rear[0], rear[1], R, ang, false);
  wheel(kit, g, front[0], front[1], R, ang + 0.5, false);
  const grip = toWorld([64, -74]);
  // contact points in frame pixels: the paw on the rail end, the nose, the back of the box
  const points = { hand: kit.at(g, grip[0], grip[1]) };
  const cart = { handle: kit.at(g, ...toWorld([64, -74])), back: kit.at(g, ...toWorld([82, -92])) };

  // ---- hedgehog
  const bob = bobOf(D) + bodyJolt;
  const legs = [[legPose(D, 0.5), 4, C.legFar], [legPose(D, 0), -8, C.leg]];
  for (const [i, [lp, hx, col]] of legs.entries()) {
    const hip = [hx, -30 + bob];
    const foot = [hx + 8 + lp.fx, -lp.lift - 4];
    const knee = [(hip[0] + foot[0]) / 2 + 6, (hip[1] + foot[1]) / 2];
    kit.ink(g, [[hip[0], hip[1], 12], [knee[0], knee[1], 10], [foot[0], foot[1], 8]], col, { taper: false });
    g.beginPath();
    g.ellipse(foot[0] + 5, foot[1] + 1, 10, 5, 0, 0, Math.PI * 2);
    g.fillStyle = col;
    g.fill();
    if (i === 0) {
      // the far arm reaches the far rail
      kit.ink(g, [[18, -66 + bob, 10], [44, -70 + bob * 0.5, 9], [grip[0] - 4, grip[1] - 4, 8]], C.legFar, { taper: false });
    }
  }
  g.save();
  g.translate(0, bob);
  shape(kit, g, [[6, -28], [26, -38], [34, -64], [30, -88], [14, -80], [0, -50]], { base: C.fur, shade: C.furShade, rim: C.furRim }, 2.6, 420, 8);
  const { P, q } = path(kit, MANTLE);
  cel(g, P, { base: C.spine, shade: C.spineDark, rim: C.spineRim, light: LIGHT, sd: 16, rw: 4 });
  const sp = spines(kit);
  g.save();
  g.clip(P);
  for (const [sx, sy, dx, dy, v] of sp.list) {
    kit.ink(g, [[sx, sy, 4.2], [sx + dx * 0.6, sy + dy * 0.6, 3], [sx + dx, sy + dy, 1]], v < 0.5 ? C.spineDark : '#5e4248');
    kit.ink(g, [[sx + dx * 0.55, sy + dy * 0.55, 2.4], [sx + dx, sy + dy, 0.8]], kit.css(C.spineTip, 0.75));
  }
  g.restore();
  for (const [ex, ey, dx, dy] of sp.edge) {
    const k = 1 + startle * 0.35;
    kit.ink(g, [[ex - dy * 0.15, ey + dx * 0.15, 6], [ex + dx * k * 0.6, ey + dy * k * 0.6, 3], [ex + dx * k, ey + dy * k, 0.6]], C.spineDark);
  }
  line(kit, g, q, 3.6, 421);

  // head: turns about the neck to look back over the shoulder
  g.save();
  g.translate(30, -100);
  g.scale(look === 0 ? 1 : look === 1 ? 0.3 : -1, 1);
  g.translate(-30, 100);
  shape(kit, g, [[24, -76], [26, -104], [38, -126], [58, -126], [76, -112], [90, -100], [98, -92], [90, -85], [68, -80], [46, -74], [32, -66]], { base: C.fur, shade: C.furShade, rim: C.furRim }, 2.8, 430, 8);
  g.beginPath();
  g.ellipse(68, -92, 9, 5, 0.2, 0, Math.PI * 2);
  g.fillStyle = 'rgba(240,150,150,0.35)';
  g.fill();
  const er = 1 + startle * 0.35;
  g.beginPath();
  g.ellipse(62, -108, 4.2 * er, 5.4 * er, 0, 0, Math.PI * 2);
  g.fillStyle = C.nose;
  g.fill();
  g.fillStyle = '#fff6ea';
  g.fillRect(62 + 0.8 * er, -111 * 1 - 0.5 * er, 2.2, 2.2);
  g.beginPath();
  g.arc(98, -93, 5.6, 0, Math.PI * 2);
  g.fillStyle = C.nose;
  g.fill();
  g.fillStyle = 'rgba(255,240,230,0.6)';
  g.fillRect(99, -96, 2, 2);
  points.nose = kit.at(g, 103, -93);
  kit.ink(g, [[89, -85, 1.2], [84, -82.5, 2], [78, -82, 1]], INK);
  // ear
  shape(kit, g, ellipsePts(32, -128, 8, 7, 0, 8), { base: C.fur, shade: C.furShade }, 2, 431, 3);
  // chef's hat: a band and a puffed crown that trails the head a little
  g.save();
  g.translate(-hatLag * 0.6, hatLag);
  shape(kit, g, [[12, -150], [2, -172], [10, -196], [32, -207], [55, -199], [65, -179], [58, -158]], { base: C.hat, shade: C.hatShade, rim: C.hatRim }, 2.6, 432, 9);
  kit.ink(g, [[26, -156, 1], [24, -176, 1.8], [28, -194, 0.8]], kit.css(C.hatShade, 0.9));
  kit.ink(g, [[44, -158, 1], [46, -180, 1.6], [44, -196, 0.8]], kit.css(C.hatShade, 0.9));
  g.restore();
  shape(kit, g, [[14, -134], [52, -146], [57, -166], [16, -154]], { base: C.hat, shade: C.hatShade, rim: C.hatRim }, 2.6, 433, 5);
  g.restore();
  g.restore();

  // near rail and near arm on top
  g.save();
  g.translate(rear[0], rear[1]);
  g.rotate(pitch);
  g.translate(-162, R);
  kit.ink(g, [[118, -60, 8], [92, -68, 7], [62, -74, 7]], C.woodDark);
  g.restore();
  kit.ink(g, [[26, -62 + bob, 11], [50, -64 + bob * 0.5, 10], [grip[0], grip[1], 9]], C.leg, { taper: false });
  g.beginPath();
  g.arc(grip[0] + 2, grip[1], 7, 0, Math.PI * 2);
  g.fillStyle = C.leg;
  g.fill();
  g.restore();
  return { points, cart };
}

// ---------------------------------------------------------------- pigeon
const WING = {
  glide: [[0, 0], [-20, -30], [-46, -58], [-84, -80], [-92, -72], [-74, -46], [-50, -22], [-22, 2]],
  up: [[0, 0], [-2, -40], [-6, -86], [-24, -118], [-46, -114], [-58, -86], [-50, -52], [-28, -12]],
  mid: [[0, 0], [-26, -20], [-58, -34], [-100, -40], [-104, -30], [-82, -16], [-56, -2], [-24, 8]],
  down: [[0, 0], [-12, 26], [-24, 60], [-38, 94], [-50, 92], [-48, 60], [-38, 28], [-20, 8]],
  half: [[0, 0], [-22, -16], [-50, -22], [-80, -16], [-78, -6], [-56, 2], [-32, 8], [-10, 8]],
  fold: [[-40, 14], [-14, -2], [12, 4], [10, 20], [-20, 26], [-58, 22]],
};
function pigeonWing(kit, g, pose, far, seed) {
  const pts = WING[pose];
  const sh = [4, -60];
  const P = pts.map(([x, y]) => [sh[0] + x + (far ? 8 : 0), sh[1] + y + (far ? -4 : 0)]);
  const { q } = shape(kit, g, P, { base: far ? C.wingShade : C.wing, shade: far ? C.wingTip : C.wingShade, rim: far ? null : C.pgRim }, far ? 0 : 2.2, seed, 8);
  if (pose !== 'fold') {
    // dark primaries at the tip
    const tip = P[3];
    const tip2 = P[4];
    kit.ink(g, [[P[2][0], P[2][1], 5], [tip[0], tip[1], 3], [tip2[0], tip2[1], 1]], C.wingTip);
  } else {
    for (const k of [0.35, 0.6]) {
      kit.ink(g, [[P[0][0] + 10, P[0][1] - 2 + k * 10, 1.2], [P[1][0] + 8, P[1][1] + 6 + k * 8, 2.4], [P[2][0], P[2][1] + 8 + k * 6, 1]], C.wingTip);
    }
  }
  return q;
}
/** o: wing pose, pitch (radians, + = nose down), head [dx, dy], legs ('stand' | 'tuck' | 'reach') */
function pigeon(kit, g, x, y, s, o) {
  const { wing = 'fold', pitch = 0, head = [0, 0], legs = 'stand', h = 0, tail = 0 } = o;
  g.save();
  g.translate(x, y);
  g.scale(s, s);
  groundShadow(g, -10, 2, 1 / (1 + h / 260), 170, `rgba(80,60,120,${0.36 / (1 + h / 160)})`);
  g.translate(0, -h);
  // legs
  if (legs !== 'tuck') {
    for (const [lx, col] of [[6, '#b8665e'], [-4, C.feet]]) {
      const fx = legs === 'reach' ? lx + 12 : lx;
      const fy = legs === 'reach' ? -6 : 0;
      kit.ink(g, [[lx - 2, -26, 4], [fx, fy, 3]], col, { taper: false });
      kit.ink(g, [[fx - 6, fy, 2], [fx + 9, fy, 2]], col, { taper: false });
    }
  }
  g.save();
  g.translate(0, -48);
  g.rotate(pitch);
  g.translate(0, 48);
  if (wing !== 'fold') pigeonWing(kit, g, wing, true, 501);
  // tail
  g.save();
  g.translate(-42, -36);
  g.rotate(tail);
  shape(kit, g, [[0, -6], [-34, -2], [-40, 6], [-2, 6]], { base: C.pgShade, shade: C.wingTip }, 2, 502, 4);
  g.restore();
  shape(kit, g, [[-48, -42], [-30, -64], [0, -72], [22, -66], [30, -50], [22, -30], [0, -22], [-26, -24], [-46, -32]], { base: C.pg, shade: C.pgShade, rim: C.pgRim }, 2.6, 503, 10);
  // neck and head
  g.save();
  g.translate(20 + head[0], -62 + head[1]);
  g.rotate(head[2] || 0);
  g.translate(-20, 62);
  shape(kit, g, [[14, -60], [20, -80], [28, -97], [42, -94], [46, -82], [36, -62]], { base: C.pgHead, shade: C.pgShade, rim: C.pgRim }, 2.4, 504, 6);
  shape(kit, g, [[16, -62], [22, -76], [38, -74], [34, -60]], { base: C.neck, shade: C.neck2 }, 0, 505, 5);
  shape(kit, g, [[42, -88], [56, -83], [43, -80]], { base: C.beak, shade: null }, 1.2, 506, 2);
  g.beginPath();
  g.ellipse(44, -88, 3.5, 2.2, 0, 0, Math.PI * 2);
  g.fillStyle = C.cere;
  g.fill();
  g.beginPath();
  g.arc(35, -88, 3.4, 0, Math.PI * 2);
  g.fillStyle = C.eye;
  g.fill();
  g.beginPath();
  g.arc(35.6, -88, 1.6, 0, Math.PI * 2);
  g.fillStyle = INK;
  g.fill();
  g.restore();
  pigeonWing(kit, g, wing, false, 507);
  if (legs === 'tuck') kit.ink(g, [[-6, -26, 4], [-18, -22, 3]], C.feet, { taper: false });
  g.restore();
  g.restore();
}

// ---------------------------------------------------------------- the street, shared by shots 2 and 3
const KERB = 640;
function street(kit) {
  const sky = kit.layer(1920, KERB + 40);
  const sun = [1760, 470];
  paintSky(kit, sky.g, 1920, KERB + 40, sun, 4);
  paintClouds(kit, sky.g, [[560, 120, 620, 90], [1380, 200, 480, 70]], sun);
  // the sky sits far behind the softened street: soften it more
  const soft = kit.layer(1920, KERB + 40);
  soft.g.filter = 'blur(4px)';
  soft.g.drawImage(sky.canvas, 0, 0);
  soft.g.filter = 'none';
  sky.g.drawImage(soft.canvas, 0, 0);
  // the far side of the street, painted then softened: the lens is on the baker
  const raw = kit.layer(2700, KERB + 40);
  const rg = raw.g;
  rg.save();
  rg.translate(0, KERB);
  rg.scale(1.9, 1.9);
  paintHouses(kit, rg, -20, 2700 / 1.9 + 20, 0, 61);
  rg.restore();
  const rd = kit.rng(62);
  for (let x = 60; x < 2700; x += 240 + rd() * 260) {
    const w = 60 + rd() * 26;
    rg.fillStyle = kit.css(kit.jit('#4a3e52', rd, 14));
    rg.fillRect(x, KERB - 120, w, 120);
    rg.fillStyle = 'rgba(255,214,160,0.3)';
    rg.fillRect(x + w - 4, KERB - 120, 4, 120);
  }
  // brushwork over the walls so they read as paint, not flat panels
  const rm = kit.rng(63);
  rg.save();
  rg.globalCompositeOperation = 'source-atop';
  kit.mottle(rg, 0, 0, 2700, KERB, (x, y) => kit.mix('#7c7896', '#c9a49a', kit.clamp(1 - y / KERB) * 0.4 + 0.3 * rm()), { n: 900, size: 60, alpha: 0.16, r: rm, angle: Math.PI / 2 });
  // the low sun rakes the upper walls with warm light
  const wl = rg.createLinearGradient(0, 0, 0, KERB);
  wl.addColorStop(0, 'rgba(255,206,150,0.32)');
  wl.addColorStop(0.6, 'rgba(255,206,150,0.05)');
  wl.addColorStop(1, 'rgba(70,60,120,0.18)');
  rg.fillStyle = wl;
  rg.fillRect(0, 0, 2700, KERB);
  rg.restore();
  const facade = kit.layer(2700, KERB + 40);
  facade.g.filter = 'blur(3px)';
  facade.g.drawImage(raw.canvas, 0, 0);
  facade.g.filter = 'none';
  mistBand(facade.g, 260, KERB, 0.4);
  kit.tooth(facade.g, 2700, KERB + 40);
  const ground = kit.layer(2900, 1080);
  paintCobbles(kit, ground.g, KERB + 12, 1080, 2900, 5);
  // the kerb
  const gg = ground.g;
  gg.fillStyle = '#6a6682';
  gg.fillRect(0, KERB, 2900, 16);
  gg.fillStyle = 'rgba(255,222,180,0.5)';
  gg.fillRect(0, KERB, 2900, 3);
  // light lying along the street from the low sun
  const lg = gg.createLinearGradient(0, KERB, 0, 1080);
  lg.addColorStop(0, 'rgba(255,214,170,0.22)');
  lg.addColorStop(1, 'rgba(60,50,100,0.16)');
  gg.fillStyle = lg;
  gg.fillRect(0, KERB, 2900, 1080 - KERB);
  kit.tooth(gg, 2900, 1080);
  const mist = mistLayer(kit, 3200, 420, 71, { n: 36, alpha: 0.2 });
  return { sky, facade, ground, mist, sun };
}
/** Warm morning light from the right, over the finished street. */
function sunWash(g, sun) {
  g.save();
  g.globalCompositeOperation = 'screen';
  const grd = g.createRadialGradient(sun[0], sun[1], 30, sun[0], sun[1], 1500);
  grd.addColorStop(0, 'rgba(255,210,150,0.38)');
  grd.addColorStop(0.45, 'rgba(255,196,140,0.12)');
  grd.addColorStop(1, 'rgba(255,190,140,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, 1920, 1080);
  g.restore();
}

/** Rows of cobbles rise as the wheel climbs one stone, on twos. */
const climb = (tau) => (tau < -1e-6 ? 0 : [0, 11, 12, 7, 2][Math.round(tau * 12)] ?? 0);
const hop = (tau) => (tau < -1e-6 ? 0 : [0, -4, -6, -2, 2, -1, 0.5][Math.round(tau * 12)] ?? 0);

function steps(kit, t0, t1, every = 0.5, prefix = 'step') {
  let k = 0;
  for (let t = Math.ceil(t0 / every - 1e-6) * every; t < t1 - 1e-6; t += every) {
    if (t > 0.01) kit.cue(`${prefix}${k++}`, t, 'step', { minor: true });
  }
}

export default {
  // ------------------------------------------------------------ 1. the misty town at dawn
  town(kit) {
    const plate = kit.layer(1920, 1080);
    const g0 = plate.g;
    const sun = [1380, 600];
    paintSky(kit, g0, 1920, 720, sun, 3);
    paintClouds(kit, g0, [[420, 210, 760, 110], [1180, 120, 520, 80], [1720, 330, 520, 90]], sun);
    paintFarBank(kit, g0, 1920, 712, 7);
    mistBand(g0, 560, 740, 0.55);
    // the far row, painted on its own layer and softened once: a filter left on while painting
    // blurs every single stroke, which costs seconds
    const far = kit.layer(1920, 400);
    far.g.translate(0, 300);
    far.g.scale(0.6, 0.6);
    paintHouses(kit, far.g, -60, 3300, 0, 41);
    g0.filter = 'blur(1.2px)';
    g0.drawImage(far.canvas, 0, 448);
    g0.filter = 'none';
    mistBand(g0, 520, 775, 0.5);
    paintHouses(kit, g0, -30, 1960, 820, 23);
    mistBand(g0, 600, 830, 0.32);
    paintCobbles(kit, g0, 820, 1080, 1920, 5);
    const lg = g0.createLinearGradient(0, 820, 0, 1080);
    lg.addColorStop(0, 'rgba(255,214,170,0.18)');
    lg.addColorStop(1, 'rgba(60,50,100,0.14)');
    g0.fillStyle = lg;
    g0.fillRect(0, 820, 1920, 260);
    kit.tooth(g0, 1920, 1080);
    const smokes = [
      ...chimneys(kit, -60, 3300, 0, 41).map(([x, y]) => [x * 0.6, 748 + y * 0.6, 0.6]),
      ...chimneys(kit, -30, 1960, 820, 23).map(([x, y]) => [x, y, 1]),
    ].filter(([x]) => x > -40 && x < 1960);
    const mist = mistLayer(kit, 2400, 360, 72, { n: 30, alpha: 0.24 });
    const S = 0.45;
    const LANE = 960;
    steps(kit, 0, 4);
    kit.cue('roll', 0, 'roll', { minor: true, len: 4, level: 0.35 });
    return (g, t) => {
      const tw = kit.twos(t);
      const k = kit.smooth(t / 4);
      const z = 1 + 0.035 * k;
      g.save();
      g.translate(960, 820);
      g.scale(z, z);
      g.translate(-960, -820);
      g.drawImage(plate.canvas, 0, 0);
      // the edge of the sky warms from grey-blue to pale gold
      g.save();
      g.globalCompositeOperation = 'screen';
      const glow = g.createRadialGradient(sun[0], sun[1], 20, sun[0], sun[1], 1100);
      glow.addColorStop(0, `rgba(255,214,150,${0.12 + 0.36 * k})`);
      glow.addColorStop(0.5, `rgba(255,196,140,${0.05 + 0.16 * k})`);
      glow.addColorStop(1, 'rgba(255,190,140,0)');
      g.fillStyle = glow;
      g.fillRect(0, 0, 1920, 1080);
      g.restore();
      g.fillStyle = `rgba(70,80,130,${0.2 * (1 - k)})`;
      g.fillRect(0, 0, 1920, 1080);
      // chimney smoke, drawn on twos, leaning with a light breeze
      for (const [i, [cx, cy, sc]] of smokes.entries()) {
        const r = kit.rng(900 + i * 13);
        const ph = r();
        for (let p = 0; p < 8; p++) {
          const a = (tw * 0.3 + p / 8 + ph) % 1;
          const al = 0.34 * (1 - a) * Math.min(1, a * 6);
          const px = cx + sc * (a * a * 150 + 10 * Math.sin(a * 6 + ph * 6));
          const py = cy - sc * a * 230;
          const rad = sc * (9 + a * 40);
          const grd = g.createRadialGradient(px - rad * 0.2, py - rad * 0.2, 1, px, py, rad);
          grd.addColorStop(0, `rgba(240,232,240,${al})`);
          grd.addColorStop(0.6, `rgba(214,204,224,${al * 0.7})`);
          grd.addColorStop(1, 'rgba(200,190,215,0)');
          g.fillStyle = grd;
          g.beginPath();
          g.arc(px, py, rad, 0, Math.PI * 2);
          g.fill();
        }
      }
      g.globalAlpha = 0.85;
      g.drawImage(mist.canvas, -200 + t * 14, 470);
      g.globalAlpha = 1;
      const D = 100 * tw;
      const x = 560 + S * D;
      const b = baker(kit, g, x, LANE, S, { D });
      kit.actor('刺猬', { x, y: LANE, s: S, facing: 'right', points: b.points });
      kit.prop('推车', { x: x + (224 + CDX) * S, y: LANE, s: S, points: b.cart });
      g.restore();
    };
  },

  // ------------------------------------------------------------ 2. tracking alongside; the stone, the bun
  side(kit, scene) {
    const { sky, facade, ground, mist, sun } = street(kit);
    const S = 1.7;
    const LANE = 890;
    const X0 = 400;
    const V = 100 * S; // screen px a second
    const bumpT = scene.events.bump;
    const landT = scene.events.land;
    const REAR = 1.25; // seconds until the rear wheel meets the same stone (wheelbase 125 / speed 100)
    // the raised stone, in ground-plate coordinates: the front wheel reaches it at bumpT
    const stoneX = X0 + (287 + CDX) * S + V * bumpT + 24 * S;
    const gg = ground.g;
    shape(kit, gg, ellipsePts(stoneX, LANE - 8, 24, 13, -0.05, 10, 0.1, kit.rng(77)), { base: '#958aa2', shade: '#5e566e', rim: '#d8c4c0' }, 2.4, 78, 6);
    gg.fillStyle = 'rgba(60,40,90,0.35)';
    gg.beginPath();
    gg.ellipse(stoneX - 12, LANE + 3, 28, 6, 0, 0, Math.PI * 2);
    gg.fill();
    // the bun's flight: a parabola under gravity. The jolt can't throw it backwards out of the cart
    // (it travels with the cart), so it tips over the near rim and comes down nearer the camera; its
    // size grows with perspective, from the horizon this shot declares. Then one small bounce and a roll.
    const HZ = scene.horizon;
    const NEAR = 940;
    const scaleAt = (lane) => (S * (lane - HZ)) / (LANE - HZ);
    const G = 6000;
    const T = landT - bumpT;
    const h0 = (-PILE_BUN[1] - PILE_BUN[2]) * S;
    const vh = (0.5 * G * T * T - h0) / T;
    const vx = 0.55 * V;
    const xw0 = X0 + (PILE_BUN[0] + CDX) * S + V * bumpT;
    const vb = 0.12 * (G * T - vh);
    const Tb = (2 * vb) / G;
    steps(kit, 0, 5);
    kit.cue('roll', 0, 'roll', { minor: true, len: 5, level: 1 });
    kit.cue('rear', bumpT + REAR, 'clunk', { minor: true });
    kit.cue('bounce', landT + Tb, 'bounce', { minor: true });
    return (g, t) => {
      const camX = V * t;
      g.drawImage(sky.canvas, 0, 0);
      g.drawImage(facade.canvas, -camX * 0.8, 0);
      g.globalAlpha = 0.7;
      g.drawImage(mist.canvas, -camX * 0.85 - t * 10, 260);
      g.globalAlpha = 1;
      g.drawImage(ground.canvas, -camX, 0);
      sunWash(g, sun);
      const tw = kit.twos(t);
      const tau = tw - bumpT;
      const D = 100 * tw;
      const jolt = hop(tau) + hop(tau - REAR) * 0.5;
      const b = baker(kit, g, X0, LANE, S, {
        D,
        liftF: climb(tau),
        liftR: climb(tau - REAR),
        hop: jolt,
        pile: hop(tau - 1 / 12) * 1.6 + hop(tau - REAR - 1 / 12) * 0.6,
        bodyJolt: hop(tau - 1 / 12) * 0.8,
        hatLag: hop(tau - 2 / 12) * -1.4 + (bobOf(D - 8) - bobOf(D)) * 0.8,
        startle: tau > 0.05 && tau < 0.75 ? 1 : 0,
        withBun: t < bumpT,
      });
      kit.actor('刺猬', { x: X0 + camX, y: LANE, s: S, facing: 'right', points: b.points });
      kit.prop('推车', { x: X0 + camX + (224 + CDX) * S, y: LANE, s: S, points: b.cart });
      if (t >= bumpT) {
        let xw, h, lane, sc, rot, sx = 1, sy = 1;
        if (t < landT) {
          const u = t - bumpT;
          xw = xw0 + vx * u;
          h = h0 + vh * u - 0.5 * G * u * u;
          lane = LANE + (NEAR - LANE) * (u / T);
          sc = scaleAt(lane);
          rot = 0.1 - 7 * u;
        } else {
          const u = t - landT;
          const roll = 0.6 * vx * 0.3 * (1 - Math.exp(-u / 0.3));
          xw = xw0 + vx * T + roll;
          h = u < Tb ? vb * u - 0.5 * G * u * u : 0;
          lane = NEAR;
          sc = scaleAt(NEAR);
          rot = 0.1 - 7 * T + roll / (PILE_BUN[2] * sc);
          if (u < 0.07) {
            sx = 1.14;
            sy = 0.82;
          }
        }
        const xs = xw - camX;
        groundShadow(g, xs - 6, lane + 2, sc / (1 + h / 200), 70, `rgba(70,50,110,${0.4 / (1 + h / 120)})`);
        const rad = PILE_BUN[2] * sc;
        bunAt(kit, g, xs, lane - h - rad * 0.86 * sy, rad, rot, 407, sx, sy);
        // the bun flies on its own: report where it is over the ground and how high
        kit.prop('面包', { x: xw, y: lane, s: sc, air: h, ballistic: true, from: '推车' });
      }
    };
  },

  // ------------------------------------------------------------ 3. the pigeon, the look back
  pigeon(kit, scene) {
    const { sky, facade, ground, mist, sun } = street(kit);
    const S = 1.15;
    const LANE = 780;
    const NEAR = 880; // the lane nearer the camera, where the bun came to rest
    const landT = scene.events.land;
    const pecks = scene.events.peck;
    const BX = 640; // the bun
    const BR = 25;
    const PS = 1.25; // the pigeon's scale
    const PX = BX - BR - 45 * PS + 3; // the pigeon lands beside it, facing it: a peck reaches the bun's edge
    const OFF = 760; // where along the street this shot looks
    // where the hedgehog is: walking, a stop to look back, then on again
    const dist = (tw) => 100 * (Math.min(tw, 1.0) + Math.max(0, tw - 2.5));
    steps(kit, 0, 1.01);
    steps(kit, 2.51, 4, 0.5, 'again');
    kit.cue('roll', 0, 'roll', { minor: true, len: 0.9, level: 0.6 });
    kit.cue('roll2', 2.5, 'roll', { minor: true, len: 1.5, level: 0.6 });
    for (let k = 0; k < 4; k++) kit.cue(`flap${k}`, 0.5 + k * (2 / 12) + 1 / 12, 'flap', { minor: true });
    const crumbs = Array.from({ length: 7 }, (_, i) => {
      const r = kit.rng(600 + i);
      return [BX - BR - 22 + r() * 40, NEAR - 2 + r() * 10, 2 + r() * 2.5, Math.floor(i / 4)];
    });
    return (g, t) => {
      const tw = kit.twos(t);
      g.drawImage(sky.canvas, 0, 0);
      g.drawImage(facade.canvas, -OFF * 0.8, 0);
      g.globalAlpha = 0.7;
      g.drawImage(mist.canvas, -OFF * 0.85 - 50 - t * 10, 260);
      g.globalAlpha = 1;
      g.drawImage(ground.canvas, -OFF, 0);
      sunWash(g, sun);

      // the baker, farther up the street
      const D = dist(tw);
      const x = 900 + S * D;
      const look = tw < 1.25 ? 0 : tw < 1.4 ? 1 : tw < 2.2 ? 2 : tw < 2.3 ? 1 : 0;
      const b = baker(kit, g, x, LANE, S, { D, look, withBun: false, hatLag: (bobOf(D - 8) - bobOf(D)) * 0.8 + (look === 1 ? 2 : 0) });
      kit.actor('刺猬', { x, y: LANE, s: S, facing: 'right', points: b.points });
      kit.prop('推车', { x: x + (224 + CDX) * S, y: LANE, s: S, points: b.cart });

      // the bun on the road, and crumbs after each peck
      groundShadow(g, BX - 8, NEAR + 2, BR / 20, 70, 'rgba(70,50,110,0.4)');
      bunAt(kit, g, BX, NEAR - BR * 0.86, BR, 0.1 - 7 * 0.55 + 0.6, 407);
      g.fillStyle = C.breadRim;
      const done = pecks.filter((p) => tw >= p).length;
      for (const [cx, cy, cr, k] of crumbs) {
        if (k >= done) continue;
        g.beginPath();
        g.arc(cx, cy, cr, 0, Math.PI * 2);
        g.fill();
      }

      // the pigeon: a descending glide, a flare with a few wingbeats, touchdown, wings folding
      let gx, h, wing, pitch, legs, tail = 0;
      let head = [0, 0, 0];
      if (tw < landT) {
        const u = tw / landT;
        gx = -260 + (PX + 260) * (1 - (1 - u) * (1 - u));
        h = 640 * Math.pow(1 - u, 1.6);
        if (u < 0.5) {
          wing = 'glide';
          pitch = 0.18;
          legs = 'tuck';
        } else {
          wing = ['down', 'mid', 'up', 'mid'][Math.round((tw - 0.5) * 12) % 4];
          pitch = -0.15 - 0.5 * (u - 0.5);
          legs = u > 0.75 ? 'reach' : 'tuck';
        }
      } else {
        gx = PX;
        h = 0;
        const k = Math.round((tw - landT) * 12);
        wing = k === 0 ? 'up' : k === 1 ? 'half' : 'fold';
        pitch = k === 0 ? -0.3 : k === 1 ? -0.12 : 0;
        legs = 'stand';
        tail = k === 1 ? -0.25 : k === 2 ? 0.15 : 0;
        for (const p of pecks) {
          const d = Math.round((tw - p) * 12);
          if (d === -1) head = [-3, -2, -0.15];
          if (d === 0 || d === 1) {
            head = [2, 2, 1.2];
            pitch = 0.35;
          }
          if (d === 2) {
            head = [1, 1, 0.55];
            pitch = 0.15;
          }
        }
      }
      pigeon(kit, g, gx, NEAR, PS, { wing, pitch, head, legs, h: h / PS, tail });
      kit.actor('鸽子', { x: gx, y: NEAR, s: PS, facing: 'right' });
    };
  },
};
