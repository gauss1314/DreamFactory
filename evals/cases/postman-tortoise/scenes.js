// "The postman after the rain": the tortoise and the three shots.
// Sky, clouds, water, glints and cel shapes come from the engine's painters; this file only holds
// what is particular to this film: the tortoise, the canal town, the cobbles, the rain, the mailbox, the lamp.
import { path, cel, line, groundShadow, paintSky, paintClouds, paintRiver, glitter, paintHouses, paintWall, paintArchBridge, paintCobbles, paintPuddle, ripples, rain, lampPost } from '/runtime/painters.js';

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
  const points = {};
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
  points.beak = kit.at(g, 38, 4);
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
    // where the beak grips it, and its leading edge
    points.letter = kit.at(g, -2, 2);
    points.letterMid = kit.at(g, 30, 2);
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
  return points;
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
  // the opening is a little taller than the envelope, at the height the beak carries it
  g.fillRect(-54, -182, 8, 48);
  g.fillStyle = '#2a1e24';
  g.fillRect(-52, -178, 4, 40);
  const slot = kit.at(g, -50, -158);
  // a painted envelope on the side instead of words
  kit.ink(g, [[-20, -170, 1.6], [0, -156, 1.8], [20, -170, 1.6]], '#f2e6cc');
  g.strokeStyle = '#f2e6cc';
  g.lineWidth = 2;
  g.strokeRect(-22, -172, 44, 28);
  g.restore();
  return { slot };
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
    paintHouses(kit, g, -40, 1960, 560, 63, { reflect: 0.6 });
    paintArchBridge(kit, g, 620, 1300, 520, 640, 64);
    // quay wall and the cobbled path
    g.fillStyle = kit.css('#4a4660');
    g.fillRect(0, 822, 1920, 30);
    g.fillStyle = 'rgba(255,214,170,0.3)';
    g.fillRect(0, 822, 1920, 3);
    paintCobbles(kit, g, 852, 1080, 1920, 65);
    paintPuddle(kit, g, 1220, 1010, 170, 26, 66);
    paintPuddle(kit, g, 420, 930, 110, 16, 67);
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
      const points = tortoise(kit, g2, w.x, y, 0.42, { ...w, letter: true });
      kit.actor('乌龟', { x: w.x, y, s: 0.42, facing: 'right', points });
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
    paintHouses(kit, g, -40, 1960, 420, 82, { haze: 0.18 });
    paintWall(kit, g, 400, 720, 83);
    paintCobbles(kit, g, 720, 1080, 1920, 84);
    paintPuddle(kit, g, 560, 1000, 210, 30, 85);
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
      const points = tortoise(kit, g2, w.x, ground, s, { ...w, neck, push, letter: d < drop });
      // the box is drawn after the tortoise, so the part of the letter inside the slot is hidden
      const box = mailbox(kit, g2, 1330, ground, s);
      kit.actor('乌龟', { x: w.x, y: ground, s, facing: 'right', points });
      kit.prop('邮筒', { x: 1330, y: ground, s, points: box });
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
    paintHouses(kit, g, -40, 1960, 460, 92, { haze: 0.18 });
    paintWall(kit, g, 440, 700, 93);
    paintCobbles(kit, g, 700, 1080, 1920, 94);
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
