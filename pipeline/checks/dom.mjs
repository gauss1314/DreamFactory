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
    const builtin = new Set(ctx.vertical.builtinScenes);
    if (ctx.expect.requireCustomScene && !ctx.resolved.scenes.some((sc) => !builtin.has(sc.type))) {
      problems.push('任务要求的画面内置场景做不出来，需要自定义场景，但影片里只有内置场景');
    }
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
      if (ctx.audio.audible) {
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
      if (line.speech === line.display) continue;
      for (const n of extractNumbers(line.speech)) if (!hasNumber(allowed, n.value)) flag(n.raw, `念出来的旁白「${clip(line.speech)}」`);
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

export const sync = {
  id: 'sync',
  title: '同步：同一个场景里，旁白念到的数字，画面不能晚出现',
  tier: 'dom',
  run(ctx) {
    // Per scene, when each number first becomes readable in the picture. Subtitles do not count;
    // axis labels do. A number that only appears in a later scene is foreshadowing, not lag.
    const firstShown = new Map();
    for (const s of ctx.sampling.samples) {
      if (!s.grid) continue;
      for (const x of s.texts) {
        if (!shown(x) || !x.scene || x.role === 'subtitle' || x.role === 'animating') continue;
        if (!firstShown.has(x.scene)) firstShown.set(x.scene, new Map());
        const seen = firstShown.get(x.scene);
        for (const n of extractNumbers(x.text)) if (!seen.has(n.value)) seen.set(n.value, s.t);
      }
    }
    const problems = [];
    let compared = 0;
    for (const sc of ctx.timeline.scenes) {
      for (const line of sc.lines) {
        for (const n of extractNumbers(line.display)) {
          const at = firstShown.get(sc.id)?.get(n.value);
          if (at === undefined) continue;
          compared++;
          if (at > line.end + 0.3) problems.push(`旁白在 ${fmtT(line.start)} 说到 ${n.raw}，画面到 ${fmtT(at)} 才出现`);
        }
      }
    }
    return result(problems, compared ? `旁白提到的 ${compared} 处数字，画面都没有晚出现` : '没有旁白和画面同场出现的数字');
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

export const typography = {
  id: 'typography',
  title: '文字规范：没有重复的标点、残留的模板符号、空括号、带千分位的年份',
  tier: 'dom',
  run(ctx) {
    const rules = [
      [/[%％]{2,}/, '重复的百分号'],
      [/([，。、；：？！,;:?!])\1+/, '重复的标点'],
      [/\{\{|\}\}/, '残留的模板符号'],
      [/（\s*）|\(\s*\)/, '空括号'],
      [/(?<![\d,])[12],\d{3}\s?年/, '年份带了千分位'],
    ];
    const problems = new Map();
    const scan = (text, where) => {
      for (const [re, name] of rules) if (re.test(text)) problems.set(`${name}|${text}`, `${name}：${where}「${clip(text, 30)}」`);
    };
    for (const s of ctx.sampling.samples) {
      for (const x of s.texts) if (shown(x) && x.role !== 'animating' && x.role !== 'subtitle') scan(x.text, '画面');
    }
    for (const sc of ctx.timeline.scenes) for (const line of sc.lines) scan(line.display, '旁白');
    return result([...problems.values()], '没有发现文字规范问题');
  },
};

export const marks = {
  id: 'marks',
  title: '图形：标了数值的图形，长短高低与数值一致',
  tier: 'dom',
  run(ctx) {
    const allowed = allowedNumbers(ctx.data);
    const problems = [];
    const groups = new Map();
    for (const s of ctx.sampling.samples) {
      for (const m of s.marks ?? []) {
        const key = `${m.scene}/${m.group}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(m);
      }
    }
    // Scene code written for one film has to say which shape stands for which number.
    const builtin = new Set(ctx.vertical.builtinScenes);
    for (const sc of ctx.resolved.scenes) {
      if (builtin.has(sc.type) || !sc.usesData) continue;
      if (![...groups.keys()].some((k) => k.startsWith(`${sc.id}/`))) {
        problems.push(`自定义场景 ${sc.id} 用了数据，但没有给图形标 data-df-value`);
      }
    }
    let compared = 0;
    for (const [key, list] of groups) {
      const flat = list.filter((m) => m.w < 1 || m.h < 1).length;
      if (flat) problems.push(`${flat} 个图形没有画出来，宽或高为零（${key}）`);
      const stray = [...new Set(list.map((m) => m.value))].filter((v) => !hasNumber(allowed, v));
      for (const v of stray) problems.push(`图形标注的数值 ${v} 不在数据里（${key}）`);
      if (new Set(list.map((m) => m.value)).size < 3) continue;
      compared++;
      const sorted = [...list].sort((a, b) => a.value - b.value);
      // A larger value must be longer, taller, higher up or further right, on at least one of these.
      const need = Math.max(3, Math.ceil(new Set(list.map((m) => m.value)).size / 2));
      const follows = (get) =>
        new Set(sorted.map((m) => Math.round(get(m)))).size >= need &&
        sorted.every((m, i) => i === 0 || (sorted[i - 1].value === m.value ? Math.abs(get(m) - get(sorted[i - 1])) <= 1 : get(m) >= get(sorted[i - 1]) - 0.5));
      const ok = [(m) => m.w, (m) => m.h, (m) => -m.cy, (m) => m.cx].some(follows);
      if (!ok) problems.push(`图形与数值不一致（${key}）：数值大的图形应该更长、更高或位置更靠上`);
    }
    return result(problems, compared ? `${compared} 组图形与数值一致` : '没有可比较的图形');
  },
};

export const determinism = {
  id: 'determinism',
  title: '可重复：同一时刻重画，画面一致',
  tier: 'dom',
  run(ctx) {
    // Above one pixel in ten thousand. Browser anti-aliasing noise measured far below that.
    const problems = ctx.sampling.repeat
      .filter((r) => r.changed > 1e-4)
      .map((r) => `${fmtT(r.t)} 重画后有 ${(r.changed * 100).toFixed(2)}% 的像素不同，画面不能依赖随机数、时钟或上一帧`);
    return result(problems, `抽查 ${ctx.sampling.repeat.length} 个时刻，重画结果一致`);
  },
};

export const heading = {
  id: 'heading',
  title: '朝向：角色往哪儿走，就朝哪儿；侧面画的角色不往纵深里走',
  tier: 'dom',
  run(ctx) {
    const FACING = { right: 0, left: 180 };
    const problems = new Map();
    let judged = 0;
    for (const sc of ctx.timeline.scenes) {
      const grid = ctx.sampling.samples.filter((s) => s.grid && s.actors && s.t >= sc.start + 0.2 && s.t <= sc.end - 0.2);
      const names = new Set(grid.flatMap((s) => s.actors.map((a) => a.name)));
      for (const name of names) {
        const track = grid.map((s) => ({ t: s.t, a: s.actors.find((a) => a.name === name) })).filter((p) => p.a);
        for (let i = 0; i < track.length; i++) {
          const j = track.findIndex((p) => p.t >= track[i].t + 0.5 - 1e-6);
          if (j < 0) break;
          const [p, q] = [track[i], track[j]];
          const dt = q.t - p.t;
          const dx = q.a.x - p.a.x;
          const dy = q.a.y - p.a.y;
          const speed = Math.hypot(dx, dy) / dt;
          const depth = Math.abs(Math.log(q.a.s / p.a.s)) / dt;
          if (speed < 20 && depth < 0.02) continue;
          judged++;
          const face = FACING[p.a.facing];
          if (face === undefined) continue;
          if (depth > 0.1) {
            problems.set(`${sc.id}|${name}|depth`, `${sc.id}：${name} 画的是侧面，却在往纵深里走（大小每秒变化 ${Math.round(depth * 100)}%）`);
          }
          if (speed >= 20) {
            const ang = (Math.atan2(-dy, dx) * 180) / Math.PI;
            const off = Math.abs(((ang - face + 540) % 360) - 180);
            if (off > 20) problems.set(`${sc.id}|${name}|dir`, `${sc.id}：${name} 朝${p.a.facing === 'right' ? '右' : '左'}，却在往 ${Math.round(ang)}° 方向移动，偏了 ${Math.round(off)}°，上限 20°`);
          }
        }
      }
    }
    if (!judged) return { status: 'skip', summary: '没有角色报告位置', details: [] };
    return result([...problems.values()], `检查了 ${judged} 段移动，方向都和朝向一致`);
  },
};

// Where a character holds, pushes or rides something, the film declares the two points that must
// touch, and the shot reports where it drew them. A hand that floats off the handle is caught here.
export const contact = {
  id: 'contact',
  title: '接触：抓着、推着、骑着的地方，两个点真的碰在一起',
  tier: 'dom',
  run(ctx) {
    const track = ctx.sampling.track;
    const problems = new Map();
    let judged = 0;
    let declared = 0;
    for (const [i, sc] of ctx.timeline.scenes.entries()) {
      const specs = (ctx.resolved.scenes[i].contacts ?? []).map((c) => (Array.isArray(c) ? { a: c[0], b: c[1] } : c));
      declared += specs.length;
      for (const c of specs) {
        // "min" asks the opposite: two things that must not touch (a nose and the cart it pushes)
        const apart = c.min !== undefined && c.max === undefined;
        const max = c.max ?? 12;
        const from = sc.start + (c.from ?? 0);
        const to = Math.min(sc.end, sc.start + (c.to ?? Infinity));
        const point = (frame, ref) => {
          const [name, key] = ref.split('.');
          const p = frame.actors.find((a) => a.name === name)?.points?.[key];
          return Array.isArray(p) ? p : null;
        };
        let worst = null;
        let missing = null;
        for (const f of track ?? []) {
          if (f.t < from || f.t >= to) continue;
          const [p, q] = [point(f, c.a), point(f, c.b)];
          if (!p || !q) {
            missing ??= { t: f.t, ref: p ? c.b : c.a };
            continue;
          }
          judged++;
          const d = Math.hypot(p[0] - q[0], p[1] - q[1]);
          if (apart ? d < c.min && (!worst || d < worst.d) : d > max && (!worst || d > worst.d)) worst = { d, t: f.t };
        }
        const key = `${sc.id}|${c.a}|${c.b}`;
        if (missing) problems.set(`${key}|missing`, `${sc.id}：声明了 ${c.a} 碰着 ${c.b}，但 ${fmtT(missing.t)} 这一帧没有报告 ${missing.ref} 的位置`);
        if (worst && apart) problems.set(key, `${sc.id}：${c.a} 不该碰到 ${c.b}，${fmtT(worst.t)} 时两点只隔 ${Math.round(worst.d)} 像素，至少要 ${c.min}`);
        else if (worst) problems.set(key, `${sc.id}：${c.a} 应该碰着 ${c.b}，${fmtT(worst.t)} 时两点相距 ${Math.round(worst.d)} 像素，上限 ${max}`);
      }
    }
    if (!declared) return { status: 'skip', summary: 'film.json 没有声明接触点（contacts）', details: [] };
    return result([...problems.values()], `${declared} 处接触，查了 ${judged} 帧，都符合声明`);
  },
};

// Things that fly without power of their own (a thrown bun, a bounced stone) report how high above
// the ground they are. In the air they follow a parabola, and stay on the ground line they left
// from. They may fly toward the camera only in a shot that declares its horizon, and then their
// size has to grow the way perspective says: scale in proportion to the distance below the horizon.
export const landing = {
  id: 'landing',
  title: '落地：抛出去的东西走抛物线，落在它离开时的那条地面线上',
  tier: 'dom',
  run(ctx) {
    const track = ctx.sampling.track ?? [];
    const problems = [];
    let flights = 0;
    for (const [si, sc] of ctx.timeline.scenes.entries()) {
      const horizon = ctx.resolved.scenes[si].horizon;
      const frames = track.filter((f) => f.t >= sc.start && f.t < sc.end);
      const names = new Set(frames.flatMap((f) => f.actors.filter((a) => a.ballistic).map((a) => a.name)));
      for (const name of names) {
        const seq = frames.map((f) => ({ t: f.t, a: f.actors.find((a) => a.name === name), all: f.actors })).filter((p) => p.a);
        for (let i = 0; i < seq.length; i++) {
          if (!(seq[i].a.air > 0.5)) continue;
          // One flight: the frames in the air, plus the last frame on the ground before and the first
          // after. A bounce can touch down between two looks: a dip in height (lower than the frame
          // before, no higher than the one after) ends one flight and starts the next.
          let j = i;
          const dip = (k) => k > 0 && k + 1 < seq.length && seq[k].a.air < seq[k - 1].a.air && seq[k].a.air <= seq[k + 1].a.air;
          while (j + 1 < seq.length && seq[j + 1].a.air > 0.5 && !dip(j + 1)) j++;
          // a flight that starts at a dip took off from that bounce, not from the frame before it
          const from = dip(i) ? i : Math.max(0, i - 1);
          const take = seq[from];
          const land = seq[Math.min(seq.length - 1, j + 1)];
          const span = seq.slice(from, Math.min(seq.length, j + 2));
          i = j;
          flights++;
          const tol = 6 * Math.max(1, take.a.s ?? 1);
          const y0 = take.a.y;
          const drift = span.reduce((m, p) => (Math.abs(p.a.y - y0) > Math.abs(m.dy) ? { dy: p.a.y - y0, t: p.t } : m), { dy: 0, t: take.t });
          if (horizon !== undefined && Math.abs(drift.dy) > tol) {
            // moving in depth is allowed here, but the size must follow: s / (y - horizon) stays put
            const k0 = (take.a.s ?? 1) / (y0 - horizon);
            const bad = span.find((p) => Math.abs((p.a.s ?? 1) / (p.a.y - horizon) / k0 - 1) > 0.08);
            if (bad) {
              const want = k0 * (bad.a.y - horizon);
              problems.push(`${sc.id}：${name} 往${bad.a.y > y0 ? '镜头这边' : '远处'}飞了 ${Math.round(Math.abs(bad.a.y - y0))} 像素，按透视大小应该是 ${want.toFixed(2)}，画的是 ${(bad.a.s ?? 1).toFixed(2)}（${fmtT(bad.t)}）`);
            }
          } else if (Math.abs(drift.dy) > tol) {
            problems.push(`${sc.id}：${name} 在空中时地面位置变了 ${Math.round(drift.dy)} 像素（${fmtT(drift.t)}），${drift.dy > 0 ? '往镜头这边' : '往远处'}掉；侧面看抛出去的东西应该落回它离开时的那条地面线`);
          }
          if (land.a.air > 0.5 && !dip(j + 1)) problems.push(`${sc.id}：${name} 到镜头结束还在空中`);
          const parent = take.a.from && take.all.find((a) => a.name === take.a.from);
          if (parent && Math.abs(parent.y - y0) > tol) {
            problems.push(`${sc.id}：${name} 从 ${take.a.from} 上飞出时，地面位置和 ${take.a.from} 差了 ${Math.round(y0 - parent.y)} 像素`);
          }
          // the height over time must be a parabola opening downward
          const pts = span.map((p) => [p.t - span[0].t, p.a.air]);
          if (pts.length >= 4) {
            const fit = quadFit(pts);
            const peak = Math.max(...pts.map((p) => p[1]));
            const resid = Math.sqrt(pts.reduce((m, [x, y]) => m + (y - (fit.a * x * x + fit.b * x + fit.c)) ** 2, 0) / pts.length);
            if (fit.a >= 0) problems.push(`${sc.id}：${name} 在空中没有往下加速，不像被抛出去的东西`);
            else if (resid > Math.max(4, peak * 0.12)) problems.push(`${sc.id}：${name} 的高度变化不是抛物线（偏差 ${Math.round(resid)} 像素，最高 ${Math.round(peak)} 像素）`);
          }
        }
      }
    }
    if (!flights) return { status: 'skip', summary: '没有报告抛出去的东西（ballistic）', details: [] };
    return result(problems, `${flights} 次飞起，都走抛物线，落点合乎透视`);
  },
};

function quadFit(pts) {
  // least squares for y = a x^2 + b x + c
  const S = (f) => pts.reduce((m, [x, y]) => m + f(x, y), 0);
  const [s0, s1, s2, s3, s4] = [0, 1, 2, 3, 4].map((k) => S((x) => x ** k));
  const [t0, t1, t2] = [0, 1, 2].map((k) => S((x, y) => y * x ** k));
  const det = (m) => m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
  const M = [[s4, s3, s2], [s3, s2, s1], [s2, s1, s0]];
  const D = det(M) || 1e-9;
  const col = (k, v) => M.map((r, i) => r.map((x, j) => (j === k ? v[i] : x)));
  const v = [t2, t1, t0];
  return { a: det(col(0, v)) / D, b: det(col(1, v)) / D, c: det(col(2, v)) / D };
}

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
