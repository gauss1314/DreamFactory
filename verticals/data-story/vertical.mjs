// The data-story vertical: a narrated short that explains one dataset with charts and big numbers.
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

export const id = 'data-story';
export const runtimeDir = path.join(here, 'runtime');
export const builtinScenes = ['title', 'outro', 'bignumber', 'bars', 'ranges', 'bullets'];
/** The default score and effects for every data film. */
export const soundFile = path.join(here, 'sound.mjs');

/** The shortest a scene may be so its own animation finishes, whatever the narration length. */
export function minDuration(scene) {
  const n = (scene.series ?? scene.items ?? []).length;
  switch (scene.type) {
    case 'bars':
    case 'ranges':
      return 2.6 + 0.14 * n;
    case 'bullets':
      return 1.5 + 0.9 * n;
    case 'bignumber':
      return 3.2;
    default:
      return 3;
  }
}
