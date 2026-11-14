// Checks that read the film through its live page: what text is on screen, where, for how long.
import { allowedNumbers, extractNumbers, getScalar, hasNumber } from '../lib/data.mjs';
import { SAMPLE_STEP } from '../lib/stage.mjs';

const SHOWN = 0.6; // opacity from which text counts as on screen
const fmtT = (t) => `${t.toFixed(1)}s`;
const shown = (x) => x.opacity >= SHOWN;
const isFact = (x) => !['tick', 'animating', 'source'].includes(x.role);
const isContent = (x) => !['tick', 'animating', 'source', 'subtitle'].includes(x.role);
const cjkCount = (s) => (s.match(/[㐀-鿿＀-￯　-〿]/g) || []).length;
const clip = (s, n = 24) => (s.length > n ? `${s.slice(0, n)}…` : s);
const result = (problems, okSummary) => ({
  status: problems.length ? 'fail' : 'pass',
  summary: problems.length ? `${problems.length} 处问题` : okSummary,
  details: problems.slice(0, 12),
});

export const spec = {
  id: 'spec',
  title: '规格：片长、分辨率、帧率、编码',
  tier: 'dom',
  run(ctx) {
    const problems = [];
    const d = ctx.timeline.duration;
    const [min, max] = ctx.expect.duration ?? [0, Infinity];
    if (d < min || d > max) problems.push(`片长 ${d.toFixed(1)} 秒，要求 ${min}–${max} 秒`);
    for (const e of ctx.sampling.pageErrors) problems.push(`页面报错：${clip(e, 80)}`);
    const m = ctx.media;
    if (m) {
      const v = m.video;
      if (!v) problems.push('成片里没有视频流');
      else {
        if (v.codec !== 'h264' || v.pixFmt !== 'yuv420p') problems.push(`视频编码为 ${v.codec}/${v.pixFmt}，应为 h264/yuv420p`);
        if (v.width !== ctx.render.width || v.height !== ctx.render.height) {
          problems.push(`分辨率 ${v.width}x${v.height}，应为 ${ctx.render.width}x${ctx.render.height}`);
        }
        if (Math.abs(v.fps - ctx.render.fps) > 0.01) problems.push(`帧率 ${v.fps}，应为 ${ctx.render.fps}`);
        if (Math.abs(v.duration - d) > 0.15) problems.push(`视频长 ${v.duration.toFixed(2)} 秒，时间轴为 ${d.toFixed(2)} 秒`);
      }
      if (ctx.audio.voiced) {
        if (!m.audio) problems.push('成片里没有音轨');
        else if (v && Math.abs(m.audio.duration - v.duration) > 0.15) {
          problems.push(`音轨长 ${m.audio.duration.toFixed(2)} 秒，视频长 ${v.duration.toFixed(2)} 秒`);
        }
      }
    }
    return result(problems, `片长 ${d.toFixed(1)} 秒${m ? '，成片规格正确' : ''}`);
  },
};

export const dataAccuracy = {
  id: 'data-accuracy',
  title: '数据准确：画面和旁白里的数字都能追溯到 data.json',
  tier: 'dom',
  run(ctx) {
    const allowed = allowedNumbers(ctx.data);
    const problems = [];
    const seen = new Set();
    const flag = (raw, where) => {
      const key = `${raw}|${where}`;
      if (seen.has(key)) return;
      seen.add(key);
      problems.push(`数字 ${raw} 不在数据里：${where}`);
    };
    for (const s of ctx.sampling.samples) {
      for (const x of s.texts) {
        if (!shown(x) || !isFact(x) || x.role === 'subtitle') continue;
        for (const n of extractNumbers(x.text)) if (!hasNumber(allowed, n.value)) flag(n.raw, `画面「${clip(x.text)}」(${fmtT(s.t)})`);
      }
    }
    const lines = ctx.timeline.scenes.flatMap((sc) => sc.lines);
    for (const line of lines) {
      for (const n of extractNumbers(line.display)) if (!hasNumber(allowed, n.value)) flag(n.raw, `旁白「${clip(line.display)}」`);
    }

    // Required facts must be readable in the picture itself, not only in subtitles.
    for (const p of ctx.expect.mustShow ?? []) {
      const v = getScalar(ctx.data, p);
      if (typeof v !== 'number') {
        problems.push(`expect.mustShow 的 ${p} 不是 data.json 里的数字`);
        continue;
      }
      let hits = 0;
      for (const s of ctx.sampling.samples) {
        if (!s.grid) continue;
        const on = s.texts.some((x) => shown(x) && isContent(x) && extractNumbers(x.text).some((n) => Math.abs(n.value - v) < 1e-9));
        if (on) hits++;
      }
      if (hits * SAMPLE_STEP < 1) problems.push(`必须出现的数据 ${p} = ${v} 没有在画面上停留满 1 秒`);
    }
    for (const p of ctx.expect.mustSay ?? []) {
      const v = getScalar(ctx.data, p);
      const said = lines.some((l) => extractNumbers(l.display).some((n) => Math.abs(n.value - v) < 1e-9));
      if (!said) problems.push(`旁白必须提到的数据 ${p} = ${v} 没有出现`);
    }
    return result(problems, '所有数字都来自数据，必须出现的数据都在');
  },
};

export const readability = {
  id: 'readability',
  title: '可读性：文字停留够久、字号够大',
  tier: 'dom',
  run(ctx) {
    const problems = [];
    const seenFor = new Map();
    const small = new Map();
    for (const s of ctx.sampling.samples) {
      for (const x of s.texts) {
        if (!shown(x) || x.role === 'animating') continue;
        const min = x.role === 'source' || x.role === 'tick' ? 20 : 28;
        if (x.fontSize < min) small.set(x.id, `字号 ${x.fontSize}px 小于 ${min}px：「${clip(x.text)}」`);
        if (!s.grid || x.role === 'source' || x.role === 'tick') continue;
        const key = `${x.id}|${x.text}`;
        const rec = seenFor.get(key) ?? { text: x.text, n: 0, first: s.t };
        rec.n++;
        seenFor.set(key, rec);
      }
    }
    for (const rec of seenFor.values()) {
      const cjk = cjkCount(rec.text);
      const other = rec.text.replace(/\s/g, '').length - cjk;
      const need = Math.max(0.8, cjk / 9 + other / 20);
      const had = rec.n * SAMPLE_STEP;
      if (had + SAMPLE_STEP / 2 < need) {
        problems.push(`「${clip(rec.text)}」只停留约 ${had.toFixed(1)} 秒，读完需要 ${need.toFixed(1)} 秒 (${fmtT(rec.first)})`);
      }
    }
    problems.push(...small.values());
    return result(problems, '所有文字都有足够的阅读时间和字号');
  },
};

export const layout = {
  id: 'layout',
  title: '版式：文字不出界、不溢出容器、不互相重叠',
  tier: 'dom',
  run(ctx) {
    const problems = new Map();
    const safe = { x0: 48, y0: 24, x1: 1920 - 48, y1: 1080 - 12 };
    for (const s of ctx.sampling.samples) {
      const on = s.texts.filter(shown);
      for (const x of on) {
        const x1 = x.x + x.w;
        const y1 = x.y + x.h;
        if (x.x < safe.x0 - 1 || x.y < safe.y0 - 1 || x1 > safe.x1 + 1 || y1 > safe.y1 + 1) {
          problems.set(`safe|${x.id}`, `超出画面安全区：「${clip(x.text)}」(${fmtT(s.t)})`);
        }
        const b = x.box;
        if (b && (x.x < b.x - 2 || x.y < b.y - 2 || x1 > b.x + b.w + 2 || y1 > b.y + b.h + 2)) {
          problems.set(`box|${x.id}`, `溢出所在容器：「${clip(x.text)}」(${fmtT(s.t)})`);
        }
      }
      for (let i = 0; i < on.length; i++) {
        for (let j = i + 1; j < on.length; j++) {
          const a = on[i];
          const b = on[j];
          if (a.id === b.id) continue;
          const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
          const hgt = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
          if (w <= 0 || hgt <= 0) continue;
          if ((w * hgt) / Math.min(a.w * a.h, b.w * b.h) > 0.15) {
            problems.set(`overlap|${a.id}|${b.id}`, `文字重叠：「${clip(a.text, 14)}」与「${clip(b.text, 14)}」(${fmtT(s.t)})`);
          }
        }
      }
    }
    return result([...problems.values()], '没有出界、溢出或重叠的文字');
  },
};

export const contrast = {
  id: 'contrast',
  title: '对比度：文字与背景分得开',
  tier: 'dom',
  run(ctx) {
    const worst = new Map();
    let measured = 0;
    for (const s of ctx.sampling.samples) {
      for (const x of s.texts) {
        if (x.contrast == null) continue;
        measured++;
        const need = x.fontSize >= 36 ? 3 : 4.5;
        if (x.contrast >= need) continue;
        const key = `${x.id}|${x.text}`;
        if (!worst.has(key) || worst.get(key).ratio > x.contrast) worst.set(key, { ratio: x.contrast, need, text: x.text, t: s.t });
      }
    }
    const problems = [...worst.values()].map((w) => `对比度 ${w.ratio}:1，低于 ${w.need}:1：「${clip(w.text)}」(${fmtT(w.t)})`);
    if (!measured) return { status: 'fail', summary: '没有测到任何文字的对比度', details: [] };
    return result(problems, `抽测 ${measured} 处文字，对比度都达标`);
  },
};

export const citation = {
  id: 'citation',
  title: '来源：用到数据的画面都标注了数据来源',
  tier: 'dom',
  run(ctx) {
    const scenes = ctx.timeline.scenes.filter((sc) => sc.usesData);
    if (!scenes.length) return { status: 'pass', summary: '没有用到数据的画面', details: [] };
    const name = ctx.data.source?.name;
    if (!name) return { status: 'fail', summary: 'data.json 没有写 source.name', details: [] };
    const problems = [];
    for (const sc of scenes) {
      const mid = (sc.start + sc.end) / 2;
      const s = ctx.sampling.samples.reduce((a, b) => (Math.abs(b.t - mid) < Math.abs(a.t - mid) ? b : a));
      const ok = s.texts.some((x) => x.role === 'source' && shown(x) && x.text.includes(name));
      if (!ok) problems.push(`场景 ${sc.id} 没有显示数据来源「${clip(name, 40)}」`);
    }
    return result(problems, `${scenes.length} 个数据画面都标了来源`);
  },
};

export const emptyFrames = {
  id: 'empty-frames',
  title: '空画面：没有内容的画面不超过 1.5 秒',
  tier: 'dom',
  run(ctx) {
    const problems = [];
    let runStart = null;
    const grid = ctx.sampling.samples.filter((s) => s.grid);
    const close = (endT) => {
      if (runStart != null && endT - runStart >= 1.5) problems.push(`${fmtT(runStart)}–${fmtT(endT)} 画面上没有内容`);
      runStart = null;
    };
    for (const s of grid) {
      const empty = !s.texts.some((x) => x.opacity >= 0.5 && isContent(x));
      if (empty && runStart == null) runStart = s.t;
      if (!empty) close(s.t);
    }
    close(ctx.timeline.duration);
    return result(problems, '没有长时间的空画面');
  },
};

export const subtitles = {
  id: 'subtitles',
  title: '字幕：与旁白逐句对应，长度合适',
  tier: 'dom',
  run(ctx) {
    const problems = [];
    const zh = ctx.resolved.lang === 'zh';
    const limit = zh ? 30 : 84;
    const norm = (s) => s.replace(/\s+/g, ' ').trim();
    let count = 0;
    for (const sc of ctx.timeline.scenes) {
      for (const line of sc.lines) {
        count++;
        const cjk = cjkCount(line.display);
        const len = zh ? cjk + (line.display.length - cjk) / 2 : line.display.length;
        if (len > limit) problems.push(`这句旁白 ${Math.round(len)} 字，超过 ${limit} 字，请拆句：「${clip(line.display)}」`);
        const mid = (line.start + line.end) / 2;
        const s = ctx.sampling.samples.reduce((a, b) => (Math.abs(b.t - mid) < Math.abs(a.t - mid) ? b : a));
        const text = s.texts.filter((x) => x.role === 'subtitle' && shown(x)).map((x) => x.text).join(' ');
        if (norm(text) !== norm(line.display)) problems.push(`${fmtT(mid)} 的字幕与旁白不一致：「${clip(line.display)}」`);
      }
    }
    return result(problems, `${count} 句旁白都有对应字幕`);
  },
};

export const fonts = {
  id: 'fonts',
  title: '字体：中文字形能正常显示',
  tier: 'dom',
  run(ctx) {
    const hasCjk = ctx.sampling.samples.some((s) => s.texts.some((x) => cjkCount(x.text) > 0));
    if (!hasCjk) return { status: 'pass', summary: '影片没有中文文字', details: [] };
    if (ctx.sampling.cjkOk) return { status: 'pass', summary: '中文字形正常', details: [] };
    return { status: 'fail', summary: '中文显示为空白方框，这台机器缺少中文字体', details: [] };
  },
};
