// Frame-by-frame render: seek, screenshot, pipe to ffmpeg. Any frame can be drawn on its own,
// so every run gives the same picture (up to a few anti-aliased pixels the browser varies).
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import { run } from './util.mjs';

export async function renderVideo(stage, timeline, { outDir, draft = false, audioFile = null }) {
  const fps = draft ? 15 : timeline.fps;
  const frames = Math.round(timeline.duration * fps);
  const silent = path.join(outDir, 'video.mp4');
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

  const file = path.join(outDir, 'film.mp4');
  if (audioFile) {
    await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', silent, '-i', audioFile, '-c:v', 'copy',
      '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', file]);
  } else {
    await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', silent, '-c', 'copy', '-movflags', '+faststart', file]);
  }
  fs.rmSync(silent, { force: true });
  return { file, fps, frames, width: 1920 * stage.scale, height: 1080 * stage.scale };
}
