// Score and effects for 《河堤上的鹈鹕》. D major, 96 bpm, six bars; every cut lands on a bar line.
export default function score({ synth: S, film, timeline, eventList }) {
  const dur = timeline.duration;
  const music = S.buffer(dur + 3);
  const sfx = S.buffer(dur + 3);
  const amb = S.buffer(dur + 3);
  const cues = [];
  const beat = 60 / (film.tempo || 96);
  const at = (b) => b * beat;
  const sc = Object.fromEntries(timeline.scenes.map((s) => [s.id, s]));

  // ---------------- music
  const chords = [
    ['D3', 'A3', 'D4', 'F#4'],
    ['B2', 'F#3', 'B3', 'D4'],
    ['G2', 'D3', 'G3', 'B3'],
    ['A2', 'E3', 'A3', 'C#4'],
    ['G2', 'D3', 'G3', 'B3'],
    ['D3', 'A3', 'D4', 'F#4'],
  ];
  chords.forEach((c, bar) => {
    for (const [i, nm] of c.entries()) S.place(music, S.strings(S.hz(nm), 4 * beat, 0.16), at(bar * 4) + i * 0.02, i === 0 ? 0.9 : 0.55);
    // bass on the downbeat, felt piano
    S.place(music, S.piano(S.hz(c[0]) / 2, 2 * beat, 0.55), at(bar * 4), 0.7);
  });
  // a pedalling arpeggio in the tracking shot (bars 3 and 4), plucked
  for (const bar of [2, 3]) {
    const c = chords[bar];
    for (let k = 0; k < 8; k++) {
      const nm = c[[1, 2, 3, 2, 1, 2, 3, 2][k]];
      S.place(music, S.pluck(S.hz(nm) * 2, 0.3, 0.5, 7 + k), at(bar * 4 + k * 0.5), 0.35);
    }
  }
  // melody, original: [beat, note, beats, velocity]
  const tune = [
    [1, 'F#5', 1, 0.5], [2, 'A5', 0.5, 0.45], [2.5, 'G5', 0.5, 0.4], [3, 'F#5', 1, 0.45],
    [4, 'D5', 1.5, 0.5], [5.5, 'E5', 0.5, 0.4], [6, 'F#5', 1, 0.45], [7, 'B4', 1, 0.4],
    [8, 'D5', 0.5, 0.45], [8.5, 'E5', 0.5, 0.42], [9, 'G5', 1, 0.5], [10, 'F#5', 0.5, 0.42], [10.5, 'E5', 0.5, 0.4], [11, 'D5', 1, 0.42],
    [12.5, 'C#5', 0.5, 0.4], [13, 'E5', 0.5, 0.45], [13.5, 'A5', 1.5, 0.5], [15, 'G5', 1, 0.42],
    [16, 'F#5', 1, 0.45],
    [19, 'A4', 1, 0.4], [20, 'D5', 1, 0.45], [21, 'A4', 1, 0.38], [22, 'D5', 2, 0.42],
  ];
  for (const [b, nm, len, vel] of tune) S.place(music, S.piano(S.hz(nm), len * beat, vel), at(b), 0.6);
  // a glockenspiel answers the egrets
  for (const [b, nm] of [[18.75, 'A6'], [19.25, 'F#6'], [19.75, 'D6']]) S.place(music, S.glock(S.hz(nm), 0.4), at(b), 0.35);

  // fade the music in and out with the picture
  const fadeOutStart = dur - 1.3;
  let m = S.room(music, 0.32);
  m = S.shape(m, (t) => Math.min(1, t / 0.8) * (t > fadeOutStart ? Math.max(0, 1 - (t - fadeOutStart) / 1.3) : 1));

  // ---------------- ambience: wind and water, louder in the wide shots
  const level = (t) => (t < sc['s2-side'].start ? 1 : t < sc['s3-end'].start ? 0.55 : 0.9);
  const wind = S.lowpass(S.bandpass(S.noise(dur + 1, 301), 380, 0.6), 700);
  S.shape(wind, (t) => 0.22 * level(t) * (0.7 + 0.3 * Math.sin(t * 0.9) + 0.15 * Math.sin(t * 2.3 + 1)));
  S.place(amb, wind, 0, 1);
  // water lapping at the bank: slow soft swells
  const lap = S.bandpass(S.noise(dur + 1, 302), 520, 1.2);
  S.shape(lap, (t) => 0.12 * level(t) * Math.max(0, Math.sin(t * 2.1)) ** 2);
  S.place(amb, lap, 0, 1);

  // ---------------- tyres on gravel: a grainy crunch that follows each shot's speed
  const crunch = (t0, t1, gain, seed) => {
    const len = t1 - t0;
    const r = S.rng(seed);
    const x = S.bandpass(S.noise(len, seed), 1700, 1.1);
    const grains = Array.from({ length: Math.ceil(len * 40) }, () => 0.4 + r() * 0.6);
    S.shape(x, (t) => gain(t) * grains[Math.min(grains.length - 1, Math.floor(t * 40))] * Math.min(1, t / 0.05) * Math.min(1, (len - t) / 0.05));
    S.place(sfx, x, t0, 1);
  };
  const s1 = sc['s1-wide'];
  const s2 = sc['s2-side'];
  const s3 = sc['s3-end'];
  crunch(s1.start, s1.end, () => 0.04, 401);
  crunch(s2.start, s2.end, () => 0.22, 402);
  crunch(s3.start, s3.end, (t) => 0.09 * (t < 0.6 ? 1 : t < 2.9 ? 0.75 : 1) * (t > 3.6 ? Math.max(0, 1 - (t - 3.6) / 1.4) : 1), 403);

  // chain: a soft tick each sixth of a crank turn while pedalling in the tracking shot
  const v2 = 220 / (film.scenes[1].events.bump[1] - film.scenes[1].events.bump[0]);
  const crankRate = v2 / 70 / 2.2; // rad/s
  const tick = () => S.shape(S.highpass(S.noise(0.02, 501), 4200), (t) => Math.exp(-t * 300));
  for (let k = 0; ; k++) {
    const t = (k * (Math.PI / 3)) / crankRate;
    if (t > s2.end - s2.start) break;
    S.place(sfx, tick(), s2.start + t, 0.05);
  }
  // the freewheel ticking while the pelican coasts through the bell and the birds
  for (let t = 0.65; t < 2.85; t += 0.085 + (t - 0.65) * 0.01) S.place(sfx, tick(), s3.start + t, 0.03);

  // ---------------- the declared events
  for (const ev of eventList) {
    if (/\.bump\.\d$/.test(ev.name)) {
      const big = ev.name.endsWith('.1');
      S.place(sfx, S.softKick(big ? 1 : 0.6), ev.t, 1);
      // gravel spat out from under the tyre, and the basket rattling after
      S.place(sfx, S.shape(S.bandpass(S.noise(0.15, big ? 601 : 602), 1500, 0.9), (t) => Math.exp(-t * 25)), ev.t, big ? 0.6 : 0.35);
      for (let k = 0; k < 4; k++) S.place(sfx, S.shape(S.bandpass(S.noise(0.04, 610 + k), 3200, 3), (t) => Math.exp(-t * 90)), ev.t + 0.07 + k * 0.06, (big ? 0.18 : 0.1) * (1 - k * 0.2));
      cues.push({ name: ev.name, t: ev.t, stem: 'sfx', band: [45, 150] });
    } else if (/\.bell\.\d$/.test(ev.name)) {
      const first = ev.name.endsWith('.1');
      const b = S.bell(S.hz('E7'), 0.9, first ? 3 : 4);
      // the thumb comes back to the dome: the first ring is stopped before the second strike
      if (first) S.shape(b, (t) => (t < 0.2 ? 1 : Math.exp(-(t - 0.2) * 70)));
      S.place(sfx, b, ev.t, 0.9);
      cues.push({ name: ev.name, t: ev.t, stem: 'sfx', band: [2300, 3000] });
    } else if (ev.name.endsWith('.egrets')) {
      // a splash as the first legs push off the water
      S.place(sfx, S.shape(S.bandpass(S.noise(0.3, 701), 900, 0.8), (t) => Math.min(1, t / 0.004) * Math.exp(-t * 14)), ev.t, 0.6);
      cues.push({ name: ev.name, t: ev.t, stem: 'sfx', band: [600, 1400] });
    } else if (/\.egret\d+$/.test(ev.name)) {
      // each bird's own wingbeats, one whump per downstroke, fading as it climbs away
      const rate = ev.rate || 3.5;
      const seed = 800 + Number(ev.name.match(/(\d+)$/)[1]) * 13;
      for (let k = 0; k < 10; k++) {
        const t = ev.t + k / rate;
        if (t > dur) break;
        const w = S.shape(S.bandpass(S.noise(0.12, seed + k), 650 + (k % 3) * 60, 0.9), (u) => Math.min(1, u / 0.008) * Math.exp(-u * 28));
        S.place(sfx, w, t, 0.32 * Math.exp(-k * 0.28));
      }
    }
  }

  const out = (x) => x.subarray(0, S.n(dur));
  for (let i = 0; i < sfx.length; i++) sfx[i] += amb[i];
  return { music: out(m), sfx: out(sfx), cues };
}
