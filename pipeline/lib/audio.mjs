// Narration mix: every clip is placed at its timeline position, then the track is brought to the
// loudness target without letting the peak past the ceiling.
import fs from 'node:fs';
import path from 'node:path';
import { run } from './util.mjs';
import { RATE, readWav, writeWav } from './wav.mjs';

export const LOUDNESS_TARGET = -14; // LUFS, integrated
export const PEAK_CEILING = -1.5; // dBFS

/** Integrated loudness and peak of an audio file, measured with ffmpeg's EBU R128 meter. */
export async function measureLevels(file) {
  const { stderr } = await run('ffmpeg', ['-nostats', '-hide_banner', '-i', file, '-af', 'ebur128=peak=true', '-f', 'null', '-']);
  const summary = stderr.slice(stderr.lastIndexOf('Summary:'));
  const lufs = Number((summary.match(/I:\s+(-?[\d.]+) LUFS/) || [])[1]);
  const peak = Number((summary.match(/Peak:\s+(-?[\d.]+) dBFS/) || [])[1]);
  return { lufs, peak };
}

/** Narration clips at their timeline positions, plus any music and effect stems, to the loudness target. */
export async function mixNarration({ timeline, outDir, stems = [] }) {
  const total = Math.round(timeline.duration * RATE);
  const mix = new Float32Array(total);
  let clips = 0;
  for (const scene of timeline.scenes) {
    for (const line of scene.lines) {
      const { samples, rate } = readWav(line.audio);
      if (rate !== RATE) throw new Error(`clip is ${rate} Hz, expected ${RATE}: ${line.audio}`);
      const at = Math.round(line.start * RATE);
      for (let i = 0; i < samples.length && at + i < total; i++) mix[at + i] += samples[i] / 32768;
      clips++;
    }
  }
  // the narration alone, for the checks that listen to the voice
  const voiceFile = path.join(outDir, 'audio', 'voice.wav');
  {
    const v = new Int16Array(total);
    for (let i = 0; i < total; i++) v[i] = Math.max(-32768, Math.min(32767, Math.round(mix[i] * 32767)));
    writeWav(voiceFile, v);
  }
  for (const stem of stems) for (let i = 0; i < Math.min(total, stem.length); i++) mix[i] += stem[i];
  const audible = clips > 0 || stems.length > 0;
  const file = path.join(outDir, 'audio', 'mix.wav');
  const save = (target, floats) => {
    const out = new Int16Array(total);
    for (let i = 0; i < total; i++) out[i] = Math.max(-32768, Math.min(32767, Math.round((floats[i] ?? 0) * 32767)));
    writeWav(target, out);
  };
  save(file, mix);
  if (!audible || (stems.length === 0 && timeline.backend === 'silent')) return { file, voiced: false, audible: false };

  const before = await measureLevels(file);
  if (!Number.isFinite(before.lufs)) return { file, voiced: false, audible: false };

  // Raise the voice to the target through a limiter: speech peaks sit far above its average level,
  // so plain gain would stop short. The limiter trims loudness a little, hence the second pass.
  const raw = path.join(outDir, 'audio', 'mix.raw.wav');
  fs.renameSync(file, raw);
  const limit = 10 ** ((PEAK_CEILING - 1) / 20); // 1 dB under the ceiling: the meter reads true peak
  let gainDb = LOUDNESS_TARGET - before.lufs;
  for (let pass = 0; pass < 4; pass++) {
    const levelIn = Math.min(64, 10 ** (gainDb / 20));
    await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', raw,
      '-af', `alimiter=level_in=${levelIn}:limit=${limit}:attack=5:release=60:level=false`,
      '-ar', String(RATE), '-ac', '1', '-c:a', 'pcm_s16le', file]);
    const off = LOUDNESS_TARGET - (await measureLevels(file)).lufs;
    if (Math.abs(off) <= 0.5) break;
    gainDb += off;
  }
  fs.rmSync(raw, { force: true });
  // Keep the track exactly as long as the timeline.
  const { samples } = readWav(file);
  if (samples.length !== total) {
    const fixed = new Int16Array(total);
    fixed.set(samples.subarray(0, Math.min(total, samples.length)));
    writeWav(file, fixed);
  }
  return { file, voiceFile, voiced: clips > 0 && timeline.backend !== 'silent', audible: true, gainDb: Math.round(gainDb * 10) / 10 };
}
