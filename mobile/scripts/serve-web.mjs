import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';

const root = resolve('dist');
const port = Number(process.env.PORT || 4173);
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.webmanifest': 'application/manifest+json',
  '.png': 'image/png', '.ico': 'image/x-icon', '.ttf': 'font/ttf', '.woff2': 'font/woff2' };

createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    let file = resolve(root, `.${pathname}`);
    if (file !== root && !file.startsWith(root + sep)) { response.writeHead(403).end(); return; }
    if (file === root || pathname.endsWith('/')) file = resolve(file, 'index.html');
    else if (!extname(file)) file += '.html';
    if (!(await stat(file)).isFile()) throw new Error('Not a file');
    response.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream',
      'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
    response.end(await readFile(file));
  } catch { response.writeHead(404).end('Not found'); }
}).listen(port, '127.0.0.1', () => console.log(`CueBell preview at http://127.0.0.1:${port}`));
