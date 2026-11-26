// Narrative runtime: loads the film's shots, then draws any frame from its time alone.
import * as engine from './engine.js';

const film = await (await fetch('/film/film.resolved.json')).json();
const timeline = film.timeline;
const shots = film.customScenes ? (await import('/film/scenes.js')).default : {};
// Shots report each character every frame: its position on the ground plane (before any camera
// move), its scale, and which way it faces. The checks use this to catch impossible motion.
let frameActors = [];
// Props report the same way (a cart, a thrown bun); they have no facing. Either may add named
// points in drawing coordinates (a hand, a handle) for the contacts film.json declares, and things
// in the air report how high above their ground point they are.
const kit = {
  ...engine,
  look: film.look || {},
  actor: (name, info) => frameActors.push({ name, ...info }),
  prop: (name, info) => frameActors.push({ name, prop: true, ...info }),
  // a point drawn at (x, y) under the context's current transform, in frame pixels: report contact
  // points with this, so both ends are measured the same way whatever each was drawn under
  at: (g, x, y) => {
    const m = g.getTransform();
    return [Math.round((m.a * x + m.c * y + m.e) * 10) / 10, Math.round((m.b * x + m.d * y + m.f) * 10) / 10];
  },
};
engine.initGrain();

const g = document.getElementById('frame').getContext('2d');
// Shots may report the moments that want a sound (a footstep, a door), in shot time; they reach the
// pipeline as film-time events, next to the ones declared in film.json.
const events = [];
const scenes = [];
for (const [i, scene] of film.scenes.entries()) {
  const build = shots[scene.type];
  if (!build) throw new Error(`unknown shot type "${scene.type}" in scene "${scene.id}"`);
  const span = timeline.scenes[i];
  const shotKit = { ...kit, cue: (name, at, kind, extra = {}) => events.push({ name: `${scene.id}.${name}`, t: span.start + at, kind, ...extra }) };
  scenes.push({ scene, draw: await build(shotKit, scene), start: span.start, end: span.end });
}

function seek(t) {
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1;
  g.filter = 'none';
  g.globalCompositeOperation = 'source-over';
  g.fillStyle = '#000';
  g.fillRect(0, 0, engine.W, engine.H);
  const last = scenes.length - 1;
  const i = scenes.findIndex((s, k) => t >= s.start && (t < s.end || k === last));
  if (i < 0) return;
  const s = scenes[i];
  frameActors = [];
  const lt = t - s.start;
  const dur = s.end - s.start;
  g.save();
  s.draw(g, lt, dur);
  g.restore();
  engine.finish(g, t, film.finish || {});
  // fades are part of the cut list, not of the shot
  const fadeIn = s.scene.fadeIn ?? 0;
  const fadeOut = s.scene.fadeOut ?? 0;
  const dark = Math.max(fadeIn ? 1 - engine.clamp(lt / fadeIn) : 0, fadeOut ? engine.clamp((lt - (dur - fadeOut)) / fadeOut) : 0);
  if (dark > 0) {
    g.fillStyle = `rgba(0,0,0,${dark})`;
    g.fillRect(0, 0, engine.W, engine.H);
  }
}

// Where everyone is at time t, and whether the shot covers the whole frame, without finishing it:
// the checks call this a dozen times a second of film. The shot is drawn twice, once over white
// and once over black. Where it painted the frame the two agree; where they differ, the background
// shows through: that part of the frame was never painted (a translucent wash over it is not paint).
function probe(t) {
  const last = scenes.length - 1;
  const i = scenes.findIndex((s, k) => t >= s.start && (t < s.end || k === last));
  if (i < 0) return { actors: [], bare: {} };
  const s = scenes[i];
  const strips = [[engine.W - 1, 0, 1, engine.H], [0, 0, 1, engine.H], [0, 0, engine.W, 1], [0, engine.H - 1, engine.W, 1]];
  const drawOver = (bg) => {
    frameActors = [];
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalAlpha = 1;
    g.filter = 'none';
    g.globalCompositeOperation = 'source-over';
    g.fillStyle = bg;
    g.fillRect(0, 0, engine.W, engine.H);
    g.save();
    s.draw(g, t - s.start, s.end - s.start);
    g.restore();
    return strips.map(([x, y, w, h]) => g.getImageData(x, y, w, h).data);
  };
  const white = drawOver('#fff');
  const black = drawOver('#000');
  const share = (a, b) => {
    let n = 0;
    for (let k = 0; k < a.length; k += 4) if (Math.abs(a[k] - b[k]) + Math.abs(a[k + 1] - b[k + 1]) + Math.abs(a[k + 2] - b[k + 2]) > 60) n++;
    return n / (a.length / 4);
  };
  const [r, l, top, bottom] = white.map((w, k) => share(w, black[k]));
  return { actors: JSON.parse(JSON.stringify(frameActors)), bare: { 右: r, 左: l, 上: top, 下: bottom } };
}

window.DF = { duration: timeline.duration, fps: timeline.fps, seek, probe, events, get actors() { return frameActors; } };
seek(Number(new URLSearchParams(location.search).get('t') || 0));
document.documentElement.dataset.ready = '1';
