// Data-story runtime. Everything on screen is a pure function of time: seek(t) sets every style
// from t alone, with no clocks, no CSS animations and no state carried between frames.
// How it should look and move is set out in ../ART.md.
const film = await (await fetch('/film/film.resolved.json')).json();
const timeline = film.timeline;
const stage = document.getElementById('stage');
for (const [k, v] of Object.entries(film.theme || {})) stage.style.setProperty(`--${k}`, v);
document.documentElement.lang = film.lang || 'zh';
const css = getComputedStyle(stage);
const palette = Object.fromEntries(['bg', 'bg2', 'text', 'muted', 'bar', 'track', 'accent', 'accent2'].map((k) => [k, css.getPropertyValue(`--${k}`).trim()]));

// ---------- motion (ART.md section 4) ----------
const clamp = (x) => Math.max(0, Math.min(1, x));
/** Gentle ease-out. Kept for scene code written before the motion rules. */
const ease = (x) => 1 - (1 - clamp(x)) ** 3;
/** Fast in, no overshoot. */
const snap = (x) => 1 - (1 - clamp(x)) ** 4;
/** Fast in, about 3.7% past the mark, back to rest. */
const pop = (x) => {
  const t = clamp(x) - 1;
  return 1 + 2 * t ** 3 + t ** 2;
};

const fmt = (n) =>
  typeof n === 'number' ? (Number.isInteger(n) ? n : Math.round(n * 10) / 10).toLocaleString('en-US') : String(n ?? '');

function h(tag, cls, text, parent) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text != null && text !== '') el.textContent = text;
  if (parent) parent.appendChild(el);
  return el;
}

/** Create an SVG element with attributes. */
function svg(tag, attrs, parent) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, String(v));
  if (parent) parent.appendChild(el);
  return el;
}

/** Wipe an element in from the left while it settles upward, like a line being inked. p: 0..1. */
function reveal(el, p) {
  const q = snap(p);
  el.style.opacity = String(clamp(p * 3));
  el.style.clipPath = q >= 1 ? '' : `inset(-30% ${((1 - q) * 100).toFixed(2)}% -30% -4%)`;
  el.style.transform = q >= 1 ? '' : `translateY(${((1 - q) * 16).toFixed(2)}px)`;
}

/** Older fade-and-rise, kept so existing scene code still runs. */
function rise(el, p, dy = 28) {
  el.style.opacity = String(p);
  el.style.transform = dy ? `translateY(${(1 - p) * dy}px)` : '';
}

/** A number with its unit. A unit in Latin letters gets a space; "233works" reads as one word. */
const withUnit = (text, unit) => (unit ? text + (/^[A-Za-z]/.test(unit) ? ' ' : '') + unit : text);

function chartHead(scene, root) {
  const title = h('h2', 'chart-title', scene.title, root);
  const sub = scene.sub ? h('div', 'chart-sub', scene.sub, root) : null;
  return (lt) => {
    reveal(title, (lt - 0.05) / 0.5);
    if (sub) reveal(sub, (lt - 0.3) / 0.45);
  };
}

function glow(root, left, top) {
  const g = h('div', 'glow', null, root);
  g.style.left = `${left}px`;
  g.style.top = `${top}px`;
}

/** When the hero of a scene should light up: as the narration names it, never before the chart settles. */
function heroTime(lines, label, settled) {
  const line = label ? lines.find((l) => l.display.includes(label)) : null;
  return Math.max(settled, line ? line.start - 0.1 : settled);
}

// Each builder creates a scene's DOM once and returns update(localTime, lines).
const builders = {
  title(scene, root) {
    root.classList.add('center');
    glow(root, -160, -60);
    let kicker = null;
    let rule = null;
    if (scene.kicker) {
      kicker = h('div', 'kicker', null, root);
      rule = h('span', 'rule', null, kicker);
      h('span', '', scene.kicker, kicker);
    }
    const headline = h('h1', 'headline', scene.headline, root);
    const sub = scene.sub ? h('p', 'sub', scene.sub, root) : null;
    return (lt) => {
      if (kicker) {
        rule.style.width = `${56 * snap((lt - 0.05) / 0.35)}px`;
        reveal(kicker.lastChild, (lt - 0.2) / 0.4);
      }
      reveal(headline, (lt - 0.3) / 0.7);
      if (sub) reveal(sub, (lt - 0.95) / 0.5);
    };
  },

  outro(scene, root) {
    root.classList.add('middle');
    glow(root, 410, -40);
    const headline = h('h1', 'headline', scene.headline, root);
    const line = h('div', 'underline', null, root);
    const sub = scene.sub ? h('p', 'sub', scene.sub, root) : null;
    return (lt) => {
      reveal(headline, (lt - 0.15) / 0.7);
      line.style.width = `${180 * snap((lt - 0.75) / 0.45)}px`;
      if (sub) reveal(sub, (lt - 1.0) / 0.5);
    };
  },

  bignumber(scene, root) {
    root.classList.add('center');
    glow(root, -120, -40);
    const label = h('div', 'bn-label', scene.label, root);
    const row = h('div', 'bn-row', null, root);
    const value = h('span', 'bn-value', '', row);
    const unit = scene.unit ? h('span', 'bn-unit', scene.unit, row) : null;
    const line = h('div', 'underline', null, root);
    const note = scene.note ? h('div', 'bn-note', scene.note, root) : null;
    const countable = Number.isInteger(scene.value) && Math.abs(scene.value) >= 10;
    return (lt) => {
      reveal(label, (lt - 0.05) / 0.45);
      const p = clamp((lt - 0.3) / 0.9);
      value.style.opacity = String(clamp((lt - 0.3) * 6));
      if (countable && p < 1) {
        // Intermediate count-up values are not facts; the checks skip them by role.
        value.textContent = fmt(Math.round(scene.value * snap(p)));
        value.dataset.dfRole = 'animating';
      } else {
        value.textContent = fmt(scene.value);
        delete value.dataset.dfRole;
      }
      if (unit) {
        const u = pop((lt - 1.1) / 0.4);
        unit.style.opacity = String(clamp((lt - 1.1) * 6));
        unit.style.transform = `translateY(${((1 - u) * 30).toFixed(2)}px)`;
      }
      line.style.width = `${240 * snap((lt - 1.25) / 0.5)}px`;
      if (note) reveal(note, (lt - 1.5) / 0.5);
    };
  },

  bars(scene, root) {
    glow(root, 900, 60);
    const head = chartHead(scene, root);
    const list = h('div', 'rows', null, root);
    const items = scene.series || [];
    const max = Math.max(1, ...items.map((it) => it.value));
    const total = items.reduce((a, it) => a + it.value, 0);
    const rows = items.map((it) => {
      const hero = it.label === scene.highlight;
      const row = h('div', 'row', null, list);
      const label = h('div', 'row-label', it.label, row);
      label.dataset.dfBox = '';
      const track = h('div', 'row-track', null, row);
      const fill = h('div', 'bar-fill', null, track);
      fill.dataset.dfValue = String(it.value);
      const hot = hero ? h('div', 'bar-hot', null, fill) : null;
      const value = h('div', 'bar-value', withUnit(fmt(it.value), scene.unit), track);
      if (scene.showShare) h('span', 'bar-share', `${Math.round((100 * it.value) / total)}%`, value);
      return { hero, label, fill, hot, value, frac: it.value / max };
    });
    const step = Math.min(0.09, 0.7 / Math.max(1, rows.length));
    const settled = 0.55 + step * rows.length + 0.55;
    let lit = null;
    return (lt, lines) => {
      head(lt);
      lit ??= heroTime(lines, scene.highlight, settled);
      const on = lt >= lit;
      rows.forEach((r, i) => {
        const at = 0.55 + i * step;
        reveal(r.label, (lt - at) / 0.35);
        r.fill.style.width = `${(76 * r.frac * pop((lt - at) / 0.55)).toFixed(3)}%`;
        r.value.style.opacity = String(clamp((lt - at - 0.45) * 5));
        r.label.style.color = on && !r.hero && scene.highlight ? 'var(--muted)' : r.hero && on ? 'var(--accent)' : '';
        r.label.style.fontWeight = r.hero && on ? '700' : '';
        if (r.hot) r.hot.style.width = `${(100 * snap((lt - lit) / 0.4)).toFixed(2)}%`;
      });
    };
  },

  ranges(scene, root) {
    root.classList.add('ranges');
    glow(root, 900, 60);
    const head = chartHead(scene, root);
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
      const hero = it.label === scene.highlight;
      const row = h('div', 'row', null, list);
      const label = h('div', 'row-label', it.label, row);
      label.dataset.dfBox = '';
      const track = h('div', 'row-track', null, row);
      const pill = h('div', 'range-pill', null, track);
      pill.style.left = `${100 * pos(it.low)}%`;
      const value = h('div', 'range-value', `${fmt(it.low)}–${fmt(it.high)}${scene.unit ? ` ${scene.unit}` : ''}`, row);
      value.dataset.dfBox = '';
      return { hero, label, pill, value, span: 100 * (pos(it.high) - pos(it.low)) };
    });
    const axis = h('div', 'axis', null, root);
    const ticks = h('div', 'axis-ticks', null, axis);
    ticks.dataset.dfRole = 'tick';
    for (let v = lo; v <= hi * 1.0001; v *= 10) h('div', 'tick', fmt(Math.round(v)), ticks).style.left = `${100 * pos(v)}%`;
    const settled = 0.5 + 0.25 * rows.length + 0.6;
    let lit = null;
    return (lt, lines) => {
      head(lt);
      lit ??= heroTime(lines, scene.highlight, settled);
      const on = lt >= lit;
      axis.style.opacity = String(snap((lt - 0.3) / 0.4));
      rows.forEach((r, i) => {
        const at = 0.5 + i * 0.25;
        reveal(r.label, (lt - at) / 0.35);
        r.pill.style.width = `${(r.span * pop((lt - at - 0.05) / 0.55)).toFixed(3)}%`;
        r.pill.style.opacity = String(clamp((lt - at) * 8));
        r.pill.style.background = r.hero && on ? 'linear-gradient(90deg, var(--accent2), var(--accent))' : '';
        r.value.style.opacity = String(clamp((lt - at - 0.4) * 5));
        r.label.style.color = on && !r.hero && scene.highlight ? 'var(--muted)' : r.hero && on ? 'var(--accent)' : '';
        r.label.style.fontWeight = r.hero && on ? '700' : '';
      });
    };
  },

  bullets(scene, root) {
    root.classList.add('center');
    glow(root, -120, 80);
    const head = chartHead(scene, root);
    const ul = h('ul', 'bullets', null, root);
    const items = (scene.items || []).map((text) => {
      const li = h('li', '', null, ul);
      const mark = h('span', 'mark', null, li);
      const words = h('span', '', text, li);
      return { li, mark, words };
    });
    return (lt, lines) => {
      head(lt);
      // An item lands as its narration line starts, when there is one line per item.
      const starts = items.map((_, i) => (lines.length === items.length ? Math.max(0.6, lines[i].start - 0.15) : 0.7 + i * 0.9));
      items.forEach((it, i) => {
        const at = starts[i];
        it.mark.style.width = `${48 * snap((lt - at) / 0.3)}px`;
        reveal(it.words, (lt - at - 0.08) / 0.45);
        // Once the next point arrives, this one steps back.
        const next = starts[i + 1];
        it.words.style.color = next != null && lt >= next ? 'var(--muted)' : '';
      });
    };
  },
};

// What scene code may use. A film can bring its own scenes in scenes.js (see DIRECTOR.md and ART.md).
const kit = { h, svg, reveal, rise, pop, snap, ease, clamp, fmt, palette, chartHead: (scene, root) => {
  // Scene code calls chartHead once; the head then draws itself in on the scene's own clock.
  const draw = chartHead(scene, root);
  heads.push({ root, draw });
} };
const heads = [];
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
  const head = heads.find((x) => x.root === root);
  const lines = span.lines.map((l) => ({ ...l, start: l.start - span.start, end: l.end - span.start }));
  return { root, update, head, lines, start: span.start, end: span.end };
});

// ---------- finish: film grain, a new pattern twelve times a second (ART.md section 5) ----------
const GRAIN_TILES = 4;
const grainEl = document.getElementById('grain');
const grainLayers = [];
function grainTile(seed) {
  let a = seed >>> 0;
  const rnd = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  const img = g.createImageData(256, 256);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.round(255 * ((rnd() + rnd() + rnd()) / 3));
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  return c.toDataURL('image/png');
}
for (let k = 0; k < GRAIN_TILES; k++) {
  const url = grainTile(1009 + k * 7919);
  const im = new Image();
  im.src = url;
  await im.decode();
  const layer = h('div', 'fx', null, grainEl);
  layer.style.backgroundImage = `url(${url})`;
  grainLayers.push(layer);
}

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
    // Cuts, not dissolves. The only continuous motion is a slow push-in within the scene.
    const push = 1 + 0.025 * clamp(lt / Math.max(0.1, s.end - s.start));
    s.root.style.transform = `scale(${push.toFixed(5)})`;
    if (s.head) s.head.draw(lt);
    s.update(lt, s.lines);
  });
  const line = allLines.find((l) => t >= l.start && t < l.end + 0.12);
  subtitle.textContent = line ? line.display : '';
  progress.style.width = `${(100 * t) / timeline.duration}%`;
  const g = Math.floor(t * 12 + 1e-6) % GRAIN_TILES;
  grainLayers.forEach((layer, k) => (layer.style.display = k === g ? 'block' : 'none'));
}

window.DF = { duration: timeline.duration, fps: timeline.fps, seek };
await document.fonts.ready;
seek(Number(new URLSearchParams(location.search).get('t') || 0));
document.documentElement.dataset.ready = '1';
