// Frame-by-frame render: seek, screenshot, pipe to ffmpeg. Any frame can be drawn on its own,
// so every run gives the same picture (up to a few anti-aliased pixels the browser varies).
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { run } from './util.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const cacheRoot = () => process.env.DF_RENDER_CACHE ?? path.join(here, '..', '..', '.cache', 'render');

/**
 * Render the picture and lay the audio under it. `cacheKey` names everything the picture depends
 * on; a picture rendered before under the same key is reused, so a change to the sound alone costs
 * a remux instead of a render.
 */
export async function renderVideo(stage, timeline, { outDir, draft = false, audioFile = null, cacheKey = null }) {
  const fps = draft ? 15 : timeline.fps;
  const frames = Math.round(timeline.duration * fps);
  const silent = path.join(outDir, 'video.mp4');
  const cached = cacheKey && process.env.DF_RENDER_CACHE !== 'off' ? path.join(cacheRoot(), `${cacheKey}-${fps}.mp4`) : null;
  if (cached && fs.existsSync(cached)) {
    fs.copyFileSync(cached, silent);
    return finishVideo({ outDir, silent, audioFile, fps, frames, stage, reused: true });
  }
  const ff = spawn(
    'ffmpeg',
    ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(fps), silent],
    { stdio: ['pipe', 'ignore', 'pipe'] },
  );
  let stderr = '';
  ff.stderr.on('data', (d) => (stderr += d));
  const done = new Promise((resolve, reject) => {
    ff.on('error', reject);
    ff.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code}\n${stderr.slice(-1500)}`))));
  });
  for (let i = 0; i < frames; i++) {
    await stage.seek(i / fps);
    const jpg = await stage.page.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(jpg)) await once(ff.stdin, 'drain');
  }
  ff.stdin.end();
  await done;
  if (cached) {
    // write under a temporary name first: another run may be storing the same picture
    fs.mkdirSync(path.dirname(cached), { recursive: true });
    const tmp = `${cached}.${process.pid}.${Date.now()}.tmp`;
    fs.copyFileSync(silent, tmp);
    fs.renameSync(tmp, cached);
  }
  return finishVideo({ outDir, silent, audioFile, fps, frames, stage, reused: false });
}

async function finishVideo({ outDir, silent, audioFile, fps, frames, stage, reused }) {
  const file = path.join(outDir, 'film.mp4');
  if (audioFile) {
    await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', silent, '-i', audioFile, '-c:v', 'copy',
      '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', file]);
  } else {
    await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', silent, '-c', 'copy', '-movflags', '+faststart', file]);
  }
  fs.rmSync(silent, { force: true });
  return { file, fps, frames, width: 1920 * stage.scale, height: 1080 * stage.scale, reused };
}
