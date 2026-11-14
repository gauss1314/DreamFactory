// Data references. A film never types a number that comes from the data: it points at it
// ({"$": "series.categories"} or "{{facts.total}}"), and the checks later verify that every
// number that reaches the screen or the narration can be traced back to data.json.

const splitPath = (p) => [...String(p).matchAll(/[^.[\]]+|\[([^\]]+)\]/g)].map((m) => m[1] ?? m[0]);

/** Look up a path. Arrays of {label, ...} items can be indexed by label: series.categories[游戏]. */
export function getPath(data, p) {
  let cur = data;
  for (const seg of splitPath(p)) {
    if (cur == null) return undefined;
    if (Array.isArray(cur)) {
      const byLabel = cur.find((it) => it && typeof it === 'object' && it.label === seg);
      cur = byLabel !== undefined ? byLabel : cur[Number(seg)];
    } else {
      cur = cur[seg];
    }
  }
  return cur;
}

/** The scalar at a path: a number or string, or the `value` of a series item. */
export function getScalar(data, p) {
  const v = getPath(data, p);
  if (v && typeof v === 'object' && !Array.isArray(v) && 'value' in v) return v.value;
  return v;
}

export const formatNumber = (n) =>
  (Number.isInteger(n) ? n : Math.round(n * 10) / 10).toLocaleString('en-US');

/** The whole-percent share of a series item within its series. */
function sharePercent(data, p) {
  const segs = splitPath(p);
  const series = getPath(data, segs.slice(0, -1).join('.'));
  const item = getPath(data, p);
  if (!Array.isArray(series) || !item || typeof item.value !== 'number') {
    throw new Error(`"share ${p}" must point at an item of a series`);
  }
  const total = series.reduce((a, it) => a + it.value, 0);
  return Math.round((100 * item.value) / total);
}

/**
 * Fill {{path}} and {{share path}} in a string.
 * mode "screen": numbers get thousands separators. mode "speech": plain digits, spoken percent.
 */
export function renderTemplate(str, data, mode, lang = 'zh') {
  return str.replace(/\{\{\s*(share\s+)?([^}]+?)\s*\}\}/g, (_, share, p) => {
    if (share) {
      const pct = sharePercent(data, p);
      if (mode === 'screen') return `${pct}%`;
      return lang === 'zh' ? `百分之${pct}` : `${pct} percent`;
    }
    const v = getScalar(data, p);
    if (v === undefined || (typeof v === 'object' && v !== null)) {
      throw new Error(`film.json points at "${p}", which is not a value in data.json`);
    }
    if (typeof v !== 'number') return String(v);
    return mode === 'screen' ? formatNumber(v) : String(v);
  });
}

/** Resolve every data reference in a film. Narration becomes {display, speech} per line. */
export function resolveFilm(film, data) {
  const lang = film.lang ?? 'zh';
  let touched = false;
  const walk = (v) => {
    if (typeof v === 'string') {
      if (v.includes('{{')) touched = true;
      return renderTemplate(v, data, 'screen', lang);
    }
    if (Array.isArray(v)) return v.map(walk);
    if (v && typeof v === 'object') {
      const keys = Object.keys(v);
      if (keys.length === 1 && keys[0] === '$') {
        const target = getPath(data, v.$);
        if (target === undefined) throw new Error(`film.json points at "${v.$}", which is not in data.json`);
        touched = true;
        return structuredClone(target);
      }
      return Object.fromEntries(keys.map((k) => [k, walk(v[k])]));
    }
    return v;
  };
  const out = { ...film, lang };
  if (film.source != null) out.source = renderTemplate(film.source, data, 'screen', lang);
  if (film.title != null) out.title = renderTemplate(film.title, data, 'screen', lang);
  out.scenes = (film.scenes ?? []).map((scene, i) => {
    touched = false;
    const { narration = [], ...rest } = scene;
    const resolved = walk(rest);
    resolved.id = scene.id ?? `scene-${i + 1}`;
    resolved.lines = narration.map((line) => {
      // A line is a string, or { text, say } when the voice should read it differently from the subtitle.
      const text = typeof line === 'string' ? line : line.text;
      const say = typeof line === 'string' ? line : line.say ?? line.text;
      if (text.includes('{{') || say.includes('{{')) touched = true;
      return {
        display: renderTemplate(text, data, 'screen', lang),
        speech: renderTemplate(say, data, 'speech', lang),
      };
    });
    resolved.usesData = touched;
    return resolved;
  });
  return out;
}

/**
 * Every number a film may show or say: the values in data.json, numbers written inside its labels
 * ("7月") and its source block (an as-of date), plus series totals and shares.
 */
export function allowedNumbers(data) {
  const set = new Set();
  const walk = (v) => {
    if (typeof v === 'number') set.add(v);
    else if (typeof v === 'string') extractNumbers(v).forEach((n) => set.add(n.value));
    else if (Array.isArray(v)) {
      if (v.length && v.every((it) => it && typeof it === 'object' && typeof it.value === 'number')) {
        const total = v.reduce((a, it) => a + it.value, 0);
        set.add(total);
        for (const it of v) {
          set.add(Math.round((100 * it.value) / total));
          set.add(Math.round((1000 * it.value) / total) / 10);
        }
      }
      v.forEach(walk);
    } else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  walk(data);
  return set;
}

/**
 * Numbers written as digits in a text. Digits glued to Latin letters ("3D", "H264") are words,
 * not quantities, and are skipped.
 */
export function extractNumbers(text) {
  const out = [];
  const re = /\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?/g;
  for (const m of text.matchAll(re)) {
    const prev = text[m.index - 1] ?? '';
    const next = text[m.index + m[0].length] ?? '';
    if (/[A-Za-z]/.test(prev) || /[A-Za-z]/.test(next)) continue;
    out.push({ raw: m[0], value: Number(m[0].replace(/,/g, '')) });
  }
  return out;
}

export const hasNumber = (set, value) => [...set].some((a) => Math.abs(a - value) < 1e-9);
