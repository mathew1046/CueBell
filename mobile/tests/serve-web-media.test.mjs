import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';

test('static server supports demo video playback and byte-range seeking', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'cuebell-media-'));
  const probe = createServer();
  probe.listen(0, '127.0.0.1');
  await once(probe, 'listening');
  const port = probe.address().port;
  await new Promise(resolve => probe.close(resolve));
  await mkdir(join(dir, 'dist'));
  await writeFile(join(dir, 'dist', 'demo.mp4'), '0123456789');
  await writeFile(join(dir, 'dist', 'poster.jpg'), 'poster');
  const child = spawn(process.execPath, [fileURLToPath(new URL('../scripts/serve-web.mjs', import.meta.url))], {
    cwd: dir, env: { ...process.env, PORT: String(port) }, stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await once(child.stdout, 'data');
    const url = `http://127.0.0.1:${port}/demo.mp4`;
    const full = await fetch(url);
    assert.equal(full.headers.get('content-type'), 'video/mp4');
    assert.equal(full.headers.get('accept-ranges'), 'bytes');
    assert.equal(await full.text(), '0123456789');
    for (const [range, expected, contentRange] of [
      ['bytes=2-5', '2345', 'bytes 2-5/10'],
      ['bytes=7-', '789', 'bytes 7-9/10'],
      ['bytes=-3', '789', 'bytes 7-9/10'],
    ]) {
      const response = await fetch(url, { headers: { Range: range } });
      assert.equal(response.status, 206);
      assert.equal(response.headers.get('content-range'), contentRange);
      assert.equal(await response.text(), expected);
    }
    const invalid = await fetch(url, { headers: { Range: 'bytes=20-' } });
    assert.equal(invalid.status, 416);
    assert.equal(invalid.headers.get('content-range'), 'bytes */10');
    const image = await fetch(`http://127.0.0.1:${port}/poster.jpg`);
    assert.equal(image.headers.get('content-type'), 'image/jpeg');
  } finally {
    child.kill();
    await once(child, 'exit');
    await rm(dir, { recursive: true, force: true });
  }
});
