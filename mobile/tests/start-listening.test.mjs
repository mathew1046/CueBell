import assert from 'node:assert/strict';
import test from 'node:test';
import { startListeningIfCurrent } from '../src/lib/start-listening.ts';

test('a valid task starts the microphone immediately after activation without another action', async () => {
  const calls = [];
  await startListeningIfCurrent(() => true, async () => { calls.push('activate'); }, async () => { calls.push('start'); });
  assert.deepEqual(calls, ['activate', 'start']);
});

test('native startup explicitly defaults noise reduction to off', async () => {
  await startListeningIfCurrent(() => true, async () => {}, async options => {
    assert.deepEqual(options, { noiseReductionMode: 'off' });
  });
});

test('request and monitor startup preserve the selected noise reduction mode', async () => {
  for (const mode of ['request', 'monitor']) {
    for (const noiseReductionMode of ['off', 'gtcrn']) {
      const calls = [];
      const nativeStart = async (url, token, captureMode, options) => calls.push({ captureMode, options });
      await startListeningIfCurrent(() => true, async () => {},
        options => nativeStart('https://example.invalid', 'test-token', mode, options), noiseReductionMode);
      assert.deepEqual(calls, [{ captureMode: mode, options: { noiseReductionMode } }]);
    }
  }
});

test('pending activation retains its selected mode and stop still cancels opt-in capture', async () => {
  let selected = 'gtcrn';
  let complete;
  const pending = startListeningIfCurrent(() => true,
    () => new Promise(resolve => { complete = resolve; }), async options => {
      assert.deepEqual(options, { noiseReductionMode: 'gtcrn' });
    }, selected);
  selected = 'off';
  complete();
  await pending;

  let current = true;
  const stopped = startListeningIfCurrent(() => current,
    () => new Promise(resolve => { complete = resolve; }), async () => assert.fail('restarted after Stop'), 'gtcrn');
  current = false;
  complete();
  await stopped;
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
