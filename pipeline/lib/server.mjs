// A tiny static server: /runtime/ serves the vertical's page, /film/ serves one film's build output.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.wav': 'audio/wav',
};

export function startServer(mounts) {
  const server = http.createServer((req, res) => {
    const url = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    for (const [prefix, dir] of Object.entries(mounts)) {
      if (!url.startsWith(prefix)) continue;
      const file = path.join(dir, url.slice(prefix.length));
      if (!path.resolve(file).startsWith(path.resolve(dir))) break;
      if (fs.existsSync(file) && fs.statSync(file).isFile()) {
        res.writeHead(200, { 'content-type': TYPES[path.extname(file)] ?? 'application/octet-stream', 'cache-control': 'no-store' });
        return fs.createReadStream(file).pipe(res);
      }
    }
    res.writeHead(404).end('not found');
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const close = () =>
        new Promise((r) => {
          server.closeAllConnections?.();
          server.close(r);
        });
      resolve({ origin: `http://127.0.0.1:${server.address().port}`, close });
    });
  });
}
