// One run of the pipeline for one film: script -> timeline -> picture -> self-check -> film.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { hash, probe, readJson, writeJson } from './lib/util.mjs';
import { resolveFilm } from './lib/data.mjs';
import { pickBackend } from './lib/tts.mjs';
import { buildTimeline } from './lib/timeline.mjs';
import { mixNarration } from './lib/audio.mjs';
import * as synth from './lib/synth.mjs';
import { writeWav } from './lib/wav.mjs';
import { openStage, sampleFilm } from './lib/stage.mjs';
import { renderVideo } from './lib/render.mjs';
import { runChecks } from './checks/index.mjs';

const VERTICALS = {
  'data-story': () => import('../verticals/data-story/vertical.mjs'),
  narrative: () => import('../verticals/narrative/vertical.mjs'),
};

/**
 * @param {string} filmDir  holds film.json, data.json and optionally expect.json
 * @param {object} opts     draft, video (false = text-level checks only), tts, only, outDir,
 *                          film/data/expect (in-memory overrides, used by the evals), log (false = no run log),
 *                          scenes (source of custom scene code; null = none; default: scenes.js in filmDir),
 *                          sound (source of the score and effects; null = none; default: sound.js in filmDir)
 */
// Everything the picture depends on: the resolved film (its sound settings aside), the film's scene
// code, the vertical's runtime and the renderer itself. Same key, same frames.
function pictureKey(resolved, scenesSource, vertical) {
  const { music, ...picture } = resolved;
  const files = [];
  const walk = (d) => {
    for (const name of fs.readdirSync(d).sort()) {
      const p = path.join(d, name);
      if (fs.statSync(p).isDirectory()) walk(p);
      else files.push(name, fs.readFileSync(p, 'utf8'));
    }
  };
  walk(vertical.runtimeDir);
  const renderer = fs.readFileSync(new URL('./lib/render.mjs', import.meta.url), 'utf8');
  return hash(JSON.stringify([picture, scenesSource ?? '', files, renderer]));
}

export async function runFilm(filmDir, opts = {}) {
  const started = Date.now();
  const film = opts.film ?? readJson(path.join(filmDir, 'film.json'));
  const dataFile = path.join(filmDir, 'data.json');
  const data = opts.data ?? (fs.existsSync(dataFile) ? readJson(dataFile) : {});
  const expectFile = path.join(filmDir, 'expect.json');
  const expect = opts.expect ?? (fs.existsSync(expectFile) ? readJson(expectFile) : {});
  const outDir = opts.outDir ?? path.join(filmDir, 'out');
  const draft = Boolean(opts.draft);

  const loadVertical = VERTICALS[film.vertical ?? 'data-story'];
  if (!loadVertical) throw new Error(`unknown vertical "${film.vertical}"`);
  const vertical = await loadVertical();
  // DF_TIMING=1 prints how long each stage took, to stderr
  let lap = Date.now();
  const timing = (stage) => {
    if (process.env.DF_TIMING) process.stderr.write(`[timing] ${path.basename(opts.outDir ?? filmDir)} ${stage} ${((Date.now() - lap) / 1000).toFixed(1)}s\n`);
    lap = Date.now();
  };

  // Script -> timeline. Narration is synthesized here; its length sets the pace.
  const resolved = resolveFilm(film, data);
  // A film may bring its own scene code: scenes.js next to film.json.
  const scenesFile = path.join(filmDir, 'scenes.js');
  const scenesSource = opts.scenes !== undefined ? opts.scenes : fs.existsSync(scenesFile) ? fs.readFileSync(scenesFile, 'utf8') : null;
  resolved.customScenes = Boolean(scenesSource);
  const backend = pickBackend(opts.tts ?? film.voice?.backend);
  const timeline = await buildTimeline({ resolved, outDir, backend, vertical, fps: vertical.fps ?? 30 });
  resolved.timeline = timeline;
  timing('timeline');
  writeJson(path.join(outDir, 'build', 'film.resolved.json'), resolved);
  let soundHash = '';
  const builtScenes = path.join(outDir, 'build', 'scenes.js');
  if (scenesSource) fs.writeFileSync(builtScenes, scenesSource);
  else fs.rmSync(builtScenes, { force: true });
  // Open the picture first: it reports the moments its actions happen, and the sound is placed on them.
  const contactFile = path.join(outDir, 'contact.jpg');
  const stage = await openStage({ outDir, vertical, draft });
  let sampling;
  let video = null;
  let audio;
  try {
    const pageEvents = await stage.page.evaluate(() => (window.DF.events ? window.DF.events.map((e) => ({ ...e })) : []));
    const declared = Object.entries(eventTimes(resolved, timeline)).map(([name, t]) => ({ name, t, kind: 'declared' }));
    const eventList = [...declared, ...pageEvents].sort((x, y) => x.t - y.t);

    // Score and effects: the film's own sound.js, else the vertical's, unless the film says "music": false.
    const soundFile = path.join(filmDir, 'sound.js');
    const verticalSound = film.music !== false && vertical.soundFile && fs.existsSync(vertical.soundFile) ? fs.readFileSync(vertical.soundFile, 'utf8') : null;
    const soundSource = opts.sound !== undefined ? opts.sound : fs.existsSync(soundFile) ? fs.readFileSync(soundFile, 'utf8') : verticalSound;
    soundHash = hash(soundSource ?? '');
    let sound = null;
    if (soundSource) {
      const built = path.join(outDir, 'build', 'sound.mjs');
      fs.writeFileSync(built, soundSource);
      const render = (await import(`${pathToFileURL(built).href}?v=${hash(soundSource)}`)).default;
      sound = await render({ synth, film: resolved, timeline, events: Object.fromEntries(eventList.map((e) => [e.name, e.t])), eventList });
      for (const stem of ['music', 'sfx']) if (sound[stem]) writeWav(path.join(outDir, 'audio', `${stem}.wav`), toInt16(sound[stem], timeline.duration));
    }
    audio = await mixNarration({ timeline, outDir, stems: sound ? [sound.music, sound.sfx].filter(Boolean) : [] });
    audio.cues = sound?.cues ?? [];
    audio.events = eventList.filter((e) => !e.minor);
    timing('open+sound+mix');
    audio.stems = sound ? { music: path.join(outDir, 'audio', 'music.wav'), sfx: path.join(outDir, 'audio', 'sfx.wav') } : {};

    // Picture: read the text back from the live page, then render if asked.
    sampling = await sampleFilm(stage, timeline, { contactFile });
    timing('sample');
    if (opts.video !== false) {
      video = await renderVideo(stage, timeline, { outDir, draft, audioFile: audio.audible ? audio.file : null, cacheKey: pictureKey(resolved, scenesSource, vertical) });
    }
    timing('render');
  } finally {
    await stage.close();
  }

  const ctx = {
    film, resolved, data, expect, timeline, sampling, audio, video, vertical,
    render: video && { width: video.width, height: video.height, fps: video.fps },
    media: video ? await probe(video.file) : null,
  };
  const checks = await runChecks(ctx, { only: opts.only ?? vertical.checks, timing: process.env.DF_TIMING ? timing : null });
  timing('checks');
  const failed = checks.filter((c) => c.status === 'fail').map((c) => c.id);

  const report = {
    title: resolved.title ?? path.basename(filmDir),
    passed: failed.length === 0,
    failed,
    durationSec: timeline.duration,
    backend,
    draft,
    rendered: Boolean(video),
    wallSec: Math.round((Date.now() - started) / 100) / 10,
    checks,
    files: { film: video?.file ?? null, contact: sampling.sheetFrames ? contactFile : null },
  };
  if (opts.log !== false) {
    const logFile = path.join(outDir, 'runs.jsonl');
    const prior = fs.existsSync(logFile) ? fs.readFileSync(logFile, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)) : [];
    const entry = {
      at: new Date().toISOString(),
      round: prior.length + 1,
      filmVersion: hash(JSON.stringify(film) + (scenesSource ?? '') + soundHash),
      passed: report.passed,
      failed,
      draft,
      rendered: report.rendered,
      durationSec: timeline.duration,
      wallSec: report.wallSec,
      costUsd: opts.costUsd ?? null,
      intervention: opts.intervention ?? null,
    };
    fs.appendFileSync(logFile, JSON.stringify(entry) + '\n');
    report.round = entry.round;
    report.interventions = [...prior, entry].filter((e) => e.intervention).length;
  }
  writeJson(path.join(outDir, 'report.json'), report);
  fs.writeFileSync(path.join(outDir, 'report.md'), renderReport(report));
  return report;
}

const MARK = { pass: '通过', fail: '未通过', skip: '跳过' };

export function renderReport(r) {
  const lines = [
    `# 自检报告：${r.title}`,
    '',
    r.passed ? '**结论：通过。**' : `**结论：未通过，${r.failed.length} 项检查失败。**`,
    '',
    [
      `片长 ${r.durationSec.toFixed(1)} 秒`,
      `语音后端 ${r.backend}`,
      r.draft ? '草稿画质' : '成片画质',
      r.rendered ? '已渲染视频' : '未渲染视频，只做了文字层检查',
      r.round ? `第 ${r.round} 轮` : null,
      r.round ? `人工介入 ${r.interventions} 次` : null,
    ].filter(Boolean).join(' · '),
    '',
    '| 检查 | 结果 | 说明 |',
    '| --- | --- | --- |',
    ...r.checks.map((c) => `| ${c.title} | ${MARK[c.status]} | ${c.summary} |`),
  ];
  const broken = r.checks.filter((c) => c.status === 'fail');
  if (broken.length) {
    lines.push('', '## 需要修的地方', '');
    for (const c of broken) {
      lines.push(`- **${c.id}**：${c.summary}`);
      for (const d of c.details) lines.push(`  - ${d}`);
    }
  }
  if (r.files.contact) lines.push('', `抽帧图：${r.files.contact}`);
  if (r.files.film) lines.push(`成片：${r.files.film}`);
  return lines.join('\n') + '\n';
}

/** Every event a film declares, in seconds from the start of the film: { 's2-side.jolt': 7.8, ... }. */
export function eventTimes(resolved, timeline) {
  const out = {};
  resolved.scenes.forEach((scene, i) => {
    for (const [name, t] of Object.entries(scene.events ?? {})) {
      for (const [k, v] of (Array.isArray(t) ? t : [t]).entries()) {
        out[Array.isArray(t) ? `${scene.id}.${name}.${k + 1}` : `${scene.id}.${name}`] = timeline.scenes[i].start + v;
      }
    }
  });
  return out;
}

function toInt16(x, duration) {
  const total = Math.round(duration * synth.SR);
  const out = new Int16Array(total);
  for (let i = 0; i < Math.min(total, x.length); i++) out[i] = Math.max(-32768, Math.min(32767, Math.round(x[i] * 32767)));
  return out;
}
