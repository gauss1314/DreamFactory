// Score and effects for 清晨的面包师: a felt-piano tune in F, 4/4 at 120, over pizzicato bass and a soft string bed.
export default function score({ synth: S, film, timeline, eventList }) {
  const dur = timeline.duration;
  const music = S.buffer(dur + 3);
  const sfx = S.buffer(dur + 3);
  const cues = [];
  const beat = 60 / (film.tempo ?? 120);
  const at = (b) => b * beat;

  // ---------------------------------------------------------------- music
  // [beat, note, length in beats, velocity]
  const tune = [
    [0, 'A4', 1, 0.5], [1, 'C5', 1, 0.5], [2, 'F5', 1.5, 0.6], [3.5, 'E5', 0.5, 0.45],
    [4, 'D5', 1, 0.5], [5, 'C5', 1, 0.48], [6, 'G4', 2, 0.45],
    [8, 'A4', 0.5, 0.5], [8.5, 'Bb4', 0.5, 0.45], [9, 'C5', 1, 0.5], [10, 'D5', 1, 0.52], [11, 'F5', 1, 0.55],
    [12, 'D5', 1, 0.5], [14.5, 'Bb4', 0.5, 0.42], [15, 'C5', 1, 0.45],
    [16, 'A4', 1, 0.45], [17, 'C5', 1, 0.45], [18, 'F5', 1, 0.5], [19, 'E5', 1, 0.45],
    [20, 'D5', 1, 0.45], [21, 'C5', 0.5, 0.42], [21.5, 'Bb4', 0.5, 0.4], [22, 'A4', 1, 0.42], [23, 'G4', 1, 0.4],
    [24, 'F4', 2, 0.42],
  ];
  for (const [b, nm, len, v] of tune) S.place(music, S.piano(S.hz(nm), at(len) * 0.95, v), at(b), 0.55);
  const bars = [
    ['F2', 'C3', ['F3', 'A3', 'C4']],
    ['E2', 'G2', ['E3', 'G3', 'C4']],
    ['D2', 'A2', ['D3', 'F3', 'A3']],
    ['Bb1', 'F2', ['D3', 'F3', 'Bb3']],
    ['F2', 'C3', ['F3', 'A3', 'C4']],
    ['C2', 'G2', ['E3', 'G3', 'Bb3']],
    ['F2', 'C3', ['F3', 'A3', 'C4']],
  ];
  bars.forEach(([root, fifth, chord], i) => {
    const b0 = i * 4;
    if (at(b0) >= dur) return;
    S.place(music, S.pluck(S.hz(root), at(1.5), 0.7, 11 + i), at(b0), 0.55);
    if (at(b0 + 2) < dur) S.place(music, S.pluck(S.hz(fifth), at(1.5), 0.6, 21 + i), at(b0 + 2), 0.45);
    for (const nm of chord) S.place(music, S.strings(S.hz(nm), Math.min(at(4), dur - at(b0)), 0.07), at(b0), 1);
  });
  // a light brush pulse while the cart rolls close by (shot 2)
  for (let b = 8; b < 18; b++) if (b % 2 === 1) S.place(music, S.brush(0.18, 30 + b), at(b), 1);
  // mickey-mousing: a glockenspiel run as the bun flies, a little figure for each peck
  const ev = Object.fromEntries(eventList.map((e) => [e.name, e.t]));
  const bump = ev['s2-side.bump'];
  ['C6', 'E6', 'G6', 'C7'].forEach((nm, k) => S.place(music, S.glock(S.hz(nm), 0.5), bump + 0.06 + k * 0.1, 0.8));
  S.place(music, S.glock(S.hz('F5'), 0.5), ev['s2-side.land'], 0.7);
  for (const k of [1, 2]) S.place(music, S.glock(S.hz(k === 1 ? 'A6' : 'F6'), 0.4), ev[`s3-end.peck.${k}`] + 0.02, 0.6);
  // follow the picture's fade at the end
  const fadeFrom = dur - 1.0;
  for (let i = S.n(fadeFrom); i < music.length; i++) music[i] *= Math.max(0, 1 - (i / S.SR - fadeFrom) / 1.0);

  // ---------------------------------------------------------------- effects
  const shotOf = (t) => (t < 4 ? 0 : t < 9 ? 1 : 2);
  const near = [0.25, 1, 0.55]; // the wide shot is mostly air; close up, the baker's own sounds
  // air: a soft morning breeze, a little louder in the wide shot
  {
    const wind = S.bandpass(S.noise(dur + 1, 3), (t) => 420 + 160 * Math.sin(t * 0.7), 0.6);
    S.shape(wind, (t) => 0.05 * (t < 4 ? 1 : 0.45) * (0.7 + 0.3 * Math.sin(t * 1.3 + 1)));
    S.place(sfx, S.highpass(wind, 250), 0, 1);
    // distant birds waking in the wide shot
    const rb = S.rng(17);
    for (const t0 of [0.7, 1.15, 2.3, 2.45, 3.2]) {
      const len = 0.07 + rb() * 0.05;
      const f0 = 3600 + rb() * 900;
      const ch = S.buffer(len);
      let ph = 0;
      for (let i = 0; i < ch.length; i++) {
        const u = i / ch.length;
        ph += (f0 * (1 + 0.25 * Math.sin(u * Math.PI))) / S.SR;
        ch[i] = Math.sin(2 * Math.PI * ph) * Math.sin(Math.PI * u) * 0.03;
      }
      S.place(sfx, ch, t0, 1);
    }
  }
  const step = (seed) => {
    const x = S.bandpass(S.noise(0.1, seed), 780, 0.9);
    return S.shape(x, (t) => Math.min(1, t / 0.004) * Math.exp(-t * 45));
  };
  const clatter = (len, seed) => {
    // wooden wheels on cobbles: a dry tick for each stone, over a low rumble
    const out = S.buffer(len + 0.2);
    const r = S.rng(seed);
    for (let t = 0.02; t < len; t += 0.07 + r() * 0.08) {
      const tick = S.shape(S.bandpass(S.noise(0.05, seed + Math.round(t * 1000)), 900 + r() * 500, 2), (u) => Math.exp(-u * 70));
      S.place(out, tick, t, 0.35 + r() * 0.4);
    }
    const rum = S.shape(S.bandpass(S.noise(len, seed + 1), 520, 0.8), (t) => 0.12 * Math.min(1, t / 0.08, (len - t) / 0.08));
    S.place(out, rum, 0, 1);
    return out;
  };
  const clunk = (v, seed) => {
    // a wooden wheel knocking up over a stone, the box rattling after
    const out = S.buffer(0.6);
    S.place(out, S.softKick(1), 0, 0.9 * v);
    const knock = S.buffer(0.3);
    for (let i = 0; i < knock.length; i++) {
      const t = i / S.SR;
      knock[i] = (Math.sin(2 * Math.PI * 165 * t) * 0.8 + Math.sin(2 * Math.PI * 240 * t) * 0.4) * Math.exp(-t * 22) * Math.min(1, t / 0.0015);
    }
    S.place(out, knock, 0, 0.8 * v);
    for (const [dt, g] of [[0.07, 0.3], [0.13, 0.22], [0.2, 0.15]]) {
      S.place(out, S.shape(S.bandpass(S.noise(0.06, seed + dt * 100), 1100, 1.5), (t) => Math.exp(-t * 60)), dt, g * v);
    }
    return out;
  };
  const thud = (v, seed) => {
    // a soft bun meeting stone: a dull, low pat
    const out = S.buffer(0.3);
    for (let i = 0; i < out.length; i++) {
      const t = i / S.SR;
      out[i] = Math.sin(2 * Math.PI * (120 + 60 * Math.exp(-t * 40)) * t) * Math.exp(-t * 30) * Math.min(1, t / 0.0015);
    }
    S.place(out, S.shape(S.lowpass(S.noise(0.08, seed), 380), (t) => Math.exp(-t * 50) * Math.min(1, t / 0.0015)), 0, 1.6);
    return S.shape(out, () => v);
  };
  const flap = (v, seed) => S.shape(S.bandpass(S.noise(0.16, seed), 700, 0.6), (t) => v * Math.sin(Math.PI * Math.min(1, t / 0.16)) ** 2);
  const perch = (v, seed) => {
    // feet on stone and a last snap of the wings
    const out = S.buffer(0.3);
    // the first snap carries the moment; the claw ticks after it stay well under it
    S.place(out, S.shape(S.highpass(S.noise(0.1, seed), 1600), (t) => Math.min(1, t / 0.0008) * Math.exp(-t * 40)), 0, 1.6);
    for (const dt of [0.05, 0.09]) S.place(out, S.shape(S.bandpass(S.noise(0.03, seed + dt * 1000), 3400, 2), (t) => Math.exp(-t * 140)), dt, 0.18);
    return S.shape(out, () => v);
  };
  const peck = (v, seed) => {
    const x = S.bandpass(S.noise(0.05, seed), 4300, 2.5);
    return S.shape(x, (t) => v * Math.min(1, t / 0.0008) * Math.exp(-t * 110));
  };

  for (const e of eventList) {
    const k = shotOf(e.t);
    if (e.kind === 'step') S.place(sfx, step(Math.round(e.t * 100)), e.t, 0.32 * near[k]);
    else if (e.kind === 'roll') S.place(sfx, clatter(e.len, Math.round(e.t * 10) + 5), e.t, 0.4 * near[k] * (e.level ?? 1));
    else if (e.kind === 'clunk') S.place(sfx, clunk(0.45, 61), e.t, 1);
    else if (e.kind === 'bounce') S.place(sfx, thud(0.25, 62), e.t, 1);
    else if (e.kind === 'flap') S.place(sfx, flap(0.22, Math.round(e.t * 100)), e.t, 1);
  }
  const declared = [
    ['s2-side.bump', clunk(0.7, 71), [60, 300]],
    ['s2-side.land', thud(0.75, 72), [60, 300]],
    ['s3-end.land', perch(0.25, 73), [1500, 6000]],
    ['s3-end.peck.1', peck(0.5, 74), [2500, 7000]],
    ['s3-end.peck.2', peck(0.45, 75), [2500, 7000]],
  ];
  for (const [name, snd, band] of declared) {
    const t = ev[name];
    S.place(sfx, snd, t, 1);
    cues.push({ name, t, stem: 'sfx', band });
  }
  for (let i = S.n(fadeFrom); i < sfx.length; i++) sfx[i] *= Math.max(0, 1 - (i / S.SR - fadeFrom) / 1.0);
  return { music: S.room(music, 0.3).subarray(0, S.n(dur)), sfx: S.room(sfx, 0.08).subarray(0, S.n(dur)), cues };
}
