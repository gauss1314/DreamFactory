// Score and effects for "清晨的面包师": a felt-piano tune in F over a soft pad, 4/4 at 120;
// the street's small sounds on top: paws on stone, wheels on cobbles, the jolt, the bun, the pigeon.
export default function score({ synth: S, film, timeline, eventList }) {
  const dur = timeline.duration;
  const music = S.buffer(dur + 3);
  const sfx = S.buffer(dur + 3);
  const cues = [];
  const beat = 60 / (film.tempo || 120);
  const bar = beat * 4;

  // ---------- music ----------
  const chords = [
    ['F2', ['F3', 'A3', 'C4']],
    ['A2', ['E3', 'A3', 'C4']],
    ['Bb2', ['F3', 'Bb3', 'D4']],
    ['C3', ['G3', 'C4', 'E4']],
    ['D3', ['F3', 'A3', 'D4']],
    ['Bb2', ['F3', 'Bb3', 'D4']],
    ['F2', ['F3', 'A3', 'C4']],
  ];
  chords.forEach(([bass, pad], i) => {
    const t0 = i * bar;
    if (t0 >= dur) return;
    const last = i === chords.length - 1;
    for (const n of pad) S.place(music, S.strings(S.hz(n), last ? 1.6 : bar + 0.1, 0.07), t0, 1);
    S.place(music, S.pluck(S.hz(bass), 0.9, 0.55, 3 + i), t0, 0.55);
    if (!last) S.place(music, S.pluck(S.hz(bass) * 1.5, 0.6, 0.4, 7 + i), t0 + beat * 2, 0.4);
  });
  // melody, in beats
  const tune = [
    [1, 'A4', 0.45], [2, 'C5', 0.5], [3, 'F5', 0.55],
    [4, 'E5', 0.5], [5.5, 'C5', 0.45], [6, 'A4', 0.45], [7, 'C5', 0.4],
    [8, 'D5', 0.5], [9, 'F5', 0.55], [10, 'D5', 0.45], [11, 'Bb4', 0.45],
    [12, 'C5', 0.5], [13, 'E5', 0.5], [14.5, 'G5', 0.5],
    [16, 'F5', 0.55], [17.5, 'E5', 0.45], [18, 'D5', 0.5], [19, 'A4', 0.4],
    [20, 'D5', 0.45], [21, 'C5', 0.45], [22, 'Bb4', 0.4], [23, 'G4', 0.4],
    [24, 'A4', 0.4], [24, 'F4', 0.3], [25, 'C5', 0.35],
  ];
  for (const [b, n, v] of tune) if (b * beat < dur) S.place(music, S.piano(S.hz(n), beat * 1.6, v), b * beat, 0.5);
  // a light brush pulse while the cart rolls
  for (let b = 8; b < 18; b++) S.place(music, S.brush(b % 2 ? 0.16 : 0.1, 20 + b), b * beat + beat * 0.5, 0.5);
  // the bun's arc, as a rising and falling glock line
  const ev = Object.fromEntries(eventList.map((e) => [e.name, e.t]));
  const bump = ev['s2-track.bump'];
  const land = ev['s2-track.land'];
  if (bump !== undefined && land !== undefined) {
    const notes = ['C6', 'F6', 'A6', 'F6'];
    notes.forEach((n, i) => S.place(music, S.glock(S.hz(n), 0.4), bump + 0.08 + ((land - bump - 0.1) * i) / notes.length, 0.6));
  }
  // the pigeon's moment: two high bells
  const pland = ev['s3-pigeon.land'];
  if (pland !== undefined) {
    S.place(music, S.glock(S.hz('C6'), 0.3), pland + 0.25, 0.5);
    S.place(music, S.glock(S.hz('A5'), 0.3), pland + 0.5, 0.5);
  }
  // fade with the picture
  const fadeFrom = dur - 1.3;
  S.shape(music, (t) => (t < 0.4 ? t / 0.4 : t > fadeFrom ? Math.max(0, 1 - (t - fadeFrom) / 1.3) : 1));

  // ---------- effects ----------
  const declared = eventList.filter((e) => e.kind === 'declared').map((e) => e.t);
  const near = (t, w = 0.2) => declared.some((d) => Math.abs(d - t) < w && Math.abs(d - t) > 1e-9);
  const sceneOf = (t) => timeline.scenes.findIndex((sc) => t >= sc.start && t < sc.end);

  // morning air: a low, slow wind
  const wind = S.lowpass(S.noise(dur + 1, 77), (t) => 380 + 140 * Math.sin(t * 0.7));
  S.place(sfx, S.shape(wind, (t) => 0.05 * (0.7 + 0.3 * Math.sin(t * 0.9 + 1))), 0, 1);
  // a few far birds over the roofs in the wide shot
  const chirp = (f0, f1, len, seed) => {
    const out = S.buffer(len);
    let ph = 0;
    for (let i = 0; i < out.length; i++) {
      const t = i / S.SR;
      ph += (f0 + (f1 - f0) * (t / len)) / S.SR;
      out[i] = Math.sin(2 * Math.PI * ph) * Math.sin((Math.PI * t) / len);
    }
    return out;
  };
  for (const [t, f0, f1] of [[0.9, 3600, 4600], [1.05, 3900, 4800], [2.4, 4200, 3500], [3.1, 3700, 4700], [3.22, 3800, 4900]]) {
    S.place(sfx, chirp(f0, f1, 0.07, t * 10), t, 0.05);
  }

  const step = (seed, vel) => S.shape(S.lowpass(S.noise(0.09, seed), 1300), (t) => vel * Math.exp(-t * 55) * Math.min(1, t / 0.003));
  const clack = (seed, vel) => {
    const x = S.bandpass(S.noise(0.06, seed), 1100, 1.6);
    return S.shape(x, (t) => vel * Math.exp(-t * 80) * Math.min(1, t / 0.002));
  };
  const thunk = (vel, seed) => {
    const out = S.buffer(0.6);
    S.place(out, S.softKick(1), 0, 0.8);
    S.place(out, S.shape(S.bandpass(S.noise(0.3, seed), 220, 1.1), (t) => 2.2 * Math.exp(-t * 20) * Math.min(1, t / 0.002)), 0, 1);
    // the loaves knocking about in the box just after
    for (const [dt, v] of [[0.06, 0.5], [0.11, 0.35], [0.17, 0.25], [0.26, 0.15]]) S.place(out, S.shape(S.lowpass(S.noise(0.05, seed + dt * 100), 700), (t) => v * Math.exp(-t * 60)), dt, 1);
    return S.shape(out, () => vel);
  };
  const plop = (vel, seed) => {
    const out = S.buffer(0.3);
    S.place(out, S.shape(S.lowpass(S.noise(0.2, seed), 500), (t) => 1.6 * Math.exp(-t * 38) * Math.min(1, t / 0.002)), 0, 1);
    for (let i = 0; i < out.length; i++) {
      const t = i / S.SR;
      out[i] += 0.5 * Math.sin(2 * Math.PI * (110 + 60 * Math.exp(-t * 40)) * t) * Math.exp(-t * 28) * Math.min(1, t / 0.002);
    }
    return S.shape(out, () => vel);
  };
  const wingbeat = (vel, seed) => S.shape(S.bandpass(S.noise(0.08, seed), 1400, 0.7), (t) => vel * Math.exp(-t * 32) * Math.min(1, t / 0.003));
  const peck = (vel, seed) => {
    const out = S.shape(S.highpass(S.noise(0.025, seed), 2600), (t) => Math.exp(-t * 260));
    for (let i = 0; i < out.length; i++) {
      const t = i / S.SR;
      out[i] += 0.4 * Math.sin(2 * Math.PI * 3200 * t) * Math.exp(-t * 200);
    }
    return S.shape(out, () => vel);
  };
  const coo = () => {
    const out = S.buffer(0.42);
    let ph = 0;
    for (let i = 0; i < out.length; i++) {
      const t = i / S.SR;
      ph += (330 + 60 * Math.sin(t * 9) - t * 80) / S.SR;
      out[i] = (Math.sin(2 * Math.PI * ph) + 0.3 * Math.sin(4 * Math.PI * ph)) * Math.sin((Math.PI * t) / 0.42) ** 1.5;
    }
    return S.lowpass(out, 900);
  };

  let k = 0;
  for (const e of eventList) {
    k++;
    const n = e.name;
    const sc = sceneOf(e.t);
    if (e.kind === 'step') {
      if (near(e.t)) continue;
      S.place(sfx, step(100 + k, [0.05, 0.16, 0.11][sc] ?? 0.1), e.t, 1);
    } else if (e.kind === 'rattle') {
      if (near(e.t)) continue;
      S.place(sfx, clack(300 + k, [0.04, 0.12, 0.08][sc] ?? 0.08), e.t, 1);
    } else if (e.kind === 'thump') {
      S.place(sfx, thunk(0.22, 500 + k), e.t, 1);
    } else if (e.kind === 'tap') {
      // the bun's little bounce coming down again
      S.place(sfx, plop(0.22, 900 + k), e.t, 1);
    } else if (e.kind === 'flap') {
      S.place(sfx, wingbeat(0.16, 600 + k), e.t, 1);
    } else if (e.kind === 'coo') {
      S.place(sfx, coo(), e.t, 0.06);
    } else if (e.kind === 'peck' && e.minor) {
      S.place(sfx, peck(0.18, 700 + k), e.t, 1);
    } else if (n.endsWith('s2-track.bump')) {
      S.place(sfx, thunk(0.5, 800), e.t, 1);
      cues.push({ name: n, t: e.t, stem: 'sfx', band: [60, 300] });
    } else if (n.endsWith('s2-track.land')) {
      S.place(sfx, plop(0.55, 810), e.t, 1);
      cues.push({ name: n, t: e.t, stem: 'sfx', band: [80, 400] });
    } else if (n.endsWith('s3-pigeon.land')) {
      // the braking flurry as it touches down
      [[0, 0.42], [0.085, 0.34], [0.17, 0.26], [0.255, 0.16]].forEach(([dt, v], i) => S.place(sfx, wingbeat(v, 820 + i), e.t + dt, 1));
      cues.push({ name: n, t: e.t, stem: 'sfx', band: [700, 3000] });
    } else if (n.endsWith('s3-pigeon.peck')) {
      S.place(sfx, peck(0.32, 830), e.t, 1);
      cues.push({ name: n, t: e.t, stem: 'sfx', band: [2500, 8000] });
    }
  }
  S.shape(sfx, (t) => (t > dur - 1.0 ? Math.max(0, (dur - t) / 1.0) : 1));
  return { music: S.room(music, 0.3).subarray(0, S.n(dur)), sfx: sfx.subarray(0, S.n(dur)), cues };
}
