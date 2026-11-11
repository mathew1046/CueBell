import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../public/sw.js', import.meta.url), 'utf8');
const origin = 'https://app.example.com';

async function click(url, windows = []) {
  const events = new Map();
  const opened = [];
  let work;
  let closed = false;
  runInNewContext(source, { URL, self: {
    location: { origin }, addEventListener: (name, handler) => events.set(name, handler),
    clients: { matchAll: async () => windows, openWindow: async destination => opened.push(destination) },
  } });
  events.get('notificationclick')({ notification: { data: { url }, close: () => { closed = true; } },
    waitUntil: promise => { work = promise; } });
  await work;
  return { opened, closed };
}

test('notification clicks resolve the supplied destination and focus its existing window', async () => {
  let focused = false;
  const result = await click('/history', [{ url: origin + '/settings', focus: async () => assert.fail('Wrong window') },
    { url: origin + '/history', focus: async () => { focused = true; } }]);
  assert.equal(focused, true);
  assert.equal(result.closed, true);
  assert.deepEqual(result.opened, []);
});

test('notification clicks open the resolved destination when no window matches', async () => {
  assert.deepEqual((await click('/history?alert=42')).opened, [origin + '/history?alert=42']);
});

test('missing, malformed and external notification destinations return to CueBell', async () => {
  for (const url of [undefined, '', 'http://[', 'https://untrusted.example/', '//untrusted.example/']) {
    assert.deepEqual((await click(url)).opened, [origin + '/']);
  }
});
