import assert from 'node:assert/strict';
import test from 'node:test';
import { stopListening } from '../src/lib/stop-listening.ts';

const connection = { url: 'https://example.org', token: 'test-bearer', expires: 9999999999 };
const failure = async () => { throw new Error('unavailable'); };

function harness(overrides = {}) {
  const calls = [];
  let saved = connection;
  let current = connection;
  let storageCleanupPending = false;
  const dependencies = {
    stopCapture: async () => { calls.push('capture'); },
    clearLocal: () => { calls.push('clear'); },
    setConnection: value => { current = value; },
    setStorageCleanupPending: value => { storageCleanupPending = value; },
    save: async value => { calls.push('save'); saved = value; },
    remove: async () => { calls.push('remove'); saved = null; },
    remote: async (value, action) => { calls.push(`remote:${action}`); assert.equal(value, connection); },
    ...overrides,
  };
  return { calls, dependencies, saved: () => saved, current: () => current, storageCleanupPending: () => storageCleanupPending };
}

test('pause still turns off capture without a restored connection', async () => {
  const h = harness();
  await stopListening('pause', null, h.dependencies);
  assert.deepEqual(h.calls, ['capture']);
});

test('stop clears capture, local events and saved credentials without a restored connection', async () => {
  const h = harness();
  await stopListening('stop', null, h.dependencies);
  assert.deepEqual(h.calls, ['capture', 'clear', 'remove']);
  assert.equal(h.saved(), null);
  assert.equal(h.current(), null);
});

test('full stop suppresses restoration before attempting remote cleanup', async () => {
  const h = harness();
  await stopListening('stop', connection, h.dependencies);
  assert.deepEqual(h.calls, ['capture', 'clear', 'save', 'remote:stop']);
  assert.equal(h.saved().suppressMonitor, true);
  assert.equal(h.current().suppressMonitor, true);
});

test('pause keeps local history and credentials, even when backend cleanup fails', async () => {
  const h = harness({ remote: failure });
  await assert.rejects(stopListening('pause', connection, h.dependencies), /Microphone is off.*Backend cleanup failed/);
  assert.deepEqual(h.calls, ['capture']);
  assert.equal(h.saved(), connection);
});

test('storage write failure falls back to deleting stale credentials and still cleans up remotely', async () => {
  const h = harness({ save: failure });
  await assert.rejects(stopListening('stop', connection, h.dependencies), /saved session was removed instead/);
  assert.deepEqual(h.calls, ['capture', 'clear', 'remove', 'remote:stop']);
  assert.equal(h.saved(), null);
  assert.equal(h.current(), null);
  assert.equal(h.storageCleanupPending(), false);
});

test('simultaneous storage and backend failures are both reported', async () => {
  const h = harness({ save: failure, remote: failure });
  await assert.rejects(stopListening('stop', connection, h.dependencies), error => {
    assert.match(error.message, /Could not save the cleared state/);
    assert.match(error.message, /saved session was removed instead/);
    assert.match(error.message, /Backend cleanup failed/);
    return true;
  });
  assert.equal(h.saved(), null);
});

test('failed fallback deletion gives actionable recovery and does not skip remote cleanup', async () => {
  const h = harness({ save: failure, remove: failure });
  await assert.rejects(stopListening('stop', connection, h.dependencies), error => {
    assert.match(error.message, /Retry Stop in Settings before closing the app/);
    assert.match(error.message, /clear CueBell storage in Android settings/);
    return true;
  });
  assert.deepEqual(h.calls, ['capture', 'clear', 'remote:stop']);
  assert.equal(h.current().suppressMonitor, true);
  assert.equal(h.storageCleanupPending(), true);
});

test('all cleanup failures remain visible rather than masking one another', async () => {
  const h = harness({ save: failure, remove: failure, remote: failure });
  await assert.rejects(stopListening('stop', connection, h.dependencies), error => {
    assert.match(error.message, /Could not update or remove the saved session/);
    assert.match(error.message, /Backend cleanup failed/);
    return true;
  });
});

test('remote failure cannot prevent durable local suppression', async () => {
  const h = harness({ remote: failure });
  await assert.rejects(stopListening('stop', connection, h.dependencies), /Backend cleanup failed/);
  assert.equal(h.saved().suppressMonitor, true);
  assert.equal(h.current().suppressMonitor, true);
  assert.deepEqual(h.calls, ['capture', 'clear', 'save']);
});

test('native stop failure is propagated without falsely claiming capture is off', async () => {
  const h = harness({ stopCapture: failure });
  await assert.rejects(stopListening('stop', connection, h.dependencies), /unavailable/);
  assert.deepEqual(h.calls, []);
});
