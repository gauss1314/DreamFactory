import fs from 'node:fs';
// Checks that read the encoded film and its audio mix.
import { LOUDNESS_TARGET, measureLevels } from '../lib/audio.mjs';
import { asrAvailable, compareSpeech, transcribe } from '../lib/asr.mjs';
import { run } from '../lib/util.mjs';

const fmtT = (t) => `${t.toFixed(1)}s`;

export const videoStillness = {
  id: 'video-stillness',
  title: '画面：没有黑屏，也没有长时间静止',
  tier: 'media',
  async run(ctx) {
    const limit = ctx.expect.maxFrozenSec ?? 6;
    const { stderr } = await run('ffmpeg', ['-hide_banner', '-nostats', '-i', ctx.video.file,
      // Judge stillness on a 64x36 copy: film grain and the slow push-in average away there,
      // while a subtitle changing or a chart growing still shows.
      '-vf', 'blackdetect=d=0.5:pix_th=0.03,scale=64:36:flags=area,freezedetect=n=0.0015:d=2', '-an', '-f', 'null', '-']);
    const problems = [];
    for (const m of stderr.matchAll(/black_start:([\d.]+) black_end:([\d.]+)/g)) {
      problems.push(`${fmtT(Number(m[1]))}–${fmtT(Number(m[2]))} 是黑屏`);
    }
    const starts = [...stderr.matchAll(/freeze_start: ([\d.]+)/g)].map((m) => Number(m[1]));
    const lengths = [...stderr.matchAll(/freeze_duration: ([\d.]+)/g)].map((m) => Number(m[1]));
    let longest = 0;
    starts.forEach((start, i) => {
      const len = lengths[i] ?? ctx.timeline.duration - start; // a freeze that runs to the end has no length logged
      longest = Math.max(longest, len);
      if (len >= limit) problems.push(`${fmtT(start)} 起画面静止 ${len.toFixed(1)} 秒，上限 ${limit} 秒`);
    });
    return {
      status: problems.length ? 'fail' : 'pass',
      summary: problems.length ? `${problems.length} 处问题` : `没有黑屏，最长静止 ${longest.toFixed(1)} 秒`,
      details: problems,
    };
  },
};

export const audioLevels = {
  id: 'audio-levels',
  title: '响度：整体响度和峰值在范围内',
  tier: 'media',
  async run(ctx) {
    if (!ctx.audio.audible) return { status: 'skip', summary: '没有声音（静音语音后端，也没有配乐）', details: [] };
    const { lufs, peak } = await measureLevels(ctx.audio.file);
    const problems = [];
    if (Math.abs(lufs - LOUDNESS_TARGET) > 2.5) problems.push(`整体响度 ${lufs} LUFS，目标 ${LOUDNESS_TARGET}±2.5`);
    if (peak > -1) problems.push(`峰值 ${peak} dBFS，上限 -1`);
    return {
      status: problems.length ? 'fail' : 'pass',
      summary: problems.length ? `${problems.length} 处问题` : `${lufs} LUFS，峰值 ${peak} dBFS`,
      details: problems,
    };
  },
};

export const audioGaps = {
  id: 'audio-gaps',
  title: '停顿：旁白之间没有过长的无声',
  tier: 'media',
  async run(ctx) {
    if (!ctx.audio.voiced) return { status: 'skip', summary: '没有人声（静音语音后端）', details: [] };
    const limit = ctx.expect.maxSilenceSec ?? 3.5;
    // listen to the narration alone: music under a pause would hide it
    const { stderr } = await run('ffmpeg', ['-hide_banner', '-nostats', '-i', ctx.audio.voiceFile ?? ctx.audio.file,
      '-af', 'silencedetect=noise=-45dB:d=2', '-f', 'null', '-']);
    const starts = [...stderr.matchAll(/silence_start: (-?[\d.]+)/g)].map((m) => Math.max(0, Number(m[1])));
    const lengths = [...stderr.matchAll(/silence_duration: ([\d.]+)/g)].map((m) => Number(m[1]));
    const problems = [];
    let longest = 0;
    starts.forEach((start, i) => {
      const len = lengths[i] ?? ctx.timeline.duration - start;
      longest = Math.max(longest, len);
      if (len >= limit) problems.push(`${fmtT(start)} 起无声 ${len.toFixed(1)} 秒，上限 ${limit} 秒`);
    });
    return {
      status: problems.length ? 'fail' : 'pass',
      summary: problems.length ? `${problems.length} 处问题` : `最长无声 ${longest.toFixed(1)} 秒`,
      details: problems,
    };
  },
};

export const asr = {
  id: 'asr',
  title: '听写核对：语音识别听到的内容和数字与字幕一致',
  tier: 'media',
  async run(ctx) {
    const skip = (summary) => ({ status: 'skip', summary, details: [] });
    if (!ctx.timeline.scenes.some((sc) => sc.lines.length)) return skip('影片没有旁白');
    if (!ctx.audio.voiced) return skip('没有人声（静音语音后端）');
    if (ctx.timeline.backend === 'espeak') return skip('espeak 的发音连语音识别都听不懂，只用来占位，不做核对');
    if (!(await asrAvailable())) return skip('没有安装语音识别，运行 pip install faster-whisper 后可用');
    const lines = ctx.timeline.scenes.flatMap((sc) => sc.lines);
    const heard = await transcribe(lines.map((l) => l.audio), ctx.resolved.lang);
    const clip = (t) => (t.length > 26 ? `${t.slice(0, 26)}…` : t);
    const problems = [];
    lines.forEach((line, i) => {
      const c = compareSpeech(line.display, heard[i]);
      if (c.missing.length) {
        problems.push(`字幕里的 ${c.missing.join('、')} 没有在语音里听到：字幕「${clip(line.display)}」，听到「${clip(heard[i])}」`);
      } else if (c.letters >= 4 && c.distance > 0.5) {
        // Homophones ("支" heard as "只") stay well under this; a different sentence does not.
        problems.push(`语音和字幕说的不是一回事：字幕「${clip(line.display)}」，听到「${clip(heard[i])}」`);
      }
    });
    return {
      status: problems.length ? 'fail' : 'pass',
      summary: problems.length ? `${problems.length} 处问题` : `${lines.length} 句旁白，听到的内容和数字都与字幕一致`,
      details: problems.slice(0, 12),
    };
  },
};

// ---------- checks for films with no text on screen ----------

/** Decode the film to small grey frames: one Float32Array per frame. */
async function greyFrames(file, w = 128, h = 72) {
  const { stdout } = await run('ffmpeg', ['-v', 'error', '-i', file, '-vf', `scale=${w}:${h}:flags=area,format=gray`, '-f', 'rawvideo', '-'], { binary: true });
  const size = w * h;
  const frames = [];
  for (let off = 0; off + size <= stdout.length; off += size) frames.push(stdout.subarray(off, off + size));
  return frames;
}

export const pops = {
  id: 'pops',
  title: '突跳：剪辑点和声明过的画面事件以外，画面没有一帧突然跳变',
  tier: 'media',
  async run(ctx) {
    const frames = await greyFrames(ctx.video.file);
    const fps = ctx.render.fps;
    const diff = [0];
    for (let i = 1; i < frames.length; i++) {
      let s = 0;
      for (let k = 0; k < frames[i].length; k++) s += Math.abs(frames[i][k] - frames[i - 1][k]);
      diff.push(s / frames[i].length);
    }
    const cuts = new Set(ctx.timeline.scenes.slice(1).map((sc) => Math.round(sc.start * fps)));
    // a declared event (a lamp coming on, a jolt) is a change the film means to make
    const declared = (ctx.audio.events ?? []).filter((e) => e.kind === 'declared').map((e) => e.t);
    const atEvent = (t) => declared.some((e) => t >= e - 1 / fps && t <= e + 0.3);
    // fades are meant to change every frame
    const fading = (t) => ctx.resolved.scenes.some((scene, k) => {
      const sc = ctx.timeline.scenes[k];
      return (scene.fadeIn && t >= sc.start && t <= sc.start + scene.fadeIn + 1 / fps) || (scene.fadeOut && t >= sc.end - scene.fadeOut - 1 / fps && t <= sc.end);
    });
    const problems = [];
    let worst = 0;
    for (let i = 1; i < diff.length; i++) {
      if ([i - 1, i, i + 1].some((k) => cuts.has(k)) || fading(i / fps) || atEvent(i / fps)) continue;
      const around = diff.slice(Math.max(1, i - 12), i + 13).filter((_, k, a) => k !== Math.min(i - 1, 12)).sort((a, b) => a - b);
      const typical = around[around.length >> 1] ?? 0;
      const ratio = diff[i] / Math.max(1, typical);
      worst = Math.max(worst, diff[i]);
      // A jump has to stand out from its own neighbourhood and be big enough to see.
      if (diff[i] > 6 && ratio > 4) problems.push(`${(i / fps).toFixed(2)}s 画面突然跳变（变化量 ${diff[i].toFixed(1)}，前后一般只有 ${typical.toFixed(1)}）`);
    }
    return {
      status: problems.length ? 'fail' : 'pass',
      summary: problems.length ? `${problems.length} 处突跳` : `剪辑点以外没有突跳（相邻两帧最大变化 ${worst.toFixed(1)}）`,
      details: problems.slice(0, 10),
    };
  },
};

function lab([r, g, b]) {
  const lin = (v) => {
    v /= 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  const [R, G, B] = [lin(r), lin(g), lin(b)];
  const f = (t) => (t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116);
  const x = f((0.4124 * R + 0.3576 * G + 0.1805 * B) / 0.9505);
  const y = f(0.2126 * R + 0.7152 * G + 0.0722 * B);
  const z = f((0.0193 * R + 0.1192 * G + 0.9505 * B) / 1.089);
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
}

export const palette = {
  id: 'palette',
  title: '色彩脚本：每个镜头的整体颜色符合脚本',
  tier: 'media',
  async run(ctx) {
    const script = ctx.expect.palette;
    if (!script) return { status: 'skip', summary: 'expect.json 没有写色彩脚本（palette）', details: [] };
    const tol = ctx.expect.paletteTolerance ?? 10;
    const problems = [];
    const seen = [];
    for (const sc of ctx.timeline.scenes) {
      const want = script[sc.id];
      if (!want) continue;
      const t = (sc.start + sc.end) / 2;
      const { stdout } = await run('ffmpeg', ['-v', 'error', '-ss', t.toFixed(3), '-i', ctx.video.file, '-frames:v', '1', '-vf', 'scale=1:1:flags=area', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { binary: true });
      const got = [stdout[0], stdout[1], stdout[2]];
      const a = lab(got);
      const b = lab(want.match(/[0-9a-f]{2}/gi).map((h) => parseInt(h, 16)));
      const dE = Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
      const hexGot = `#${got.map((v) => v.toString(16).padStart(2, '0')).join('')}`;
      seen.push(`${sc.id} ${hexGot}（差 ${dE.toFixed(1)}）`);
      if (dE > tol) problems.push(`${sc.id} 的整体颜色是 ${hexGot}，脚本是 ${want}，差 ${dE.toFixed(1)}，上限 ${tol}`);
    }
    return { status: problems.length ? 'fail' : 'pass', summary: problems.length ? `${problems.length} 个镜头跑色` : seen.join('；'), details: problems };
  },
};

export const cueSync = {
  id: 'cue-sync',
  title: '声画同步：每个画面事件都有声音，起点对准那一刻',
  tier: 'media',
  async run(ctx) {
    const events = Object.fromEntries((ctx.audio.events ?? []).map((e) => [e.name, e.t]));
    const names = Object.keys(events);
    if (!names.length) return { status: 'skip', summary: '影片没有声明画面事件', details: [] };
    const { readWav } = await import('../lib/wav.mjs');
    const S = await import('../lib/synth.mjs');
    const problems = [];
    const offsets = [];
    const stems = {};
    for (const name of names) {
      const cue = ctx.audio.cues.find((c) => c.name === name);
      if (!cue) {
        problems.push(`画面事件 ${name}（${events[name].toFixed(2)}s）没有对应的声音`);
        continue;
      }
      if (Math.abs(cue.t - events[name]) > 1e-6) problems.push(`${name} 的声音登记在 ${cue.t.toFixed(2)}s，画面在 ${events[name].toFixed(2)}s`);
      stems[cue.stem] ??= readWav(ctx.audio.stems[cue.stem]).samples;
      const x = stems[cue.stem];
      // band energy around the event, then the steepest rise within ±0.25 s
      const a = Math.max(0, S.n(events[name] - 0.5));
      const seg = new Float32Array(S.n(1.0));
      for (let i = 0; i < seg.length && a + i < x.length; i++) seg[i] = x[a + i] / 32768;
      const [lo, hi] = cue.band;
      const y = S.bandpass(seg, Math.sqrt(lo * hi), Math.sqrt(lo * hi) / (hi - lo));
      const hop = S.n(0.002);
      const env = [];
      for (let i = 0; i + hop <= y.length; i += hop) {
        let e = 0;
        for (let k = i; k < i + hop; k++) e += y[k] * y[k];
        env.push(10 * Math.log10(e / hop + 1e-12));
      }
      const t0 = events[name] - a / S.SR;
      let best = -1;
      let bestRise = 0;
      for (let i = 5; i < env.length; i++) {
        const tt = (i * hop) / S.SR;
        if (Math.abs(tt - t0) > 0.12) continue;
        const rise = env[i] - env[i - 5];
        if (rise > bestRise) {
          bestRise = rise;
          best = tt;
        }
      }
      if (best < 0 || bestRise < 6) {
        problems.push(`${name}：${events[name].toFixed(2)}s 前后 0.12 秒内听不到声音起来`);
        continue;
      }
      const off = best - t0;
      offsets.push(Math.abs(off));
      if (Math.abs(off) > 0.06) problems.push(`${name}：声音在 ${(events[name] + off).toFixed(2)}s 起来，画面在 ${events[name].toFixed(2)}s，差 ${Math.round(off * 1000)} 毫秒`);
    }
    return {
      status: problems.length ? 'fail' : 'pass',
      summary: problems.length ? `${problems.length} 处问题` : `${names.length} 个事件都对准了，最大偏差 ${Math.round(Math.max(0, ...offsets) * 1000)} 毫秒`,
      details: problems,
    };
  },
};

export const voiceOverMusic = {
  id: 'voice-over-music',
  title: '人声清楚：旁白比配乐和音效至少响 10 dB',
  tier: 'media',
  async run(ctx) {
    const lines = ctx.timeline.scenes.flatMap((sc) => sc.lines);
    if (!lines.length) return { status: 'skip', summary: '影片没有旁白', details: [] };
    if (!ctx.audio.stems?.music) return { status: 'skip', summary: '影片没有配乐和音效', details: [] };
    const { readWav } = await import('../lib/wav.mjs');
    const voice = readWav(ctx.audio.voiceFile).samples;
    const bed = [ctx.audio.stems.music, ctx.audio.stems.sfx].filter((f) => f && fs.existsSync(f)).map((f) => readWav(f).samples);
    const rms = (x, a, b) => {
      let e = 0;
      for (let i = a; i < b && i < x.length; i++) e += (x[i] / 32768) ** 2;
      return Math.sqrt(e / Math.max(1, b - a));
    };
    const SR = 48000;
    const problems = [];
    let worst = Infinity;
    for (const l of lines) {
      const a = Math.round(l.start * SR);
      const b = Math.round(l.end * SR);
      const v = rms(voice, a, b);
      // the bed is the music and effects summed
      let e = 0;
      for (let i = a; i < b; i++) {
        let s = 0;
        for (const x of bed) s += (x[i] ?? 0) / 32768;
        e += s * s;
      }
      const m = Math.sqrt(e / Math.max(1, b - a));
      const margin = 20 * Math.log10((v + 1e-9) / (m + 1e-9));
      worst = Math.min(worst, margin);
      if (margin < 10) problems.push(`${l.start.toFixed(1)}s「${l.display.slice(0, 16)}」旁白只比配乐响 ${margin.toFixed(1)} dB，至少要 10 dB`);
    }
    return {
      status: problems.length ? 'fail' : 'pass',
      summary: problems.length ? `${problems.length} 句旁白被配乐盖住` : `旁白比配乐至少响 ${worst.toFixed(1)} dB`,
      details: problems.slice(0, 8),
    };
  },
};
