import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { compileFunction } from 'node:vm';
import ts from 'typescript';
import { CaptureCancelledError } from '../src/lib/listening.ts';

const source = readFileSync(new URL('../modules/queue-listener/browser.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
const load = compileFunction(outputText, ['exports', 'require', 'window', 'document', 'navigator', 'DOMException']);

function permissionHarness() {
  const requests = [];
  const navigator = { mediaDevices: { getUserMedia: () => new Promise((resolve, reject) => requests.push({ resolve, reject })) } };
  const events = { addEventListener() {}, removeEventListener() {} };
  const window = { ...events, isSecureContext: true, AudioWorkletNode: class {} };
  const document = { ...events, visibilityState: 'visible', hidden: false };
  const exports = {};
  load(exports, id => id.endsWith('/listening') ? { CaptureCancelledError } : {}, window, document, navigator, DOMException);
  return { ...exports, requests, document };
}

function microphone() {
  const track = { readyState: 'live', stop() { this.readyState = 'ended'; } };
  return { track, getTracks: () => [track], getAudioTracks: () => [track] };
}

test('concurrent permission callers share one prompt and one prepared stream', async () => {
  const h = permissionHarness();
  const first = h.requestMicrophone();
  const second = h.requestMicrophone();
  assert.equal(first, second);
  assert.equal(h.requests.length, 1);
  const stream = microphone();
  h.requests[0].resolve(stream);
  await Promise.all([first, second]);
  await h.requestMicrophone();
  assert.equal(h.requests.length, 1);
  h.releasePreparedMicrophone();
  assert.equal(stream.track.readyState, 'ended');
});

test('a cancelled late grant cannot overwrite or release a newer permission request', async () => {
  const h = permissionHarness();
  const first = h.requestMicrophone();
  h.releasePreparedMicrophone();
  const second = h.requestMicrophone();
  const stale = microphone();
  h.requests[0].resolve(stale);
  await assert.rejects(first, CaptureCancelledError);
  assert.equal(stale.track.readyState, 'ended');
  assert.equal(h.requestMicrophone(), second);
  const current = microphone();
  h.requests[1].resolve(current);
  await second;
  assert.equal(current.track.readyState, 'live');
  h.releasePreparedMicrophone();
  assert.equal(current.track.readyState, 'ended');
});

test('a denied permission after cancellation retains the cancellation result', async () => {
  const h = permissionHarness();
  const request = h.requestMicrophone();
  h.releasePreparedMicrophone();
  h.requests[0].reject(new DOMException('Denied', 'NotAllowedError'));
  await assert.rejects(request, CaptureCancelledError);
});
