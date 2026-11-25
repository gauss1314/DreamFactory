// Sound from code. Instruments and effects are built from physical descriptions (strings, bars,
// bells, air, gravel), every noise source is seeded, and the same score renders the same samples
// on every run. Mono, 48 kHz, float in -1..1.
import { RATE } from './wav.mjs';

export const SR = RATE;
export const n = (sec) => Math.max(0, Math.round(sec * SR));
export const buffer = (sec) => new Float32Array(n(sec));
export const db = (d) => 10 ** (d / 20);

/** Seeded uniform random in [0, 1). */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const NOTE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
/** "A4" -> 440, "F#3", "Bb2". */
export function hz(name) {
  const m = /^([A-G])([#b]?)(-?\d)$/.exec(name);
  if (!m) throw new Error(`bad note name "${name}"`);
  const semis = NOTE[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0) + (Number(m[3]) + 1) * 12;
  return 440 * 2 ** ((semis - 69) / 12);
}

/** Mix src into dst starting at time t (seconds), scaled by gain. */
export function place(dst, src, t, gain = 1) {
  const at = n(t);
  for (let i = 0; i < src.length && at + i < dst.length; i++) if (at + i >= 0) dst[at + i] += src[i] * gain;
  return dst;
}

// ---------- filters ----------
export function lowpass(x, cutoff) {
  const y = new Float32Array(x.length);
  const f = typeof cutoff === 'function' ? cutoff : () => cutoff;
  let s = 0;
  for (let i = 0; i < x.length; i++) {
    const a = 1 - Math.exp((-2 * Math.PI * f(i / SR)) / SR);
    s += a * (x[i] - s);
    y[i] = s;
  }
  return y;
}

export function highpass(x, cutoff) {
  const lp = lowpass(x, cutoff);
  for (let i = 0; i < x.length; i++) lp[i] = x[i] - lp[i];
  return lp;
}

/** Resonant band-pass (RBJ biquad), constant 0 dB peak gain. */
export function bandpass(x, center, q = 1) {
  const y = new Float32Array(x.length);
  const fc = typeof center === 'function' ? center : () => center;
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < x.length; i++) {
    const w = (2 * Math.PI * fc(i / SR)) / SR;
    const alpha = Math.sin(w) / (2 * q);
    const a0 = 1 + alpha;
    const b0 = alpha / a0, b2 = -alpha / a0, a1 = (-2 * Math.cos(w)) / a0, a2 = (1 - alpha) / a0;
    const v = b0 * x[i] + b2 * x2 - a1 * y1 - a2 * y2;
    x2 = x1; x1 = x[i]; y2 = y1; y1 = v;
    y[i] = v;
  }
  return y;
}

export function noise(sec, seed) {
  const r = rng(seed);
  const b = buffer(sec);
  for (let i = 0; i < b.length; i++) b[i] = r() * 2 - 1;
  return b;
}

/** Multiply by an envelope function of time (seconds). */
export function shape(x, env) {
  for (let i = 0; i < x.length; i++) x[i] *= env(i / SR);
  return x;
}

export const adsr = (a, d, s, r, len) => (t) =>
  t < a ? t / a : t < a + d ? 1 - (1 - s) * ((t - a) / d) : t < len ? s : Math.max(0, s * (1 - (t - len) / r));

// ---------- instruments ----------
/**
 * Felt piano: a few slightly stretched partials, each with its own decay, a soft hammer thump,
 * and a felt-damped top end.
 */
export function piano(freq, dur, vel = 0.8) {
  const tail = 1.2;
  const out = buffer(dur + tail);
  const B = 0.00035; // string stiffness
  for (let k = 1; k <= 10; k++) {
    const f = freq * k * Math.sqrt(1 + B * k * k);
    if (f > 9000) break;
    const amp = (vel / k ** 1.25) * (k === 1 ? 1 : 0.7);
    const decay = 1.6 / (1 + 0.45 * k) + 0.25;
    const ph = k * 1.37;
    for (let i = 0; i < out.length; i++) {
      const t = i / SR;
      const release = t > dur ? Math.exp(-(t - dur) * 9) : 1;
      out[i] += amp * Math.sin(2 * Math.PI * f * t + ph) * Math.exp(-t / decay) * release * Math.min(1, t / 0.004);
    }
  }
  const thump = lowpass(noise(0.03, Math.round(freq)), 900);
  place(out, shape(thump, (t) => Math.exp(-t * 120)), 0, 0.25 * vel);
  return lowpass(out, 2600 + 2400 * vel);
}

/** Plucked nylon string (Karplus-Strong with a soft pick). */
export function pluck(freq, dur, vel = 0.7, seed = 1) {
  const out = buffer(dur + 0.8);
  const period = SR / freq;
  const N = Math.max(2, Math.floor(period));
  const frac = period - N;
  const r = rng(seed + Math.round(freq * 10));
  const line = new Float32Array(N + 1);
  for (let i = 0; i <= N; i++) line[i] = (r() * 2 - 1) * vel;
  // a soft pick: smooth the initial burst
  for (let p = 0; p < 3; p++) for (let i = 1; i <= N; i++) line[i] = 0.5 * (line[i] + line[i - 1]);
  let idx = 0;
  const damp = 0.996;
  for (let i = 0; i < out.length; i++) {
    const a = line[idx];
    const b = line[(idx + 1) % (N + 1)];
    const v = a + frac * (b - a);
    out[i] = v;
    line[idx] = damp * 0.5 * (a + b);
    idx = (idx + 1) % (N + 1);
    if (i / SR > dur) line[idx] *= 0.995;
  }
  return lowpass(out, 3800);
}

/** A held string section: detuned saws through a slowly opening filter. */
export function strings(freq, dur, vel = 0.4) {
  const out = buffer(dur + 0.6);
  const voices = [-7, -2.5, 2.5, 7].map((c) => freq * 2 ** (c / 1200));
  for (const [j, f] of voices.entries()) {
    let ph = j * 0.21;
    for (let i = 0; i < out.length; i++) {
      const t = i / SR;
      const vib = 1 + 0.0025 * Math.sin(2 * Math.PI * 5.2 * t + j);
      ph += (f * vib) / SR;
      out[i] += ((ph % 1) * 2 - 1) * 0.25;
    }
  }
  const env = adsr(0.35, 0.3, 0.85, 0.5, dur);
  return shape(lowpass(out, (t) => 900 + 1400 * Math.min(1, t / 1.2)), (t) => env(t) * vel);
}

/** Modal bell. Partials of a small bicycle bell, each with its own ring time. */
export function bell(freq, vel = 0.8, seed = 3) {
  const modes = [[1, 1, 1.6], [2.32, 0.7, 1.1], [4.25, 0.45, 0.8], [6.63, 0.3, 0.5], [9.38, 0.18, 0.3], [1.004, 0.6, 1.5]];
  const out = buffer(1.9);
  for (const [ratio, amp, ring] of modes) {
    const f = freq * ratio;
    for (let i = 0; i < out.length; i++) {
      const t = i / SR;
      out[i] += amp * Math.sin(2 * Math.PI * f * t) * Math.exp(-t / ring) * Math.min(1, t / 0.0008);
    }
  }
  // the striker hitting the dome: a bright click that cuts through the previous ring
  const strike = highpass(noise(0.012, seed), 3500);
  place(out, shape(strike, (t) => Math.exp(-t * 500)), 0, 2.2);
  return shape(out, () => vel * 0.3);
}

/** Glockenspiel: a struck bar, bright and short. */
export function glock(freq, vel = 0.5) {
  const out = buffer(1.4);
  for (const [ratio, amp, ring] of [[1, 1, 0.9], [2.76, 0.35, 0.35], [5.4, 0.15, 0.15]]) {
    for (let i = 0; i < out.length; i++) {
      const t = i / SR;
      out[i] += amp * Math.sin(2 * Math.PI * freq * ratio * t) * Math.exp(-t / ring) * Math.min(1, t / 0.0006);
    }
  }
  return shape(out, () => vel * 0.35);
}

/** Soft kick and brushed snare for a light pulse. */
export function softKick(vel = 0.6) {
  const out = buffer(0.4);
  let ph = 0;
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    ph += (55 + 70 * Math.exp(-t * 30)) / SR;
    out[i] = Math.sin(2 * Math.PI * ph) * Math.exp(-t * 9) * vel;
  }
  return out;
}

export function brush(vel = 0.3, seed = 9) {
  const x = bandpass(noise(0.25, seed), 4200, 0.7);
  return shape(x, (t) => vel * Math.exp(-t * 18) * Math.min(1, t / 0.006));
}

// ---------- room ----------
/** A small Schroeder reverb: parallel combs into series all-passes. Returns the wet signal only. */
export function reverb(x, { size = 1, damp = 0.35, tail = 2.2 } = {}) {
  const out = new Float32Array(x.length + n(tail));
  const combs = [1557, 1617, 1491, 1422, 1277, 1356].map((d) => Math.round(d * size * (SR / 44100)));
  for (const d of combs) {
    const buf = new Float32Array(d);
    let idx = 0;
    let lp = 0;
    const fb = 0.8;
    for (let i = 0; i < out.length; i++) {
      const y = buf[idx];
      lp = y * (1 - damp) + lp * damp;
      buf[idx] = (i < x.length ? x[i] : 0) + lp * fb;
      idx = (idx + 1) % d;
      out[i] += y / combs.length;
    }
  }
  for (const d of [225, 556, 441, 341].map((v) => Math.round(v * (SR / 44100)))) {
    const buf = new Float32Array(d);
    let idx = 0;
    const g = 0.5;
    for (let i = 0; i < out.length; i++) {
      const bv = buf[idx];
      const v = -g * out[i] + bv;
      buf[idx] = out[i] + g * v;
      idx = (idx + 1) % d;
      out[i] = v;
    }
  }
  return out;
}

/** Sum of the dry signal and its room. */
export function room(x, wet = 0.25, opts) {
  const w = reverb(x, opts);
  const out = new Float32Array(w.length);
  for (let i = 0; i < out.length; i++) out[i] = (i < x.length ? x[i] : 0) + w[i] * wet;
  return out;
}

export function peak(x) {
  let p = 0;
  for (let i = 0; i < x.length; i++) p = Math.max(p, Math.abs(x[i]));
  return p;
}
