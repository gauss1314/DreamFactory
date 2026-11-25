// "The postman after the rain": score and effects.
// A waltz in A minor at 90 bpm (a bar is two seconds, so every cut falls on a bar line). It turns
// to C major when the lamp comes on, and ends on C. Rain under everything, thinning to nothing.
// Footsteps come from the picture's own footfalls; the letter and the lamp from film.json.

export default function score({ synth: S, film, timeline, events, eventList }) {
  const dur = timeline.duration;
  const beat = 60 / (film.tempo ?? 90);
  const bar = 3 * beat;
  const music = S.buffer(dur + 3);
  const sfx = S.buffer(dur + 3);
  const cues = [];

  // ---------------- music ----------------
  const chords = [
    ['A2', 'C4', 'E4'], ['F2', 'A3', 'C4'], ['C3', 'E4', 'G4'], ['G2', 'B3', 'D4'], ['C3', 'E4', 'G4'], ['F2', 'C4', 'A4'], ['C2', 'G3', 'E4'],
  ];
  chords.forEach((ch, k) => {
    const t0 = k * bar;
    if (t0 >= dur) return;
    const last = k === chords.length - 1 || t0 + bar >= dur;
    // oom-pah-pah: a low pluck on one, the chord plucked on two and three
    S.place(music, S.pluck(S.hz(ch[0]), beat * 0.9, 0.6, 3 + k), t0, 0.45);
    if (!last) {
      for (const b of [1, 2]) for (const nt of ch.slice(1)) S.place(music, S.pluck(S.hz(nt), beat * 0.5, 0.35, 10 + k * 3 + b), t0 + b * beat, 0.25);
    }
  });
  // the tune, on felt piano: a question in A minor, answered in C once the lamp is on
  const tune = [
    [1, 'E5', 1], [2, 'C5', 1], [3, 'A4', 2], [5, 'B4', 1],
    [6, 'C5', 2], [8, 'D5', 1], [9, 'E5', 1.5], [10.5, 'D5', 0.5], [11, 'C5', 1],
    [12, 'E5', 1], [13, 'G5', 2], [15, 'F5', 1], [16, 'E5', 1], [17, 'C5', 1],
    [18, 'C5', 3],
  ];
  for (const [b, nt, len] of tune) if (b * beat < dur - 0.3) S.place(music, S.piano(S.hz(nt), len * beat, b >= 12 ? 0.7 : 0.55), b * beat, 0.4);
  // strings come in with the lamp
  const lampT = Object.entries(events).find(([k]) => k.endsWith('.lamp'))?.[1] ?? dur;
  for (const nt of ['C4', 'E4', 'G4']) S.place(music, S.strings(S.hz(nt), dur - lampT + 0.5, 0.3), lampT - 0.2, 0.3);
  const wet = S.room(music, 0.3, { size: 1.1, damp: 0.5 });

  // ---------------- effects ----------------
  const cut = timeline.scenes.map((s) => s.start);
  const rainLevel = (t) => (t < cut[1] ? 0.8 : t < cut[2] ? 0.55 : Math.max(0, 0.4 - (t - cut[2]) * 0.25));
  const hiss = S.shape(S.bandpass(S.noise(dur, 1), 4200, 0.5), (t) => 0.2 * rainLevel(t));
  S.place(sfx, hiss, 0, 1);
  // single drops: on stone, on the leaf, into puddles
  const r = S.rng(2);
  for (let t = 0.05; t < dur; t += 0.04 + r() * 0.12) {
    if (r() > rainLevel(t)) continue;
    const f = 1400 + r() * 2200;
    const drop = S.buffer(0.06);
    for (let i = 0; i < drop.length; i++) {
      const u = i / S.SR;
      drop[i] = Math.sin(2 * Math.PI * f * u * (1 + u * 8)) * Math.exp(-u * 90);
    }
    S.place(sfx, drop, t, 0.12 * r());
  }
  // canal water lapping in the wide
  const lap = S.shape(S.lowpass(S.noise(cut[1] + 0.5, 3), 500), (t) => 0.18 * (0.6 + 0.4 * Math.sin(t * 3.1)) * Math.min(1, (cut[1] + 0.5 - t) * 2));
  S.place(sfx, lap, 0, 1);

  for (const ev of eventList) {
    const { t } = ev;
    if (ev.kind === 'step') {
      // a soft pad on wet stone, a little splash on top
      const tap = S.shape(S.bandpass(S.noise(0.08, 100 + Math.round(t * 100)), 700, 1.2), (u) => Math.min(1, u / 0.003) * Math.exp(-u * 60));
      const splash = S.shape(S.highpass(S.noise(0.06, 200 + Math.round(t * 100)), 3500), (u) => Math.exp(-u * 70));
      S.place(sfx, tap, t, 0.9 * (ev.near ?? 1));
      S.place(sfx, splash, t + 0.005, 0.2 * (ev.near ?? 1));
    }
    if (ev.name.endsWith('.drop')) {
      // the envelope slides through the slot, then lands in the wooden box
      const slide = S.shape(S.bandpass(S.noise(0.22, 300), 3000, 0.8), (u) => Math.sin(Math.min(1, u / 0.22) * Math.PI));
      S.place(sfx, slide, t - 0.22, 0.25);
      const thud = S.shape(S.lowpass(S.noise(0.12, 301), 350), (u) => Math.min(1, u / 0.002) * Math.exp(-u * 40));
      S.place(sfx, thud, t, 1.6);
      S.place(sfx, S.pluck(150, 0.2, 0.8, 302), t, 0.6);
      cues.push({ name: ev.name, t, stem: 'sfx', band: [80, 400] });
    }
    if (ev.name.endsWith('.lamp')) {
      // the switch clicks, the filament hums, and the glockenspiel answers
      const click = S.shape(S.highpass(S.noise(0.01, 400), 3500), (u) => Math.exp(-u * 700));
      S.place(sfx, click, t, 1.4);
      const hum = S.buffer(dur - t);
      for (let i = 0; i < hum.length; i++) {
        const u = i / S.SR;
        hum[i] = (Math.sin(2 * Math.PI * 100 * u) * 0.6 + Math.sin(2 * Math.PI * 200 * u) * 0.3) * Math.min(1, u / 0.3) * 0.04;
      }
      S.place(sfx, hum, t, 1);
      ['C6', 'E6', 'G6'].forEach((nt, k) => S.place(music.length ? wet : sfx, S.glock(S.hz(nt), 0.5), t + 0.15 + k * 0.12, 0.6));
      cues.push({ name: ev.name, t, stem: 'sfx', band: [3500, 9000] });
    }
  }
  // fade with the picture
  const fadeFrom = dur - 1.0;
  for (const x of [wet, sfx]) for (let i = Math.round(fadeFrom * S.SR); i < x.length; i++) x[i] *= Math.max(0, 1 - (i / S.SR - fadeFrom));
  for (let i = 0; i < Math.round(0.6 * S.SR); i++) sfx[i] *= i / (0.6 * S.SR);
  return { music: wet.subarray(0, S.n(dur)), sfx: sfx.subarray(0, S.n(dur)), cues };
}
