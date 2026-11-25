// Data-story sound: a quiet bed under the narration and small sounds on the picture's actions.
// Every data film gets this unless it brings its own sound.js or sets "music": false.
// The picture reports its actions (events); each one gets a sound placed on exactly that moment.
//
// Music: D major, 84 bpm, four chords looping (Dmaj7, Bm7, Gmaj7, A). Pad and a sparse plucked
// figure, a few felt-piano notes on top. It drops by 12 dB while anyone is speaking and resolves
// to D for the last bar.

export default function score({ synth: S, film, timeline, eventList }) {
  const dur = timeline.duration;
  const music = S.buffer(dur + 4);
  const sfx = S.buffer(dur + 2);
  const cues = [];
  const opts = typeof film.music === 'object' ? film.music : {};
  const beat = 60 / (opts.tempo ?? 84);
  const barLen = 4 * beat;

  // ---------------- music ----------------
  const loop = [
    ['D3', 'A3', 'C#4', 'F#4'],
    ['B2', 'F#3', 'A3', 'D4'],
    ['G2', 'D3', 'F#3', 'B3'],
    ['A2', 'E3', 'A3', 'C#4'],
  ];
  const top = ['F#4', 'D4', 'B3', 'C#4'];
  const bars = Math.ceil(dur / barLen);
  const endBar = Math.max(0, Math.floor((dur - 2.5) / barLen));
  for (let b = 0; b < bars; b++) {
    const final = b >= endBar;
    const ch = final ? ['D2', 'A2', 'F#3', 'D4'] : loop[b % 4];
    const t0 = b * barLen;
    if (t0 >= dur) break;
    const len = final ? dur - t0 + 1 : barLen;
    for (const nt of ch.slice(0, 3)) S.place(music, S.strings(S.hz(nt), len, 0.22), t0, 0.35);
    // a sparse pluck: root, fifth, third, fifth, on the beat
    if (!final) {
      [0, 1, 2, 1].forEach((k, e) => S.place(music, S.pluck(S.hz(ch[k]) * 2, beat * 0.9, 0.35, 11 + b * 4 + e), t0 + e * beat, 0.3));
    }
    // a felt-piano note at the top of every other bar, and the tonic at the end
    if (final) S.place(music, S.piano(S.hz('D5'), 2.5, 0.55), t0, 0.4);
    else if (b % 2 === 0) S.place(music, S.piano(S.hz(top[(b / 2) % 4]) * 2, barLen * 0.9, 0.45), t0 + beat * 0.02, 0.35);
  }
  // duck under the voice: 12 dB down while a line is spoken, with short ramps either side
  const lines = timeline.scenes.flatMap((sc) => sc.lines);
  const duck = (t) => {
    let d = 0;
    for (const l of lines) {
      const into = Math.min(1, Math.max(0, (t - (l.start - 0.25)) / 0.25));
      const out = Math.min(1, Math.max(0, (l.end + 0.35 - t) / 0.35));
      d = Math.max(d, Math.min(into, out));
    }
    return 1 - d * (1 - S.db(-14));
  };
  S.shape(music, duck);
  // fade in over the first second, out over the last two
  S.shape(music, (t) => Math.min(1, t / 1.0) * Math.min(1, Math.max(0, (dur - t) / 2)));
  const gain = S.db(opts.gainDb ?? 0);
  const wet = S.room(music, 0.25, { size: 1.0, damp: 0.45 });

  // ---------------- sounds on the picture's actions ----------------
  const BAND = { swish: [1500, 6000], tick: [1200, 3600], chime: [3500, 9000], hit: [40, 220], pop: [600, 2400] };
  for (const ev of eventList) {
    const { t, kind } = ev;
    if (kind === 'swish') {
      const x = S.shape(S.bandpass(S.noise(0.35, 21), (u) => 1800 + 6000 * u, 1.2), (u) => Math.min(1, u / 0.006) * Math.exp(-u * 9));
      S.place(sfx, x, t, 0.35);
    } else if (kind === 'tick') {
      // a small pluck, higher for a longer bar
      const note = 72 + Math.round((ev.rank ?? 0.5) * 7);
      S.place(sfx, S.pluck(440 * 2 ** ((note - 69) / 12), 0.12, 0.55, 31 + Math.round(t * 100)), t, 0.45);
    } else if (kind === 'chime') {
      ['A5', 'D6'].forEach((nt, k) => S.place(sfx, S.glock(S.hz(nt), 0.55), t + k * 0.09, 0.7));
    } else if (kind === 'hit') {
      S.place(sfx, S.softKick(0.7), t, 0.45);
      S.place(sfx, S.glock(S.hz('D5'), 0.35), t, 0.45);
    } else if (kind === 'pop') {
      S.place(sfx, S.pluck(S.hz('A4'), 0.15, 0.6, 41 + Math.round(t * 100)), t, 0.55);
    } else if (kind === 'count') {
      // ticks that slow down as the number settles, like a counter coming to rest
      for (let k = 0; ; k++) {
        const u = k / 14;
        const tt = t + (ev.dur ?? 0.9) * (1 - (1 - u) ** 1.8);
        if (u > 1) break;
        const click = S.shape(S.highpass(S.noise(0.008, 200 + k), 3000), (v) => Math.exp(-v * 900));
        S.place(sfx, click, tt, 0.25);
      }
    }
    if (!ev.minor && BAND[kind]) cues.push({ name: ev.name, t, stem: 'sfx', band: BAND[kind] });
  }

  // the effects step back under the voice too, less than the music: they still mark the moment
  const duckFx = (t) => 1 - (1 - duck(t)) * 0.8;
  S.shape(sfx, duckFx);
  return { music: wet.subarray(0, S.n(dur)).map((v) => v * gain), sfx: sfx.subarray(0, S.n(dur)), cues };
}
