import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { createSessionManager, prepareConsentedSession, requireProcessingConsent, serviceOrigin } from '../src/lib/session.ts';

const origin = 'https://service.queuesaathi.org'; // Test fixture only; no network requests.
const now = 100000;
const stored = { url: origin, token: 'session', expires: 1000, suppressMonitor: true };
function fixture(overrides = {}) {
  const calls = { created: 0, saved: [] };
  const ensure = createSessionManager({
    origin, now: () => now, load: async () => null,
    save: async value => { calls.saved.push(value); },
    create: async value => { assert.equal(value, origin); calls.created++; return { token: 'new', expires_at: 1000 }; },
    ...overrides,
  });
  return { ensure, calls };
}
test('service origin normalizes HTTPS without any user configuration', () => {
  assert.equal(serviceOrigin(` ${origin}/ `), origin);
});
test('missing, insecure and credential-bearing origins fail without leaking configuration', () => {
  for (const url of ['', 'no-url', 'http://localhost', 'https://secret:pass@host.org', `${origin}/path`, `${origin}?key=secret`, `${origin}#frag`]) {
    assert.throws(() => serviceOrigin(url), /^Error: QueueSaathi is temporarily unavailable\./);
  }
});
test('first action automatically creates and securely saves a bearer session', async () => {
  const { ensure, calls } = fixture();
  const value = await ensure();
  assert.equal(calls.created, 1); assert.deepEqual(calls.saved, [value]); assert.equal(value.token, 'new');
});
test('restores unexpired session and local stop suppression without new admission', async () => {
  const { ensure, calls } = fixture({ load: async () => stored });
  assert.deepEqual(await ensure(), stored); assert.equal(calls.created, 0);
});
test('expired, nearly expired, malformed and different-deployment sessions are not reused', async () => {
  for (const value of [
    { ...stored, expires: 99 }, { ...stored, expires: 125 }, { ...stored, expires: '1000' },
    { ...stored, token: '' }, { ...stored, url: 'https://previous.org' },
  ]) {
    const { ensure, calls } = fixture({ load: async () => value });
    assert.equal((await ensure()).token, 'new'); assert.equal(calls.created, 1);
  }
});
test('concurrent actions share one admission request', async () => {
  const { ensure, calls } = fixture();
  const values = await Promise.all([ensure(), ensure(), ensure()]);
  assert.equal(calls.created, 1); assert.equal(values[0], values[2]);
});
test('server-revoked bearer is replaced on the next explicit action, including speech', async () => {
  const { ensure, calls } = fixture({ load: async () => stored, validate: async () => false });
  assert.equal((await ensure()).token, 'new'); assert.equal(calls.created, 1);
});
test('validation network failure never silently admits another session', async () => {
  const { ensure, calls } = fixture({ load: async () => stored, validate: async () => { throw new Error('offline'); } });
  await assert.rejects(ensure(), /offline/); assert.equal(calls.created, 0);
});
test('withdrawing consent during deferred admission prevents subsequent processing', async () => {
  let consent = true;
  let release;
  let processed = false;
  const ensure = () => new Promise(resolve => { release = resolve; });
  const action = prepareConsentedSession(ensure, () => consent).then(() => { processed = true; });
  consent = false; release(stored);
  await assert.rejects(action, /Processing was not allowed/); assert.equal(processed, false);
});
test('absent consent never requests a session; capture can recheck after permission dialogs', async () => {
  let created = false;
  await assert.rejects(prepareConsentedSession(async () => { created = true; return stored; }, () => false), /Processing was not allowed/);
  assert.equal(created, false);
  assert.throws(() => requireProcessingConsent(() => false), /Processing was not allowed/);
});
test('failed admission can be retried, and invalid responses are never persisted', async () => {
  let attempts = 0;
  const { ensure, calls } = fixture({ create: async () => {
    if (++attempts === 1) throw new Error('offline');
    return { token: '', expires_at: 1000 };
  } });
  await assert.rejects(ensure(), /offline/);
  await assert.rejects(ensure(), /Could not start a session/);
  assert.equal(calls.saved.length, 0);
});
test('unconfigured builds cannot silently pass distribution checks', () => {
  for (const url of ['', 'http://localhost:8000', 'https://your-queuesaathi-service.example', `${origin}/api`]) {
    const result = spawnSync(process.execPath, ['scripts/check-service.mjs'], {
      env: { ...process.env, EXPO_PUBLIC_API_URL: url }, encoding: 'utf8',
    });
    assert.notEqual(result.status, 0);
  }
  const valid = spawnSync(process.execPath, ['scripts/check-service.mjs'], {
    env: { ...process.env, EXPO_PUBLIC_API_URL: origin }, encoding: 'utf8',
  });
  assert.equal(valid.status, 0, valid.stderr);
});
test('main surface contains workflow controls, not operator setup', () => {
  const source = readFileSync(new URL('../src/app/index.tsx', import.meta.url), 'utf8');
  for (const label of ['Backend HTTPS URL', 'Pairing code', 'Connect your backend', 'Backend connection settings', '<Modal']) {
    assert.ok(!source.includes(label), `Operator UI must not return: ${label}`);
  }
  for (const label of ['>Speak</Button>', '>Continue</Button>', '>Start listening</Button>', '>Announcements</Button>', '>Stop</Button>']) {
    assert.ok(source.includes(label));
  }
});
