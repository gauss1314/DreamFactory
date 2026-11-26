// The anime vertical: hand-drawn-style films painted and scored in Python (numpy, OpenCV, pycairo,
// numba). The engine in lp/ and audio/ comes from The Last Page; tools/film.py drives it.
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

export const id = 'anime';
export const engine = 'python';
export const engineDir = here;
export const runtimeDir = here;
export const builtinScenes = [];
export const fps = 24;
export const needsData = false;
/** Checks for a film with no on-screen text. Picture checks read what the shots report. */
export const checks = ['spec', 'determinism', 'heading', 'contact', 'landing', 'video-stillness', 'pops', 'palette', 'audio-levels', 'cue-sync'];

/** Every shot is cut to its stated length. */
export function minDuration(scene) {
  return scene.duration ?? 3;
}
