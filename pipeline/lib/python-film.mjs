// Films whose picture and sound are made by Python (the anime vertical). The pipeline keeps doing
// what it does for every film: the timeline, the events, the mix the checks listen to, and the
// checks. Python paints the frames and writes the score; tools/film.py in the vertical is the driver.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { hash, readJson, run, writeJson } from './util.mjs';
import { mixNarration } from './audio.mjs';
import { readWav } from './wav.mjs';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const python = () => process.env.DF_PYTHON ?? path.join(repoRoot, '.venv', 'bin', 'python');
const cacheRoot = () => process.env.DF_RENDER_CACHE ?? path.join(repoRoot, '.cache', 'render');

/** Every file under dir with one of the given extensions, as [relative name, content] pairs. */
function sources(dir, exts, skip = () => false) {
  const out = [];
  const walk = (d) => {
    for (const name of fs.readdirSync(d).sort()) {
      const p = path.join(d, name);
      const rel = path.relative(dir, p);
      if (name === '__pycache__' || name === 'qa' || name === 'out' || skip(rel)) continue;
      if (fs.statSync(p).isDirectory()) walk(p);
      else if (exts.some((e) => name.endsWith(e))) out.push(rel, fs.readFileSync(p, 'utf8'));
    }
  };
  walk(dir);
  return out;
}

/**
 * Everything the picture depends on: the film's shot list (its sound aside), every Python file of
 * the film except the sound, and the engine. Same key, same frames.
 */
function pictureKey(film, filmDir, vertical) {
  const { music, ...picture } = film;
  const filmCode = sources(filmDir, ['.py'], (rel) => /^sound[^/]*\.py$/.test(rel));
  const engine = sources(vertical.engineDir, ['.py'], (rel) => rel.startsWith('audio'));
  return hash(JSON.stringify([picture, filmCode, engine]));
}

async function driver(vertical, args) {
  try {
    return await run(python(), [path.join(vertical.engineDir, 'tools', 'film.py'), ...args]);
  } catch (e) {
    // the end of the Python traceback is the useful part
    throw new Error(`${args[0]} 失败：${String(e.message).trim().split('\n').slice(-6).join('\n')}`);
  }
}

function cached(dir, files) {
  return files.every((f) => fs.existsSync(path.join(dir, f)));
}

function store(dir, from) {
  const tmp = `${dir}.${process.pid}.${Date.now()}.tmp`;
  fs.mkdirSync(tmp, { recursive: true });
  for (const [name, src] of Object.entries(from)) if (fs.existsSync(src)) fs.copyFileSync(src, path.join(tmp, name));
  fs.rmSync(dir, { recursive: true, force: true });
  fs.renameSync(tmp, dir);
}

/**
 * Picture, sound and mix for a Python film. Returns what the checks need, in the same shape the
 * browser path produces: sampling (track, samples, repeat, sheet), audio (mix, stems, cues, events)
 * and video (the finished film with its stereo master).
 */
export async function runPythonFilm({ film, filmDir, outDir, timeline, declared, draft, video: wantVideo, vertical, timing }) {
  fs.mkdirSync(path.join(outDir, 'build'), { recursive: true });
  fs.mkdirSync(path.join(outDir, 'audio'), { recursive: true });
  const key = `${pictureKey(film, filmDir, vertical)}-anime-${draft ? 'draft' : 'full'}`;
  const cache = process.env.DF_RENDER_CACHE === 'off' ? null : path.join(cacheRoot(), key);
  const pictureFile = path.join(outDir, 'build', 'picture.json');
  const contactFile = path.join(outDir, 'contact.jpg');
  const silent = path.join(outDir, 'video.mp4');

  // 1. The picture's own reports: where everyone is, the moments that want a sound, a contact sheet.
  //    With a video asked for, the frames are rendered in the same pass.
  const need = wantVideo ? ['picture.json', 'video.mp4'] : ['picture.json'];
  if (cache && cached(cache, need)) {
    fs.copyFileSync(path.join(cache, 'picture.json'), pictureFile);
    if (fs.existsSync(path.join(cache, 'contact.jpg'))) fs.copyFileSync(path.join(cache, 'contact.jpg'), contactFile);
    if (wantVideo) fs.copyFileSync(path.join(cache, 'video.mp4'), silent);
  } else {
    await driver(vertical, ['picture', filmDir, '--out', outDir, ...(draft ? ['--draft'] : []), ...(wantVideo ? [] : ['--no-video']), '--jobs', String(process.env.DF_JOBS ?? 4)]);
    if (cache) store(cache, { 'picture.json': pictureFile, 'contact.jpg': contactFile, ...(wantVideo ? { 'video.mp4': silent } : {}) });
  }
  const picture = readJson(pictureFile);
  timing?.('picture');

  // 2. Sound, placed on the declared events and the moments the shots report.
  const eventList = [...declared, ...picture.events].sort((a, b) => a.t - b.t);
  writeJson(path.join(outDir, 'build', 'events.json'), eventList);
  await driver(vertical, ['sound', filmDir, '--out', outDir]);
  const stemFiles = { music: path.join(outDir, 'audio', 'music.wav'), sfx: path.join(outDir, 'audio', 'sfx.wav') };
  const stems = Object.values(stemFiles).map((f) => Float32Array.from(readWav(f).samples, (v) => v / 32768));
  // the mono mix the checks listen to, brought to the same loudness target as every film
  const audio = await mixNarration({ timeline, outDir, stems });
  audio.cues = readJson(path.join(outDir, 'build', 'cues.json'));
  audio.events = eventList.filter((e) => !e.minor);
  audio.stems = stemFiles;
  timing?.('sound');

  // 3. The film: the frames, with the stereo master under them.
  let video = null;
  if (wantVideo) {
    const file = path.join(outDir, 'film.mp4');
    await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', silent, '-i', path.join(outDir, 'audio', 'master.wav'),
      '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', file]);
    fs.rmSync(silent, { force: true });
    video = { file, fps: picture.fps, frames: Math.round(timeline.duration * picture.fps), width: picture.width, height: picture.height };
  }

  // The checks read the characters on a quarter-second grid, like the browser films' samples.
  const samples = picture.track
    .filter((x) => Math.abs(x.t * 4 - Math.round(x.t * 4)) < 1e-6)
    .map((x) => ({ t: x.t, grid: true, texts: [], actors: x.actors }));
  const sampling = { ...picture, samples, cjkOk: true };
  return { sampling, audio, video, key };
}
