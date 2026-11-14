// Data-story runtime. Everything on screen is a pure function of time: seek(t) sets every style
// from t alone, with no clocks, no CSS animations and no state carried between frames.
const film = await (await fetch('/film/film.resolved.json')).json();
const timeline = film.timeline;
const stage = document.getElementById('stage');
for (const [k, v] of Object.entries(film.theme || {})) stage.style.setProperty(`--${k}`, v);
document.documentElement.lang = film.lang || 'zh';

const clamp = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => 1 - (1 - clamp(x)) ** 3;
const fmt = (n) =>
  typeof n === 'number' ? (Number.isInteger(n) ? n : Math.round(n * 10) / 10).toLocaleString('en-US') : String(n ?? '');

function h(tag, cls, text, parent) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text != null && text !== '') el.textContent = text;
  if (parent) parent.appendChild(el);
  return el;
}

function rise(el, p, dy = 28) {
  el.style.opacity = String(p);
  el.style.transform = dy ? `translateY(${(1 - p) * dy}px)` : '';
}

/** Create an SVG element with attributes. */
function svg(tag, attrs, parent) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, String(v));
  if (parent) parent.appendChild(el);
  return el;
}

/** A number with its unit. A unit in Latin letters gets a space; "233works" reads as one word. */
const withUnit = (text, unit) => (unit ? text + (/^[A-Za-z]/.test(unit) ? ' ' : '') + unit : text);

function chartHead(scene, root) {
  h('h2', 'chart-title', scene.title, root);
  if (scene.sub) h('div', 'chart-sub', scene.sub, root);
}

// Each builder creates a scene's DOM once and returns update(localTime, lines).
const builders = {
  title(scene, root) {
    root.classList.add('center');
    const parts = [
      scene.kicker && h('div', 'kicker', scene.kicker, root),
      h('h1', 'headline', scene.headline, root),
      scene.sub && h('p', 'sub', scene.sub, root),
    ].filter(Boolean);
    return (lt) => parts.forEach((el, i) => rise(el, ease((lt - 0.1 - i * 0.25) / 0.6)));
  },

  outro(scene, root) {
    root.classList.add('outro');
    return builders.title(scene, root);
  },

  bignumber(scene, root) {
    root.classList.add('center');
    const label = h('div', 'bn-label', scene.label, root);
    const row = h('div', 'bn-row', null, root);
    const value = h('span', 'bn-value', '', row);
    if (scene.unit) h('span', 'bn-unit', scene.unit, row);
    const note = scene.note ? h('div', 'bn-note', scene.note, root) : null;
    const countable = Number.isInteger(scene.value);
    return (lt) => {
      rise(label, ease((lt - 0.1) / 0.5));
      row.style.opacity = String(ease((lt - 0.3) / 0.4));
      const p = clamp((lt - 0.35) / 1.1);
      if (countable && p < 1) {
        // Intermediate count-up values are not facts; the checks skip them by role.
        value.textContent = fmt(Math.round(scene.value * ease(p)));
        value.dataset.dfRole = 'animating';
      } else {
        value.textContent = fmt(scene.value);
        delete value.dataset.dfRole;
      }
      if (note) rise(note, ease((lt - 1.5) / 0.6));
    };
  },

  bars(scene, root) {
    chartHead(scene, root);
    const list = h('div', 'rows', null, root);
    const items = scene.series || [];
    const max = Math.max(1, ...items.map((it) => it.value));
    const total = items.reduce((a, it) => a + it.value, 0);
    const rows = items.map((it) => {
      const row = h('div', `row${it.label === scene.highlight ? ' hl' : ''}`, null, list);
      const label = h('div', 'row-label', it.label, row);
      label.dataset.dfBox = '';
      const track = h('div', 'row-track', null, row);
      const fill = h('div', 'bar-fill', null, track);
      fill.dataset.dfValue = String(it.value);
      const value = h('div', 'bar-value', withUnit(fmt(it.value), scene.unit), track);
      if (scene.showShare) h('span', 'bar-share', `${Math.round((100 * it.value) / total)}%`, value);
      return { label, fill, value, frac: it.value / max };
    });
    return (lt) =>
      rows.forEach((r, i) => {
        const at = 0.4 + i * 0.14;
        rise(r.label, ease((lt - at) / 0.4), 0);
        r.fill.style.width = `${78 * r.frac * ease((lt - at - 0.1) / 0.7)}%`;
        r.value.style.opacity = String(ease((lt - at - 0.5) / 0.4));
      });
  },

  ranges(scene, root) {
    root.classList.add('ranges');
    chartHead(scene, root);
    const list = h('div', 'rows', null, root);
    const items = scene.series || [];
    const sc = scene.scale;
    if (sc != null && !(Array.isArray(sc) && sc.length === 2 && sc.every((v) => typeof v === 'number' && v > 0) && sc[0] < sc[1])) {
      throw new Error(`scene "${scene.id}": scale must be [low, high], two positive numbers with low first; leave it out for an automatic range`);
    }
    const lo = scene.scale?.[0] ?? 10 ** Math.floor(Math.log10(Math.min(...items.map((it) => it.low))));
    const hi = scene.scale?.[1] ?? 10 ** Math.ceil(Math.log10(Math.max(...items.map((it) => it.high))));
    const pos = (v) => (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo));
    const rows = items.map((it) => {
      const row = h('div', `row${it.label === scene.highlight ? ' hl' : ''}`, null, list);
      const label = h('div', 'row-label', it.label, row);
      label.dataset.dfBox = '';
      const track = h('div', 'row-track', null, row);
      const pill = h('div', 'range-pill', null, track);
      pill.style.left = `${100 * pos(it.low)}%`;
      const value = h('div', 'range-value', `${fmt(it.low)}–${fmt(it.high)}${scene.unit ? ` ${scene.unit}` : ''}`, row);
      value.dataset.dfBox = '';
      return { label, pill, value, span: 100 * (pos(it.high) - pos(it.low)) };
    });
    const axis = h('div', 'axis', null, root);
    const ticks = h('div', 'axis-ticks', null, axis);
    ticks.dataset.dfRole = 'tick';
    for (let v = lo; v <= hi * 1.0001; v *= 10) h('div', 'tick', fmt(Math.round(v)), ticks).style.left = `${100 * pos(v)}%`;
    return (lt) => {
      rows.forEach((r, i) => {
        const at = 0.4 + i * 0.3;
        rise(r.label, ease((lt - at) / 0.4), 0);
        r.pill.style.width = `${r.span * ease((lt - at - 0.1) / 0.7)}%`;
        r.pill.style.opacity = String(ease((lt - at - 0.1) / 0.2));
        r.value.style.opacity = String(ease((lt - at - 0.5) / 0.4));
      });
      axis.style.opacity = String(ease((lt - 0.2) / 0.5));
    };
  },

  bullets(scene, root) {
    chartHead(scene, root);
    const ul = h('ul', 'bullets', null, root);
    const items = (scene.items || []).map((text) => h('li', '', text, ul));
    return (lt, lines) =>
      items.forEach((li, i) => {
        // An item appears as its narration line starts, when there is one line per item.
        const at = lines.length === items.length ? lines[i].start - 0.2 : 0.5 + i * 0.9;
        rise(li, ease((lt - at) / 0.5));
      });
  },
};

// What scene code may use. A film can bring its own scenes in scenes.js (see DIRECTOR.md).
const kit = { h, svg, rise, ease, clamp, fmt, chartHead };
if (film.customScenes) {
  const custom = (await import('/film/scenes.js')).default || {};
  for (const [name, build] of Object.entries(custom)) {
    if (builders[name]) throw new Error(`custom scene "${name}" has the name of a built-in scene`);
    builders[name] = build;
  }
}

const scenesEl = document.getElementById('scenes');
const scenes = film.scenes.map((scene, i) => {
  const span = timeline.scenes[i];
  const root = h('section', 'scene', null, scenesEl);
  root.dataset.scene = scene.id;
  root.dataset.dfBox = '';
  const build = builders[scene.type];
  if (!build) throw new Error(`unknown scene type "${scene.type}" in scene "${scene.id}"`);
  const update = build(scene, root, kit);
  if (typeof update !== 'function') throw new Error(`scene type "${scene.type}" must return an update function`);
  const lines = span.lines.map((l) => ({ ...l, start: l.start - span.start, end: l.end - span.start }));
  return { root, update, lines, start: span.start, end: span.end };
});

const subtitle = document.getElementById('subtitle');
const source = document.getElementById('source');
const progress = document.getElementById('progress');
if (film.source) source.textContent = film.source;
const allLines = timeline.scenes.flatMap((s) => s.lines);

function seek(t) {
  const last = scenes.length - 1;
  scenes.forEach((s, i) => {
    const on = t >= s.start && (t < s.end || i === last);
    s.root.style.display = on ? 'flex' : 'none';
    if (!on) return;
    const lt = t - s.start;
    s.root.style.opacity = String(Math.min(ease(lt / 0.35), ease((s.end - t) / 0.3)));
    s.update(lt, s.lines);
  });
  const line = allLines.find((l) => t >= l.start && t < l.end + 0.12);
  subtitle.textContent = line ? line.display : '';
  progress.style.width = `${(100 * t) / timeline.duration}%`;
}

window.DF = { duration: timeline.duration, fps: timeline.fps, seek };
await document.fonts.ready;
seek(Number(new URLSearchParams(location.search).get('t') || 0));
document.documentElement.dataset.ready = '1';
