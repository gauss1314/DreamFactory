#!/usr/bin/env node
// Task-level eval: a model gets only the brief, the data and DIRECTOR.md, and has to deliver a film
// that passes the checks with nobody to ask. It never sees the reference film of the case.
// Measured: did it deliver, how many pipeline runs it needed, what it cost, and whether it stayed
// inside the rules. The delivered film is then checked again here, outside the model's reach.
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runFilm } from '../pipeline/film.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.dirname(here);
const casesDir = path.join(here, 'cases');

const args = process.argv.slice(2);
const value = (name) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
};
if (args.includes('--help')) {
  console.log(`用法：node evals/agent-run.mjs [选项]

  让模型在没有人值守的情况下完成每个用例，并记录轮数、费用和结果。
  需要已登录的 Claude Code 命令行（claude）。

  --only <a,b>      只跑指定的用例
  --brief <目录>    不跑评测用例，改跑一份没有参考影片的简报（如 evals/briefs/ 下的目录）
  --model <名称>    指定模型，默认用命令行当前配置的模型
  --jobs <n>        同时跑几个，默认 3
  --budget <美元>   每个用例的费用上限，默认 8
  --timeout <分钟>  每个用例的时间上限，默认 30
  --work <目录>     工作区位置，默认在系统临时目录
  --label <名称>    结果目录名，默认是 日期-模型
  --summarize <名称> 不运行，只按已有记录重新生成该结果目录的汇总`);
  process.exit(0);
}
const only = value('--only')?.split(',');
const model = value('--model');
const jobs = Number(value('--jobs') ?? 3);
const budget = Number(value('--budget') ?? 8);
const timeoutMin = Number(value('--timeout') ?? 30);
const workRoot = value('--summarize') ? null : path.resolve(value('--work') ?? fs.mkdtempSync(path.join(os.tmpdir(), 'dreamfactory-agent-')));

const PROMPTS = {};
PROMPTS['data-story'] = `你在一条做数据短片的管线里工作。这次没有人值守，没有人可以提问，全程自己完成。

工作目录里有 DIRECTOR.md（导演规范）、pipeline/（管线）和 task/（任务）。
task/ 里有 brief.md（简报）、data.json（数据）、expect.json（要求）。
先读 DIRECTOR.md，按它的流程写出 task/film.json，直到草稿渲染（--draft）的自检全部通过。

这次运行的权限如下。超出范围的操作会被直接拒绝，不会有人来批准：
- 读文件：只能读工作目录里的文件，用读取工具。
- 写文件：只能用写入、编辑工具新建和修改 task/film.json，以及确有需要时的 task/scenes.js。
- 运行命令：只放行两种。一种是 ls。另一种是 node pipeline/cli.mjs run task，后面可以加 --no-video 或 --draft。
  命令后面不要接分号、管道、重定向或别的命令，否则整条会被拒绝。
- 某一条命令被拒绝，只说明那一条不在放行范围内。上面两种命令仍然可以用。
- 管线输出的开头就是结论，不需要另外看退出码。

按 DIRECTOR.md 的规定最多返工 3 轮；仍不通过就停下，说明卡在哪里。

结束时用三五句话报告：是否通过、管线跑了几次、每次改了什么。`;

PROMPTS.narrative = `你在一条做手绘风动画短片的管线里工作。这次没有人值守，没有人可以提问，全程自己完成。

工作目录里有 pipeline/（管线）、verticals/narrative/（画面引擎、美术规范 ART.md、导演规范 DIRECTOR.md）和 task/（任务）。
task/ 里有 brief.md（简报）和 expect.json（要求）。
先读 verticals/narrative/DIRECTOR.md 和 ART.md，按规范写出 task/film.json、task/scenes.js 和 task/sound.js，直到草稿渲染（--draft）的自检全部通过。
画面要好看、动作要合乎物理，这两点检查只能抓到一部分，要靠你自己看抽帧图把关。

这次运行的权限如下。超出范围的操作会被直接拒绝，不会有人来批准：
- 读文件：只能读工作目录里的文件，用读取工具，图片也可以读。
- 写文件：只能用写入、编辑工具新建和修改 task/ 里的 film.json、scenes.js、sound.js。
- 运行命令：只放行两种。一种是 ls。另一种是 node pipeline/cli.mjs run task，后面可以加 --no-video 或 --draft。
  命令后面不要接分号、管道、重定向或别的命令，否则整条会被拒绝。
- 某一条命令被拒绝，只说明那一条不在放行范围内。上面两种命令仍然可以用。
- 管线输出的开头就是结论，不需要另外看退出码。

按 DIRECTOR.md 的规定最多返工 4 轮；仍不通过就停下，说明卡在哪里。

结束时用三五句话报告：是否通过、管线跑了几次、每次改了什么，以及你自己看图觉得最弱的地方。`;

// What the director is allowed to touch: write only inside task/, run only the pipeline on the task.
// Reading needs no rule inside the working directory and is refused outside it; the one exception
// is the command line's own cache of long tool output. Everything else is refused without a prompt.
const TOOLS = ['Edit(task/**)', 'Bash(node pipeline/cli.mjs run task:*)', 'Bash(ls:*)', 'Read(~/.claude/projects/**)'];

function treeHash(dir, skip = []) {
  const h = createHash('sha256');
  const walk = (d) => {
    for (const name of fs.readdirSync(d).sort()) {
      const p = path.join(d, name);
      const rel = path.relative(dir, p);
      if (skip.includes(rel.split(path.sep)[0])) continue;
      const st = fs.lstatSync(p);
      if (st.isDirectory()) walk(p);
      else if (st.isFile()) h.update(rel).update(fs.readFileSync(p));
    }
  };
  walk(dir);
  return h.digest('hex');
}
const fileHash = (files) => files.reduce((h, f) => h.update(fs.readFileSync(f)), createHash('sha256')).digest('hex');

function runCli(ws, transcriptFile, prompt) {
  const cliArgs = ['-p', prompt, '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
    '--permission-mode', 'dontAsk', '--max-budget-usd', String(budget)];
  if (model) cliArgs.push('--model', model);
  cliArgs.push('--allowedTools', ...TOOLS);
  return new Promise((resolve) => {
    const env = { ...process.env, DF_TTS_CACHE: path.join(workRoot, '.tts-cache') };
    const child = spawn('claude', cliArgs, { cwd: ws, env, stdio: ['ignore', 'pipe', 'pipe'] });
    const out = fs.createWriteStream(transcriptFile);
    let stderr = '';
    child.stdout.pipe(out);
    child.stderr.on('data', (d) => (stderr += d));
    const timer = setTimeout(() => child.kill('SIGKILL'), timeoutMin * 60000);
    child.on('error', (e) => {
      clearTimeout(timer);
      resolve({ code: -1, stderr: String(e.message) });
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      out.end(() => resolve({ code, stderr }));
    });
  });
}

function readTranscript(file, ws) {
  const events = fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).flatMap((l) => {
    try {
      return [JSON.parse(l)];
    } catch {
      return [];
    }
  });
  const uses = events
    .filter((e) => e.type === 'assistant')
    .flatMap((e) => e.message?.content ?? [])
    .filter((b) => b.type === 'tool_use');
  const ownSpill = (p) => p.includes(`${path.sep}.claude${path.sep}`) && p.includes(`${path.sep}tool-results${path.sep}`);
  const inside = (p) => path.resolve(ws, p).startsWith(fs.realpathSync(ws)) || path.resolve(ws, p).startsWith(ws) || ownSpill(p);
  // Any call that names a path outside the workspace counts, whether it went through or was refused.
  const outside = uses
    .filter((u) => ['Read', 'Glob', 'Grep'].includes(u.name))
    .map((u) => u.input?.file_path ?? u.input?.path)
    .filter((p) => p && !inside(p));
  for (const u of uses) {
    if (u.name === 'Bash' && String(u.input?.command ?? '').includes(repo)) outside.push(`Bash: ${String(u.input.command).slice(0, 120)}`);
  }
  return { result: events.findLast((e) => e.type === 'result') ?? null, toolUses: uses.length, readsOutsideWorkspace: outside };
}

/**
 * passed: the model got its own draft through the checks, and the film passes again here.
 * unchecked: the film passes here, but the model never got a draft through the checks itself.
 * interrupted: the model did not end normally (usage limit, budget, timeout).
 */
function outcomeOf(r) {
  if (!r.agent.finished) return 'interrupted';
  if (!r.verified.passed) return 'failed';
  return r.roundLog.some((x) => x.passed && x.rendered) ? 'passed' : 'unchecked';
}

const briefDir = value('--brief') ? path.resolve(value('--brief')) : null;

async function runCase(id) {
  const src = briefDir ?? path.join(casesDir, id);
  const ws = path.join(workRoot, id);
  const task = path.join(ws, 'task');
  fs.rmSync(ws, { recursive: true, force: true });
  fs.mkdirSync(task, { recursive: true });
  for (const d of ['pipeline', 'verticals']) fs.cpSync(path.join(repo, d), path.join(ws, d), { recursive: true });
  // The reference film says which vertical the case belongs to; the model never sees the film itself.
  // A new brief has no reference film; it names its vertical in expect.json instead.
  const expect = JSON.parse(fs.readFileSync(path.join(src, 'expect.json'), 'utf8'));
  const refFilm = path.join(src, 'film.json');
  const vertical = (fs.existsSync(refFilm) ? JSON.parse(fs.readFileSync(refFilm, 'utf8')).vertical : expect.vertical) ?? 'data-story';
  delete expect.vertical;
  const narrative = vertical === 'narrative';
  for (const f of narrative ? ['package.json'] : ['DIRECTOR.md', 'package.json']) fs.copyFileSync(path.join(repo, f), path.join(ws, f));
  const inputs = narrative ? ['brief.md', 'expect.json'] : ['brief.md', 'data.json', 'expect.json'];
  // A narrative case's colour script is the reference film's own, keyed by its shot ids: the model
  // writes its own shots and its own colour script, so that part of the requirements is left out.
  if (narrative) {
    delete expect.palette;
    delete expect.paletteTolerance;
  }
  for (const f of inputs) {
    if (f === 'expect.json') fs.writeFileSync(path.join(task, f), JSON.stringify(expect, null, 2) + '\n');
    else fs.copyFileSync(path.join(src, f), path.join(task, f));
  }
  if (fs.existsSync(path.join(repo, 'node_modules'))) fs.symlinkSync(path.join(repo, 'node_modules'), path.join(ws, 'node_modules'), 'dir');
  const before = { rules: treeHash(ws, ['task', 'node_modules', '.cache']), inputs: fileHash(inputs.map((f) => path.join(task, f))) };

  console.log(`开始   ${id}`);
  const transcript = path.join(workRoot, `${id}.transcript.jsonl`);
  const cli = await runCli(ws, transcript, PROMPTS[vertical]);
  const { result, toolUses, readsOutsideWorkspace } = readTranscript(transcript, ws);

  const filmFile = path.join(task, 'film.json');
  const scenesFile = path.join(task, 'scenes.js');
  const delivered = fs.existsSync(filmFile);
  const scenes = fs.existsSync(scenesFile) ? fs.readFileSync(scenesFile, 'utf8') : null;
  const soundFile = path.join(task, 'sound.js');
  const sound = fs.existsSync(soundFile) ? fs.readFileSync(soundFile, 'utf8') : undefined;
  const logFile = path.join(task, 'out', 'runs.jsonl');
  const roundLog = fs.existsSync(logFile)
    ? fs.readFileSync(logFile, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l))
        .map((r) => ({ round: r.round, passed: r.passed, failed: r.failed, rendered: r.rendered, filmVersion: r.filmVersion }))
    : [];

  // Check the delivered film again against the case's own data and requirements.
  let verified = { passed: false, failed: ['(没有交付 film.json)'], durationSec: null };
  if (delivered) {
    try {
      const r = await runFilm(src, { film: JSON.parse(fs.readFileSync(filmFile, 'utf8')), scenes, sound: narrative ? sound ?? null : sound, expect, draft: true, log: false, outDir: path.join(workRoot, `${id}.verify`) });
      verified = { passed: r.passed, failed: r.failed, durationSec: r.durationSec };
    } catch (e) {
      verified = { passed: false, failed: [`(运行出错：${e.message.split('\n')[0]})`], durationSec: null };
    }
  }

  const usage = result?.modelUsage ?? {};
  const mainModel = Object.entries(usage).sort((a, b) => b[1].costUSD - a[1].costUSD)[0]?.[0] ?? model ?? 'unknown';
  const sum = (k) => Object.values(usage).reduce((a, u) => a + (u[k] ?? 0), 0);
  const record = {
    case: id,
    model: mainModel,
    vertical,
    delivered,
    customScene: Boolean(scenes),
    verified,
    pipelineRuns: roundLog.length,
    failedRuns: roundLog.filter((r) => !r.passed).length,
    filmVersions: new Set(roundLog.map((r) => r.filmVersion).filter(Boolean)).size || null,
    roundLog,
    agent: {
      finished: Boolean(result) && !result.is_error && (result.terminal_reason ?? 'completed') === 'completed',
      stopReason: !result
        ? `命令行退出码 ${cli.code}`
        : !result.is_error
          ? '完成'
          : `${result.terminal_reason ?? result.subtype}${result.api_error_status ? ` ${result.api_error_status}` : ''}：${String(result.result ?? '').split('\n')[0].slice(0, 80)}`,
      turns: result?.num_turns ?? null,
      toolUses,
      wallSec: result ? Math.round(result.duration_ms / 1000) : null,
      costUsd: result ? Math.round(result.total_cost_usd * 100) / 100 : null,
      tokens: { input: sum('inputTokens'), output: sum('outputTokens'), cacheRead: sum('cacheReadInputTokens'), cacheWrite: sum('cacheCreationInputTokens') },
      refusedActions: (result?.permission_denials ?? []).map((d) => `${d.tool_name}: ${JSON.stringify(d.tool_input).slice(0, 120)}`),
    },
    integrity: {
      rulesUntouched: treeHash(ws, ['task', 'node_modules', '.cache']) === before.rules,
      inputsUntouched: fileHash(inputs.map((f) => path.join(task, f))) === before.inputs,
      readsOutsideWorkspace,
    },
    report: result?.result ?? cli.stderr.slice(-600),
    files: { film: delivered ? filmFile : null, scenes: scenes ? scenesFile : null, sound: sound ? soundFile : null, runs: fs.existsSync(logFile) ? logFile : null },
  };
  record.outcome = outcomeOf(record);
  console.log(`${{ passed: '通过  ', failed: '未通过', interrupted: '中断  ', unchecked: '未自检' }[record.outcome]} ${id}  管线 ${record.pipelineRuns} 次，${record.agent.costUsd ?? '?'} 美元`);
  return record;
}

const summarizeOnly = value('--summarize');
const ids = summarizeOnly ? [] : briefDir ? [path.basename(briefDir)] : fs.readdirSync(casesDir).filter((d) => fs.existsSync(path.join(casesDir, d, 'brief.md'))).sort().filter((d) => !only || only.includes(d));
const records = new Array(ids.length);
let next = 0;
await Promise.all(
  Array.from({ length: Math.min(jobs, ids.length) }, async () => {
    while (next < ids.length) {
      const i = next++;
      records[i] = await runCase(ids[i]);
    }
  }),
);

// Save what the model delivered, and a summary.
let label = summarizeOnly ?? value('--label') ?? `${new Date().toISOString().slice(0, 10)}-${records[0]?.model ?? 'unknown'}`;
const date = label.match(/^\d{4}-\d{2}-\d{2}/)?.[0] ?? new Date().toISOString().slice(0, 10);
if (!summarizeOnly && !value('--label')) {
  // Never write over an earlier run's record.
  const base = label;
  for (let n = 2; fs.existsSync(path.join(here, 'agent-runs', label)); n++) label = `${base}-run${n}`;
}
const outDir = path.join(here, 'agent-runs', label);
for (const r of records) {
  const dir = path.join(outDir, r.case);
  fs.mkdirSync(dir, { recursive: true });
  if (r.files.film) fs.copyFileSync(r.files.film, path.join(dir, 'film.json'));
  if (r.files.scenes) fs.copyFileSync(r.files.scenes, path.join(dir, 'scenes.js'));
  if (r.files.sound) fs.copyFileSync(r.files.sound, path.join(dir, 'sound.js'));
  if (r.files.runs) fs.copyFileSync(r.files.runs, path.join(dir, 'runs.jsonl'));
  const { files, ...rest } = r;
  fs.writeFileSync(path.join(dir, 'result.json'), JSON.stringify(rest, null, 2) + '\n');
}

// The summary covers every case recorded under this label, so an interrupted case can be re-run alone.
const all = fs.readdirSync(outDir).filter((d) => fs.existsSync(path.join(outDir, d, 'result.json'))).sort()
  .map((d) => JSON.parse(fs.readFileSync(path.join(outDir, d, 'result.json'), 'utf8')));
const outcome = outcomeOf;
const perMinute = (r) => (r.agent.costUsd != null && r.verified.durationSec ? (r.agent.costUsd / (r.verified.durationSec / 60)).toFixed(2) : '');
const count = (o) => all.filter((r) => outcome(r) === o).length;
const clean = (r) => r.integrity.rulesUntouched && r.integrity.inputsUntouched && r.integrity.readsOutsideWorkspace.length === 0;
const verdict = (r) =>
  ({ interrupted: `中断：${r.agent.stopReason}`, failed: `未通过：${r.verified.failed.join('、')}`, unchecked: '未自检', passed: '通过' })[outcome(r)];
const md = [
  `# 无人值守运行：${label}`,
  '',
  `${count('passed')}/${all.length} 个用例由模型自己跑通自检，并通过复验${count('unchecked') ? `；${count('unchecked')} 个交付的影片能通过复验，但模型自己没有跑通自检` : ''}${count('failed') ? `；${count('failed')} 个未通过复验` : ''}${count('interrupted') ? `；${count('interrupted')} 个中途被打断，不计入结果` : ''}。模型只拿到简报、数据（叙事片没有）、要求和导演规范，看不到参考影片，全程没有人介入。`,
  '',
  `模型 ${all[0]?.model} · ${date} · 每个用例费用上限 ${budget} 美元`,
  '',
  '| 用例 | 结果 | 管线运行 | 其中未通过 | 分镜版本 | 写了场景代码 | 模型轮数 | 用时（秒） | 费用（美元） | 片长（秒） | 每分钟成片（美元） | 守规 |',
  '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |',
  ...all.map((r) =>
    `| ${r.case} | ${verdict(r)} | ${r.pipelineRuns} | ${r.failedRuns} | ${r.filmVersions ?? ''} | ${r.customScene ? '是' : ''} | ${r.agent.turns ?? ''} | ${r.agent.wallSec ?? ''} | ${r.agent.costUsd ?? ''} | ${r.verified.durationSec?.toFixed(1) ?? ''} | ${perMinute(r)} | ${clean(r) ? '是' : '否'} |`),
  '',
  '- **结果**：模型交付后，用用例原本的数据和要求重新跑一遍草稿渲染和全部自检，这叫复验。“通过”要求模型自己也跑通过草稿自检；片子能过复验但模型自己没跑通的记为“未自检”。模型没有正常结束的运行（用量限额、费用上限、超时）记为“中断”。',
  '- **管线运行**：模型自己调用管线的次数，含只查文字层的快速运行。',
  '- **分镜版本**：这些运行里实际出现过几版不同的 film.json；分镜没改就重跑的不算新版本。',
  '- **守规**：没有改动管线、规范、数据和要求，也没有读工作区以外的文件。',
  '- **费用**含命令行自身的系统提示开销，每次调用起步约 0.2 美元。',
  '',
  '## 模型自己的汇报',
  '',
  ...all.flatMap((r) => [`### ${r.case}`, '', ...String(r.report).trim().split('\n').map((l) => `> ${l}`), '']),
].join('\n');
fs.writeFileSync(path.join(outDir, 'SUMMARY.md'), md);
console.log(`\n${count('passed')}/${all.length} 通过${count('unchecked') ? `，${count('unchecked')} 个未自检` : ''}${count('interrupted') ? `，${count('interrupted')} 个被中断` : ''}。结果：${path.join(outDir, 'SUMMARY.md')}`);
if (!summarizeOnly) console.log(`工作区和完整对话记录：${workRoot}`);
process.exit(count('passed') === all.length ? 0 : 1);
