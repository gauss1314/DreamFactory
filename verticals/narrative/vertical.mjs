// The narrative vertical: a short hand-drawn-style film with a score and sound effects, no narration needed.
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

export const id = 'narrative';
export const runtimeDir = path.join(here, 'runtime');
export const builtinScenes = [];
export const fps = 24;
export const needsData = false;
/** The checks that mean something for a film with no on-screen text. */
export const checks = ['spec', 'determinism', 'video-stillness', 'pops', 'palette', 'audio-levels', 'cue-sync', 'asr'];

/** Every shot is cut to its stated length. */
export function minDuration(scene) {
  return scene.duration ?? 3;
}
