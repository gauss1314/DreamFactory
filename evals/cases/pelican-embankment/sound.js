// "Pelican on the embankment": score and sound effects, rendered from the film's own timeline.
// Picture and sound read the same event times from film.json, so a bell rung on screen rings here.
//
// Music: D major, 100 bpm. The cuts fall on beats 8 and 17; the bell on beat 19; the egrets on 20.
// A felt-piano tune over plucked nylon guitar, a soft pulse once the bike gets going, strings that
// open with the sunset, and a glockenspiel answer to the bicycle bell.

export default function score({ synth: S, film, timeline, events }) {
  const dur = timeline.duration;
  const beat = 60 / (film.tempo ?? 100);
  const music = S.buffer(dur + 3);
  const sfx = S.buffer(dur + 3);
  const cues = [];
  const cut = timeline.scenes.map((s) => s.start);

  // ---------------- music ----------------
  const chords = [
    ['D3', 'A3', 'D4', 'F#4'], // bar 1
    ['B2', 'F#3', 'B3', 'D4'], // bar 2
    ['G2', 'D3', 'G3', 'B3'], // bar 3: the side shot starts
    ['A2', 'E3', 'A3', 'C#4'], // bar 4
    ['F#2', 'D3', 'A3', 'D4'], // bar 5: the sunset
    ['G2', 'D3', 'G3', 'B3'], // bar 6: egrets
    ['D2', 'A2', 'D3', 'F#3'], // bar 7: home
  ];
  const bar = (k) => k * 4 * beat;
  // guitar: a rolling arpeggio in eighths, quieter in the wide, fuller in the side shot
  const roll = [0, 2, 1, 3, 2, 1, 3, 2];
  chords.forEach((ch, k) => {
    for (let e = 0; e < 8; e++) {
      const t = bar(k) + e * (beat / 2);
      if (t > dur - 0.6) break;
      const vel = (k === 0 ? 0.35 : k < 2 ? 0.45 : 0.55) * (e % 2 ? 0.8 : 1);
      S.place(music, S.pluck(S.hz(ch[roll[e]]) * 2, beat * 0.9, vel, 7 + k * 8 + e), t + (e % 2 ? 0.012 : 0), 0.32);
    }
  });
  // piano tune, entering in bar 2 (beats are counted from the start of the film)
  const tune = [
    [4, 'A4', 1], [5, 'F#4', 0.5], [5.5, 'G4', 0.5], [6, 'A4', 1.5], [7.5, 'D5', 0.5],
    [8, 'B4', 1], [9, 'A4', 0.5], [9.5, 'G4', 0.5], [10, 'F#4', 1.5], [11.5, 'E4', 0.5],
    [12, 'E4', 1], [13, 'F#4', 0.5], [13.5, 'G4', 0.5], [14, 'A4', 1], [15, 'C#5', 1],
    [16, 'D5', 2], [18, 'A4', 0.5], [18.5, 'B4', 0.5],
    [20, 'D5', 1], [21, 'E5', 1], [22, 'F#5', 3],
  ];
  for (const [b, note, len] of tune) {
    const t = b * beat;
    S.place(music, S.piano(S.hz(note), len * beat, b >= 20 ? 0.8 : 0.65), t, 0.42);
  }
  // soft pulse while riding: kick on 1 and 3, brush on 2 and 4, from the side shot to the egrets
  for (let b = 8; b < 22; b++) {
    const t = b * beat;
    if (b % 2 === 0) S.place(music, S.softKick(0.55), t, 0.5);
    else S.place(music, S.brush(0.35, 100 + b), t, 0.5);
  }
  // strings open with the sunset and swell under the egrets
  const pad = [[0, 4, ['D3', 'A3'], 0.18], [4, 4, ['B2', 'F#3'], 0.2], [16, 4, ['F#3', 'D4', 'A4'], 0.3], [20, 6, ['G3', 'B3', 'D4', 'G4'], 0.38], [22, 4, ['D3', 'A3', 'F#4', 'D5'], 0.42]];
  for (const [b, len, notes, vel] of pad) for (const nt of notes) S.place(music, S.strings(S.hz(nt), len * beat, vel), b * beat, 0.3);
  // the glockenspiel answers the bicycle bell, a beat later
  const bells = Object.entries(events).filter(([k]) => k.includes('.bell')).map(([, t]) => t);
  if (bells.length) {
    const t0 = bells.at(-1) + beat;
    ['D6', 'A5', 'F#6'].forEach((nt, i) => S.place(music, S.glock(S.hz(nt), 0.5), t0 + i * beat * 0.5, 0.6));
  }
  const wet = S.room(music, 0.3, { size: 1.1, damp: 0.4 });

  // ---------------- effects ----------------
  // shot levels: far in the wide, close in the side shot, receding at the sunset
  const near = (t) => (t < cut[1] ? 0.25 : t < cut[2] ? 1 : 0.6 * (1 - 0.6 * ((t - cut[2]) / (dur - cut[2]))));
  // wind and the river, under everything
  const wind = S.shape(S.bandpass(S.noise(dur, 1), (t) => 500 + 300 * Math.sin(t * 0.7), 0.6), (t) => 0.22 + 0.08 * Math.sin(t * 1.3) + (t < cut[1] ? 0.08 : 0));
  S.place(sfx, wind, 0, 0.6);
  const river = S.shape(S.lowpass(S.highpass(S.noise(dur, 2), 250), 1800), (t) => (t < cut[1] || t >= cut[2] ? 0.14 : 0.07) * (1 + 0.2 * Math.sin(t * 2.1)));
  S.place(sfx, river, 0, 0.6);
  // tyres on gravel: a hiss with a crackle of small stones, as loud as the shot is close
  const roll2 = S.shape(S.bandpass(S.noise(dur, 3), 2600, 0.7), (t) => 0.22 * near(t));
  S.place(sfx, roll2, 0, 1);
  const r = S.rng(4);
  for (let t = 0.1; t < dur; t += 0.012 + r() * 0.03) {
    const click = S.shape(S.highpass(S.noise(0.01, 50 + Math.floor(t * 100)), 2500), (u) => Math.exp(-u * 900));
    S.place(sfx, click, t, 0.45 * near(t) * r());
  }
  // pedal strokes: a soft chain tick at each downstroke, on the picture's own crank
  const cadence = film.cadence ?? 1.2;
  timeline.scenes.forEach((sc) => {
    for (let k = 0; ; k++) {
      // the crank passes a downstroke every half turn
      const t = sc.start + (k + 0.25) * (cadence / 2);
      if (t >= sc.end) break;
      const tick = S.shape(S.bandpass(S.noise(0.05, 300 + k), 1800, 3), (u) => Math.exp(-u * 120));
      S.place(sfx, tick, t, 0.5 * near(t));
    }
  });
  // the stone: a thump, then the basket and the bell rattling
  for (const [name, t] of Object.entries(events)) {
    if (name.endsWith('.jolt')) {
      S.place(sfx, S.lowpass(S.softKick(1), 400), t, 0.9);
      const rattle = S.shape(S.bandpass(S.noise(0.35, 7), 3200, 2), (u) => Math.exp(-u * 12) * (0.6 + 0.4 * Math.sin(u * 140)));
      S.place(sfx, rattle, t + 0.02, 0.6);
      S.place(sfx, S.bell(2300, 0.25, 9), t + 0.03, 0.5);
      cues.push({ name, t, stem: 'sfx', band: [60, 400] });
    }
    if (name.includes('.bell.')) {
      // a thumb lever: each strike damps the ring a little before it rings again
      const ring = S.bell(2350, 0.9, 10 + cues.length);
      const next = Object.values(events).find((u) => u > t && u - t < 0.5 && u !== t);
      // the thumb pulls the lever back just before the next strike, which stops the ring
      if (next) S.shape(ring, (u) => (u < next - t - 0.04 ? 1 : 0.12));
      S.place(sfx, ring, t, 1.2);
      cues.push({ name, t, stem: 'sfx', band: [3500, 8000] });
    }
    if (name.endsWith('.birds')) {
      // eight egrets, each with its own wingbeat
      // take-off: reeds thrashing and a sharp first wing clap, on the event itself
      const clap = S.shape(S.bandpass(S.noise(0.12, 600), 1000, 0.9), (u) => Math.min(1, u / 0.004) * Math.exp(-u * 30));
      S.place(sfx, clap, t, 3.2);
      const rustle = S.shape(S.highpass(S.noise(0.6, 601), 1800), (u) => Math.min(1, u / 0.01) * Math.exp(-u * 5));
      S.place(sfx, rustle, t, 0.35);
      const br = S.rng(11);
      for (let b = 0; b < 8; b++) {
        const t0 = t + (b === 0 ? 0.08 : 0.05 + br() * 0.3);
        const rate = 2.6 + br() * 0.8;
        for (let k = 0; k < 7; k++) {
          const flap = S.shape(S.bandpass(S.noise(0.16, 500 + b * 10 + k), 700 + br() * 500, 1.2), (u) => Math.sin(Math.min(1, u / 0.16) * Math.PI) ** 2);
          S.place(sfx, flap, t0 + k / rate, 0.9 * Math.exp(-k * 0.18));
        }
      }
      cues.push({ name, t, stem: 'sfx', band: [800, 1300] });
    }
  }
  // fade both stems at the very end with the picture
  const fadeFrom = dur - 1.0;
  for (const x of [wet, sfx]) for (let i = Math.round(fadeFrom * S.SR); i < x.length; i++) x[i] *= Math.max(0, 1 - (i / S.SR - fadeFrom) / 1.0);
  // fade the ambience in with the picture
  for (let i = 0; i < Math.round(0.6 * S.SR); i++) sfx[i] *= i / (0.6 * S.SR);

  return { music: wet.subarray(0, S.n(dur)), sfx: sfx.subarray(0, S.n(dur)), cues };
}
