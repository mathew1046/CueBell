import assert from 'node:assert/strict';
import test from 'node:test';
import { listeningPhase } from '../src/lib/listening.ts';

test('permission is explicit and denial keeps an inactive recorder in an error state', () => {
  const stopped = { running: false, state: 'STOPPED' };
  assert.equal(listeningPhase(stopped, null, false), 'IDLE');
  assert.equal(listeningPhase(stopped, { mode: 'monitor', phase: 'REQUESTING_PERMISSION' }, false), 'REQUESTING_PERMISSION');
  assert.equal(listeningPhase(stopped, null, true), 'ERROR');
  assert.equal(listeningPhase(stopped, { mode: 'monitor', phase: 'CONNECTING' }, false), 'CONNECTING');
});

test('only ready audio is listening and a lost stream stays reconnecting until audio returns', () => {
  const running = state => ({ running: true, state });
  assert.equal(listeningPhase(running('STARTING'), null, false), 'CONNECTING');
  assert.equal(listeningPhase(running('READY'), null, false), 'CONNECTING');
  assert.equal(listeningPhase(running('PROCESSING'), null, false), 'PROCESSING');
  assert.equal(listeningPhase(running('LISTENING'), { mode: 'request', phase: 'PROCESSING' }, false), 'PROCESSING');
  assert.equal(listeningPhase(running('LISTENING'), null, false), 'LISTENING');
  assert.equal(listeningPhase(running('RECONNECTING'), null, false), 'RECONNECTING');
  assert.equal(listeningPhase(running('LISTENING'), { mode: 'monitor', phase: 'STOPPING' }, false), 'STOPPING');
  assert.equal(listeningPhase(running('STOPPING'), null, false), 'STOPPING');
  assert.equal(listeningPhase({ running: false, state: 'ERROR' }, null, false), 'ERROR');
});
