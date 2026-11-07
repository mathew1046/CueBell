import assert from 'node:assert/strict';
import test from 'node:test';
import { startListeningIfCurrent } from '../src/lib/start-listening.ts';

test('a valid task starts the microphone immediately after activation without another action', async () => {
  const calls = [];
  await startListeningIfCurrent(() => true, async () => { calls.push('activate'); }, async () => { calls.push('start'); });
  assert.deepEqual(calls, ['activate', 'start']);
});

test('cancel before activation does no work', async () => {
  await startListeningIfCurrent(() => false, async () => assert.fail('activated'), async () => assert.fail('started'));
});

test('stop while activation is pending prevents a late microphone restart', async () => {
  let current = true;
  let complete;
  const pending = startListeningIfCurrent(() => current,
    () => new Promise(resolve => { complete = resolve; }), async () => assert.fail('restarted after Stop'));
  current = false;
  complete();
  await pending;
});

test('failed activation or lost processing consent never starts capture', async () => {
  await assert.rejects(startListeningIfCurrent(() => true, async () => { throw new Error('offline'); },
    async () => assert.fail('started without task')), /offline/);
  let consent = true;
  await assert.rejects(startListeningIfCurrent(() => {
    if (!consent) throw new Error('consent required');
    return true;
  }, async () => { consent = false; }, async () => assert.fail('started without consent')), /consent required/);
});
