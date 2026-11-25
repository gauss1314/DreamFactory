// Narrative runtime: loads the film's shots, then draws any frame from its time alone.
import * as engine from './engine.js';

const film = await (await fetch('/film/film.resolved.json')).json();
const timeline = film.timeline;
const shots = film.customScenes ? (await import('/film/scenes.js')).default : {};
// Shots report each character every frame: its position on the ground plane (before any camera
// move), its scale, and which way it faces. The checks use this to catch impossible motion.
let frameActors = [];
const kit = { ...engine, actor: (name, info) => frameActors.push({ name, ...info }) };
engine.initGrain();

const g = document.getElementById('frame').getContext('2d');
const scenes = [];
for (const [i, scene] of film.scenes.entries()) {
  const build = shots[scene.type];
  if (!build) throw new Error(`unknown shot type "${scene.type}" in scene "${scene.id}"`);
  const span = timeline.scenes[i];
  scenes.push({ scene, draw: await build(kit, scene), start: span.start, end: span.end });
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

window.DF = { duration: timeline.duration, fps: timeline.fps, seek, get actors() { return frameActors; } };
seek(Number(new URLSearchParams(location.search).get('t') || 0));
document.documentElement.dataset.ready = '1';
