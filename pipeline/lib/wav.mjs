import fs from 'node:fs';
import path from 'node:path';

export const RATE = 48000;

/** Read a 16-bit mono PCM WAV file. */
export function readWav(file) {
  const b = fs.readFileSync(file);
  if (b.toString('ascii', 0, 4) !== 'RIFF' || b.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error(`not a WAV file: ${file}`);
  }
  let off = 12;
  let fmt = null;
  let data = null;
  while (off + 8 <= b.length) {
    const id = b.toString('ascii', off, off + 4);
    const size = b.readUInt32LE(off + 4);
    if (id === 'fmt ') {
      fmt = {
        format: b.readUInt16LE(off + 8),
        channels: b.readUInt16LE(off + 10),
        rate: b.readUInt32LE(off + 12),
        bits: b.readUInt16LE(off + 22),
      };
    } else if (id === 'data') {
      data = b.subarray(off + 8, Math.min(off + 8 + size, b.length));
      break;
    }
    off += 8 + size + (size % 2);
  }
  if (!fmt || !data) throw new Error(`WAV file has no fmt or data chunk: ${file}`);
  if (fmt.format !== 1 || fmt.bits !== 16 || fmt.channels !== 1) {
    throw new Error(`expected 16-bit mono PCM, got format ${fmt.format}, ${fmt.bits} bit, ${fmt.channels} ch: ${file}`);
  }
  // Copy into a fresh buffer so the Int16Array view is aligned.
  const copy = new Uint8Array(data);
  return { rate: fmt.rate, samples: new Int16Array(copy.buffer, 0, copy.length >> 1) };
}

export function writeWav(file, samples, rate = RATE) {
  const header = Buffer.alloc(44);
  const bytes = samples.length * 2;
  header.write('RIFF', 0, 'ascii');
  header.writeUInt32LE(36 + bytes, 4);
  header.write('WAVE', 8, 'ascii');
  header.write('fmt ', 12, 'ascii');
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(rate, 24);
  header.writeUInt32LE(rate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write('data', 36, 'ascii');
  header.writeUInt32LE(bytes, 40);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, Buffer.concat([header, Buffer.from(samples.buffer, samples.byteOffset, bytes)]));
}
