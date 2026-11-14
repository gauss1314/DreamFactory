// Speech suppliers. Each backend turns one line of text into a 48 kHz mono WAV.
// Adding a supplier = one function here; nothing else in the pipeline knows which one ran.
import fs from 'node:fs';
import path from 'node:path';
import { hasCommand, hash, run } from './util.mjs';
import { RATE, readWav, writeWav } from './wav.mjs';

const VOICES = {
  espeak: { zh: 'cmn', en: 'en-us' },
  edge: { zh: 'zh-CN-XiaoxiaoNeural', en: 'en-US-AriaNeural' },
};

// espeak-ng speed setting. Its Mandarin is slow at the default; 280 lands near 4.5 characters a second.
const ESPEAK_SPEED = { zh: '280', en: '170' };

/** "auto" picks the offline engine when it is installed, else a silent track with estimated timing. */
export function pickBackend(requested) {
  if (requested && requested !== 'auto') return requested;
  return hasCommand('espeak-ng') ? 'espeak' : 'silent';
}

/** Rough speaking time, used only by the silent backend. */
function estimateSeconds(text) {
  const cjk = (text.match(/[㐀-鿿]/g) || []).length;
  const words = (text.match(/[A-Za-z0-9]+/g) || []).length;
  const pauses = (text.match(/[，。？！；、,.?!;]/g) || []).length;
  return Math.max(0.8, cjk / 4.5 + words / 2.7 + pauses * 0.15);
}

const toWav = (src, dst) =>
  run('ffmpeg', ['-y', '-loglevel', 'error', '-i', src, '-ar', String(RATE), '-ac', '1', '-c:a', 'pcm_s16le', dst]);

const backends = {
  async silent({ text, outFile }) {
    writeWav(outFile, new Int16Array(Math.round(estimateSeconds(text) * RATE)));
  },
  async espeak({ text, voice, lang, outFile }) {
    const tmp = outFile + '.raw.wav';
    await run('espeak-ng', ['-v', voice, '-s', ESPEAK_SPEED[lang] ?? '170', '-w', tmp, text]);
    await toWav(tmp, outFile);
    fs.rmSync(tmp, { force: true });
  },
  // Not exercised in the environment this was built in (the service was unreachable there).
  async edge({ text, voice, outFile }) {
    const tmp = outFile + '.mp3';
    await run('edge-tts', ['--voice', voice, '--text', text, '--write-media', tmp]);
    await toWav(tmp, outFile);
    fs.rmSync(tmp, { force: true });
  },
};

/** Synthesize one line. Clips are cached by backend, voice and text. Returns the file and its length. */
export async function synth({ backend, lang, voice, text, dir }) {
  const fn = backends[backend];
  if (!fn) throw new Error(`unknown speech backend "${backend}" (have: ${Object.keys(backends).join(', ')})`);
  const v = voice ?? VOICES[backend]?.[lang] ?? '';
  const speed = backend === 'espeak' ? ESPEAK_SPEED[lang] ?? '170' : '';
  const outFile = path.join(dir, `${hash([backend, v, speed, lang, text].join('|'))}.wav`);
  if (!fs.existsSync(outFile)) {
    fs.mkdirSync(dir, { recursive: true });
    await fn({ text, voice: v, lang, outFile });
  }
  const { samples, rate } = readWav(outFile);
  return { file: outFile, duration: samples.length / rate };
}
