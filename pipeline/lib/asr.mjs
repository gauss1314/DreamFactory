// Listening back: transcribe the narration clips and compare what was heard with the script.
// Speech recognition is optional (pip install faster-whisper); without it the check is skipped.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { extractNumbers } from './data.mjs';
import { cacheDir } from './tts.mjs';
import { run } from './util.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const MODEL = process.env.DF_ASR_MODEL ?? 'small';

let available;
export async function asrAvailable() {
  if (available === undefined) {
    available = await run('python3', ['-c', 'import faster_whisper, numpy']).then(() => true, () => false);
  }
  return available;
}

/** Transcripts for a list of clips, in order. Each transcript is cached next to its clip. */
export async function transcribe(files, lang) {
  const cached = (f) => `${f}.${MODEL}.${lang}.txt`;
  const todo = [...new Set(files.filter((f) => !fs.existsSync(cached(f))))];
  if (todo.length) {
    const { stdout } = await run('python3', [path.join(here, '..', 'tools', 'asr.py')], { input: JSON.stringify({ model: MODEL, lang, files: todo }) });
    const { texts } = JSON.parse(stdout);
    todo.forEach((f, i) => fs.writeFileSync(cached(f), texts[i]));
  }
  return files.map((f) => fs.readFileSync(cached(f), 'utf8'));
}

const CN_DIGIT = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
const CN_UNIT = { 十: 10, 百: 100, 千: 1000 };
const EN_WORD = { zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12 };

/** "两千七百九十三" -> 2793, "十七" -> 17, "二七九三" -> 2793, "五点五" -> 5.5 */
export function chineseNumber(s) {
  const [whole, frac] = s.split('点');
  let value = 0;
  if (!/[十百千万亿]/.test(whole)) {
    value = whole ? Number([...whole].map((c) => CN_DIGIT[c]).join('')) : 0;
  } else {
    let total = 0;
    let section = 0;
    let digit = 0;
    for (const c of whole) {
      if (c in CN_DIGIT) digit = CN_DIGIT[c];
      else if (c in CN_UNIT) {
        section += (digit || 1) * CN_UNIT[c];
        digit = 0;
      } else {
        total += (section + digit) * (c === '万' ? 1e4 : 1e8);
        section = 0;
        digit = 0;
      }
    }
    value = total + section + digit;
  }
  if (frac) value += Number(`0.${[...frac].map((c) => CN_DIGIT[c] ?? '').join('')}`);
  return value;
}

/** Every number a transcript contains, whether written as digits, Chinese numerals or small English words. */
export function heardNumbers(text) {
  const out = extractNumbers(text).map((n) => n.value);
  for (const m of text.matchAll(/[零〇一二两三四五六七八九十百千万亿点]+/g)) {
    const v = chineseNumber(m[0].replace(/^点+|点+$/g, ''));
    if (Number.isFinite(v)) out.push(v);
  }
  for (const m of text.toLowerCase().matchAll(/[a-z]+/g)) if (m[0] in EN_WORD) out.push(EN_WORD[m[0]]);
  return out;
}

/** The words of a sentence without numbers, punctuation or spacing, for a like-for-like comparison. */
const wording = (s) => s.toLowerCase().replace(/[零〇一二两三四五六七八九十百千万亿点\d%％]/g, '').replace(/[^\p{Script=Han}a-z]/gu, '');

function editDistance(a, b) {
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[b.length];
}

/**
 * Compare one subtitle with what was heard.
 * missing: numbers in the subtitle that were not heard. distance: 0 = same wording, 1 = nothing in common.
 */
export function compareSpeech(subtitle, heard) {
  const said = heardNumbers(heard);
  const missing = extractNumbers(subtitle).filter((n) => !said.some((v) => Math.abs(v - n.value) < 1e-9)).map((n) => n.raw);
  const a = [...wording(subtitle)];
  const b = [...wording(heard)];
  const distance = Math.max(a.length, b.length) ? editDistance(a, b) / Math.max(a.length, b.length) : 0;
  return { missing, distance, letters: a.length };
}
