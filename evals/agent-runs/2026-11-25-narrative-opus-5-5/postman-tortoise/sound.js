// A small waltz in F (3/4), soft rain that thins out, and the tortoise's own sounds.
export default function score({ synth: S, film, timeline, eventList }) {
  const dur = timeline.duration;
  const beat = 60 / (film.tempo ?? 135);
  const bar = beat * 3;
  const music = S.buffer(dur + 3);
  const sfx = S.buffer(dur + 3);
  const cues = [];

  // ---------- the waltz ----------
  const chords = [
    ['F2', ['A3', 'C4', 'F4']],
    ['D2', ['A3', 'D4', 'F4']],
    ['Bb1', ['Bb3', 'D4', 'F4']],
    ['C2', ['G3', 'C4', 'E4']],
    ['F2', ['A3', 'C4', 'F4']],
    ['A1', ['A3', 'C4', 'E4']],
    ['Bb1', ['Bb3', 'D4', 'F4']],
    ['C2', ['G3', 'Bb3', 'E4']],
    ['F2', ['A3', 'C4', 'F4']],
  ];
  chords.forEach(([root, tones], i) => {
    const t0 = i * bar;
    const soft = i === 0 ? 0.6 : 1;
    S.place(music, S.pluck(S.hz(root), bar * 0.9, 0.7, i + 1), t0, 0.55 * soft);
    if (i < 8) {
      for (const b of [1, 2]) for (const n of tones) S.place(music, S.piano(S.hz(n), beat * 0.7, 0.32), t0 + b * beat, 0.11 * soft);
    } else {
      for (const n of tones) S.place(music, S.piano(S.hz(n), bar * 1.5, 0.3), t0, 0.12);
    }
    // a string pad underneath, thicker toward the end
    S.place(music, S.strings(S.hz(tones[0]), bar, 0.16), t0, i >= 6 ? 0.32 : 0.2);
    S.place(music, S.strings(S.hz(tones[2]), bar, 0.12), t0, i >= 6 ? 0.26 : 0.14);
  });
  // melody: [bar, beat, note, beats]
  const tune = [
    [1, 0, 'A4', 2], [1, 2, 'F4', 1],
    [2, 0, 'D5', 1], [2, 1, 'C5', 1], [2, 2, 'Bb4', 1],
    [3, 0, 'A4', 2], [3, 2, 'G4', 1],
    [4, 0, 'A4', 1], [4, 1, 'C5', 1], [4, 2, 'F5', 1],
    [5, 0, 'E5', 3],
    [6, 0, 'D5', 1], [6, 1, 'C5', 1], [6, 2, 'Bb4', 1],
    [7, 0, 'A4', 1], [7, 1, 'G4', 1], [7, 2, 'E4', 1],
    [8, 0, 'F4', 3],
  ];
  for (const [b, k, n, len] of tune) S.place(music, S.piano(S.hz(n), len * beat * 0.92, 0.55), b * bar + k * beat, 0.42);

  // ---------- rain, thinning out as it stops ----------
  const rainLevel = (t) => (t < 8.3 ? 1 : Math.max(0.1, 1 - (t - 8.3) / 2.4));
  {
    let r = S.highpass(S.highpass(S.noise(dur, 71), 1500), 1500);
    r = S.lowpass(r, 6500);
    S.shape(r, (t) => 0.05 * rainLevel(t));
    S.place(sfx, r, 0, 1);
    // drops on the stones and on the water
    const rr = S.rng(72);
    for (let t = 0.05; t < dur; t += 0.08 + rr() * 0.3) {
      if (rr() > rainLevel(t)) continue;
      const f = 1800 + rr() * 1800;
      const n = S.buffer(0.05);
      for (let i = 0; i < n.length; i++) {
        const u = i / S.SR;
        n[i] = Math.sin(2 * Math.PI * f * (1 + u * 6) * u) * Math.exp(-u * 90);
      }
      S.place(sfx, n, t, 0.04 + rr() * 0.04);
    }
  }

  // ---------- the tortoise and the things it touches ----------
  const pat = (seed) => {
    const thud = S.shape(S.lowpass(S.noise(0.08, seed), 420), (u) => Math.exp(-u * 55) * Math.min(1, u / 0.002));
    const wet = S.shape(S.highpass(S.noise(0.03, seed + 1), 3000), (u) => Math.exp(-u * 220));
    S.place(thud, wet, 0.004, 0.25);
    return thud;
  };
  let k = 0;
  for (const ev of eventList) {
    if (ev.kind === 'step') {
      const far = ev.name.startsWith('s1-');
      S.place(sfx, pat(100 + k++), ev.t, far ? 0.35 : 0.9);
    } else if (ev.kind === 'drip') {
      // water gathering and leaving the leaf's edge: a tiny tick
      S.place(sfx, S.shape(S.highpass(S.noise(0.01, 300), 4000), (u) => Math.exp(-u * 400)), ev.t, 0.08);
    } else if (ev.kind === 'splash') {
      const n = S.buffer(0.08);
      for (let i = 0; i < n.length; i++) {
        const u = i / S.SR;
        n[i] = Math.sin(2 * Math.PI * 1400 * (1 + u * 9) * u) * Math.exp(-u * 60);
      }
      S.place(sfx, n, ev.t, 0.22);
    } else if (ev.name === 's2-side.post') {
      // paper sliding into the slot, then the flap snapping shut and the letter landing inside
      const swish = S.shape(S.highpass(S.highpass(S.noise(0.2, 400), 2600), 2600), (u) => 0.5 * Math.sin(Math.PI * Math.min(1, u / 0.2)) ** 2);
      S.place(sfx, swish, ev.t - 0.2, 0.5);
      const clack = S.buffer(0.4);
      for (let i = 0; i < clack.length; i++) {
        const u = i / S.SR;
        clack[i] = (Math.sin(2 * Math.PI * 430 * u) * 0.8 + Math.sin(2 * Math.PI * 710 * u) * 0.5) * Math.exp(-u * 38) * Math.min(1, u / 0.001)
          + Math.sin(2 * Math.PI * 150 * u) * Math.exp(-u * 18) * 0.5 * Math.min(1, u / 0.002);
      }
      S.place(clack, S.shape(S.lowpass(S.noise(0.04, 401), 1200), (u) => Math.exp(-u * 120)), 0, 0.6);
      S.place(sfx, clack, ev.t, 0.9);
      cues.push({ name: ev.name, t: ev.t, stem: 'sfx', band: [150, 900] });
    } else if (ev.name === 's3-lamp.lamp') {
      // the lamp catching: a soft low whump, a flicker, then a faint hum
      const whump = S.buffer(0.6);
      for (let i = 0; i < whump.length; i++) {
        const u = i / S.SR;
        whump[i] = Math.sin(2 * Math.PI * (70 + 50 * Math.exp(-u * 20)) * u) * Math.exp(-u * 9) * Math.min(1, u / 0.002);
      }
      S.place(whump, S.shape(S.lowpass(S.noise(0.3, 500), 380), (u) => Math.exp(-u * 14) * Math.min(1, u / 0.002)), 0, 0.7);
      S.place(sfx, whump, ev.t, 1.0);
      for (const dt of [0.1, 0.17]) S.place(sfx, S.shape(S.highpass(S.noise(0.015, 501 + dt * 100), 3000), (u) => Math.exp(-u * 300)), ev.t + dt, 0.12);
      const hum = S.buffer(dur - ev.t);
      for (let i = 0; i < hum.length; i++) {
        const u = i / S.SR;
        hum[i] = (Math.sin(2 * Math.PI * 100 * u) + 0.4 * Math.sin(2 * Math.PI * 200 * u)) * Math.min(1, u / 0.6) * 0.03;
      }
      S.place(sfx, hum, ev.t + 0.3, 1);
      // and in the score, a little glockenspiel answering the light
      ['C6', 'E6', 'G6', 'C7'].forEach((n, j) => S.place(music, S.glock(S.hz(n), 0.5), ev.t + 0.12 + j * beat * 0.5, 0.5));
      cues.push({ name: ev.name, t: ev.t, stem: 'sfx', band: [60, 400] });
    }
  }

  // everything fades with the picture
  const fadeFrom = dur - 1.0;
  const fade = (x) => S.shape(x, (t) => (t < fadeFrom ? 1 : Math.max(0, 1 - (t - fadeFrom) / 1.0)));
  return {
    music: fade(S.room(music, 0.3).subarray(0, S.n(dur))),
    sfx: fade(S.room(sfx, 0.1).subarray(0, S.n(dur))),
    cues,
  };
}
