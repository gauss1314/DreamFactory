#!/usr/bin/env node
// Review a narrative film the way a person would: a second model sees only the brief, the art rules
// and frames from the film (whole frames, and 1:1 close-ups around each character), and lists what
// it would send back. It never sees the code. The checks catch what can be measured; this is for the
// rest: does it look like an animated film, and could this happen in the real world.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { runFilm } from '../pipeline/film.mjs';
import { openStage } from '../pipeline/lib/stage.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.dirname(here);

const PROMPT = `你是一支手绘风动画短片的审片人。这次没有人值守，全程自己完成，不要提问。

工作目录里有：
- brief.md：这支片子的简报。
- ART.md：美术规范。第六节是看图质检的要求。
- frames.md：每张图是哪个时刻、哪个镜头、画面上应该在发生什么。
- frames/：全片的画面（full-*.jpg），和每个角色身边 1:1 的局部（near-*.jpg）。

你看不到代码，也不需要看。用读取工具逐张看图，对照简报和美术规范，找出你作为导演会退回去重做的地方。重点：
1. 合乎物理：东西有没有穿过别的东西，抓着、推着、骑着的地方是不是真的碰着，影子朝哪儿，掉落的东西怎么落，角色往哪儿走、朝哪儿看。
2. 简报里写的每个动作有没有真的画出来、看得清。
3. 像不像一部动画电影：构图、光、层次、细节，哪里显得空、平、廉价。

只写你在图上确实看到的问题，每条都要说出是哪张图、画面上的哪里。不要猜代码，不要写通用建议。最多 8 条，按严重程度排序。

最后输出一个 JSON 代码块，格式如下，不要有别的 JSON：
\`\`\`json
[{"frame": "full-03.jpg", "t": 6.6, "severity": "must", "problem": "……", "fix": "……"}]
\`\`\`
severity 只能是 must（必须改，违反物理或简报）或 should（改了会明显更好）。`;

/** Grab whole frames and character close-ups at the moments that matter. */
async function grabFrames(filmDir, outDir, opts) {
  const build = path.join(outDir, 'run');
  await runFilm(filmDir, { ...opts, video: false, log: false, outDir: build, only: [] });
  const resolved = JSON.parse(fs.readFileSync(path.join(build, 'build', 'film.resolved.json'), 'utf8'));
  const vertical = await import(pathToFileURL(path.join(repo, 'verticals', resolved.vertical ?? 'narrative', 'vertical.mjs')).href);
  const moments = [];
  resolved.timeline.scenes.forEach((span, i) => {
    const sc = resolved.scenes[i];
    const len = span.end - span.start;
    for (const f of [0.25, 0.55, 0.85]) moments.push({ t: span.start + len * f, shot: sc.id, what: '镜头中段' });
    for (const [name, at] of Object.entries(sc.events ?? {})) {
      for (const a of [].concat(at)) {
        moments.push({ t: span.start + a, shot: sc.id, what: `事件 ${name} 的那一刻` });
        moments.push({ t: span.start + a + 0.2, shot: sc.id, what: `事件 ${name} 之后 0.2 秒` });
      }
    }
  });
  moments.sort((a, b) => a.t - b.t);
  const frames = path.join(outDir, 'frames');
  fs.mkdirSync(frames, { recursive: true });
  const index = ['# 画面索引', '', '| 图 | 时刻（秒） | 镜头 | 这一刻 |', '| --- | --- | --- | --- |'];
  if (vertical.engine === 'python') {
    // a Python film draws its own frames: the driver renders them and the close-ups
    const py = process.env.DF_PYTHON ?? path.join(repo, '.venv', 'bin', 'python');
    await new Promise((resolve, reject) => {
      const child = spawn(py, [path.join(vertical.engineDir, 'tools', 'film.py'), 'frames', filmDir, '--at', moments.map((m) => m.t.toFixed(3)).join(','), '--out', frames], { stdio: 'inherit' });
      child.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`frames exited with ${code}`))));
    });
    const got = JSON.parse(fs.readFileSync(path.join(frames, 'index.json'), 'utf8'));
    got.forEach((g, k) => {
      const m = moments[k];
      index.push(`| ${g.file} | ${g.t.toFixed(2)} | ${g.shot} | ${m.what} |`);
      for (const c of g.closeups) index.push(`| ${c.file} | ${g.t.toFixed(2)} | ${g.shot} | ${c.name} 的 1:1 局部 |`);
    });
    fs.writeFileSync(path.join(outDir, 'frames.md'), index.join('\n') + '\n');
    return moments.length;
  }
  const stage = await openStage({ outDir: build, vertical, draft: false });
  try {
    for (const [k, m] of moments.entries()) {
      const n = String(k + 1).padStart(2, '0');
      await stage.seek(m.t);
      const actors = await stage.page.evaluate(() => (window.DF.actors ? window.DF.actors.map((a) => ({ ...a })) : []));
      await stage.page.screenshot({ path: path.join(frames, `full-${n}.jpg`), type: 'jpeg', quality: 85 });
      index.push(`| full-${n}.jpg | ${m.t.toFixed(2)} | ${m.shot} | ${m.what} |`);
      // one close-up per character, at 1:1, around the points it reports in frame pixels. Without
      // points there is no reliable place (a reported x may include the camera move), so the
      // close-up is the lower middle of the frame, where the characters usually are.
      const withPoints = actors.filter((x) => !x.prop && Object.keys(x.points ?? {}).length);
      const subjects = withPoints.length ? withPoints : [{ name: '画面下半部', points: { c: [960, 760] } }];
      for (const a of subjects) {
        const pts = Object.values(a.points);
        const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
        const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
        if (!(cx > -200 && cx < 2120)) continue;
        const w = 900;
        const h = 560;
        const x = Math.round(Math.min(1920 - w, Math.max(0, cx - w / 2)));
        const y = Math.round(Math.min(1080 - h, Math.max(0, cy - h / 2)));
        const file = `near-${n}-${a.name}.jpg`;
        await stage.page.screenshot({ path: path.join(frames, file), type: 'jpeg', quality: 88, clip: { x, y, width: w, height: h } });
        index.push(`| ${file} | ${m.t.toFixed(2)} | ${m.shot} | ${a.name} 的 1:1 局部 |`);
      }
    }
  } finally {
    await stage.close();
  }
  fs.writeFileSync(path.join(outDir, 'frames.md'), index.join('\n') + '\n');
  return moments.length;
}

function runClaude(cwd, prompt, { model, budget, timeoutMin, transcript }) {
  const args = ['-p', prompt, '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
    '--permission-mode', 'dontAsk', '--max-budget-usd', String(budget), '--allowedTools', 'Read(./**)', 'Bash(ls:*)'];
  if (model) args.push('--model', model);
  return new Promise((resolve) => {
    const child = spawn('claude', args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
    const out = fs.createWriteStream(transcript);
    child.stdout.pipe(out);
    const timer = setTimeout(() => child.kill('SIGKILL'), timeoutMin * 60000);
    child.on('close', () => {
      clearTimeout(timer);
      out.end(() => {
        const events = fs.readFileSync(transcript, 'utf8').split('\n').filter(Boolean).flatMap((l) => {
          try {
            return [JSON.parse(l)];
          } catch {
            return [];
          }
        });
        resolve(events.findLast((e) => e.type === 'result') ?? null);
      });
    });
  });
}

/**
 * Review the film in filmDir. Returns { issues, text, costUsd } and leaves frames, the reviewer's
 * transcript and review.md in workDir.
 */
export async function reviewFilm(filmDir, { workDir, model, budget = 4, timeoutMin = 20, filmOpts = {} }) {
  fs.rmSync(workDir, { recursive: true, force: true });
  fs.mkdirSync(workDir, { recursive: true });
  const brief = path.join(filmDir, 'brief.md');
  if (fs.existsSync(brief)) fs.copyFileSync(brief, path.join(workDir, 'brief.md'));
  else if (filmOpts.brief) fs.writeFileSync(path.join(workDir, 'brief.md'), filmOpts.brief);
  // the art rules: a film's own production contract when it has one, else the narrative rules
  const contract = path.join(filmDir, 'CONTRACT.md');
  fs.copyFileSync(fs.existsSync(contract) ? contract : path.join(repo, 'verticals', 'narrative', 'ART.md'), path.join(workDir, 'ART.md'));
  const { brief: _b, ...opts } = filmOpts;
  await grabFrames(filmDir, workDir, opts);
  // the frames come from a pipeline run; the reviewer gets only the pictures
  fs.rmSync(path.join(workDir, 'run'), { recursive: true, force: true });
  const result = await runClaude(workDir, PROMPT, { model, budget, timeoutMin, transcript: path.join(workDir, 'transcript.jsonl') });
  const text = String(result?.result ?? '');
  let issues = null;
  const block = [...text.matchAll(/```json\s*([\s\S]*?)```/g)].at(-1);
  try {
    issues = block ? JSON.parse(block[1]) : null;
  } catch {
    issues = null;
  }
  const costUsd = result ? Math.round(result.total_cost_usd * 100) / 100 : null;
  fs.writeFileSync(path.join(workDir, 'review.md'), `# 审片意见\n\n${text.trim()}\n`);
  if (issues) fs.writeFileSync(path.join(workDir, 'review.json'), JSON.stringify(issues, null, 2) + '\n');
  return { issues, text, costUsd, finished: Boolean(result) && !result.is_error };
}

// Command line: node evals/review.mjs <film dir> [--brief <file>] [--out <dir>] [--model <name>] [--budget <usd>]
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = process.argv.slice(2);
  const value = (name) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : undefined;
  };
  const dir = args.find((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
  if (!dir || args.includes('--help')) {
    console.log('用法：node evals/review.mjs <影片目录> [--brief <简报>] [--out <目录>] [--model <名称>] [--budget <美元>]\n\n  让另一个模型只看画面、简报和美术规范，列出要退回重做的地方。');
    process.exit(dir ? 0 : 1);
  }
  const out = path.resolve(value('--out') ?? path.join(dir, 'out', 'review'));
  const brief = value('--brief') ? fs.readFileSync(value('--brief'), 'utf8') : undefined;
  const r = await reviewFilm(path.resolve(dir), { workDir: out, model: value('--model'), budget: Number(value('--budget') ?? 4), filmOpts: { brief } });
  console.log(r.text.trim());
  console.log(`\n${r.issues ? `${r.issues.length} 条意见` : '没有读到 JSON 意见'}，${r.costUsd ?? '?'} 美元。审片材料：${out}`);
  process.exit(r.finished ? 0 : 1);
}
