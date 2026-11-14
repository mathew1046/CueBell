import assert from 'node:assert/strict';
import test from 'node:test';
import { canChangeNoiseReduction, isNoiseReductionFallback, readNoiseReductionMode } from '../src/lib/noise-reduction.ts';

test('only an explicit stored GTCRN selection enables noise reduction', () => {
  assert.equal(readNoiseReductionMode('gtcrn'), 'gtcrn');
  for (const value of [null, undefined, '', 'off', 'on', 'GTCRN', true, 1, '{}']) {
    assert.equal(readNoiseReductionMode(value), 'off');
  }
});

test('selection is available before capture or while paused, never during setup or handoff', () => {
  const stopped = { running: false };
  assert.equal(canChangeNoiseReduction(stopped, null, false), true);
  assert.equal(canChangeNoiseReduction(stopped, null, true), false);
  for (const mode of ['request', 'monitor']) {
    for (const phase of ['REQUESTING_PERMISSION', 'CONNECTING', 'PROCESSING', 'STOPPING']) {
      assert.equal(canChangeNoiseReduction(stopped, { mode, phase }, false), false);
    }
  }
  for (const state of ['STARTING', 'LISTENING', 'PROCESSING', 'RECONNECTING', 'STOPPING']) {
    assert.equal(canChangeNoiseReduction({ running: true, state }, null, false), false);
  }
});

test('fallback reflects native effective mode only for a live opted-in capture', () => {
  const fallback = { requestedMode: 'gtcrn', activeMode: 'off', fallbackReason: 'initialization_failed' };
  assert.equal(isNoiseReductionFallback({ running: true, noiseReduction: fallback }), true);
  assert.equal(isNoiseReductionFallback({ running: false, noiseReduction: fallback }), false);
  assert.equal(isNoiseReductionFallback({ running: true }), false);
  assert.equal(isNoiseReductionFallback({ running: true, noiseReduction: { ...fallback, requestedMode: 'off' } }), false);
  assert.equal(isNoiseReductionFallback({ running: true, noiseReduction: { ...fallback, activeMode: 'gtcrn', fallbackReason: null } }), false);
  assert.equal(isNoiseReductionFallback({ running: true, noiseReduction: { ...fallback, fallbackReason: null } }), false);
});
