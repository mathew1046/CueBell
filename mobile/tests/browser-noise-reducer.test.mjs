import assert from 'node:assert/strict';
import test from 'node:test';
import { BrowserNoiseReducer } from '../modules/queue-listener/browser-noise-reducer.ts';
import { RealFft, StreamingStft } from '../public/audio/gtcrn-dsp.mjs';

function pcm(start = 0) {
  const buffer = new ArrayBuffer(1024), view = new DataView(buffer);
  for (let i = 0; i < 512; i++) view.setInt16(i * 2, ((start + i) % 65536) - 32768, true);
  return buffer;
}
function samples(buffer) { return Array.from({ length: buffer.byteLength / 2 }, (_, i) => new DataView(buffer).getInt16(i * 2, true)); }

test('FFT matches an independent direct DFT, including DC and Nyquist', () => {
  const input = Float32Array.from({ length: 512 }, (_, n) => 0.1 + 0.2 * Math.sin(n * 0.31) + 0.3 * Math.cos(n * Math.PI));
  const fft = new RealFft(), actual = fft.forward(input), expected = new Float32Array(514);
  for (let bin = 0; bin <= 256; bin++) {
    let real = 0, imag = 0;
    for (let n = 0; n < 512; n++) {
      real += input[n] * Math.cos(-2 * Math.PI * bin * n / 512);
      imag += input[n] * Math.sin(-2 * Math.PI * bin * n / 512);
    }
    expected[bin * 2] = real; expected[bin * 2 + 1] = imag;
  }
  for (let i = 0; i < 514; i++) assert.ok(Math.abs(actual[i] - expected[i]) < 0.0001, `spectrum ${i}`);
  const reconstructed = fft.inverse(expected);
  for (let i = 0; i < 512; i++) assert.ok(Math.abs(reconstructed[i] - input[i]) < 0.000001, `waveform ${i}`);
});

test('identity STFT preserves PCM samples and exactly 256 samples of streaming alignment', async () => {
  const stream = new StreamingStft(async spectrum => spectrum);
  const input = [], output = [];
  let seed = 17;
  for (let frame = 0; frame < 12; frame++) {
    const buffer = new ArrayBuffer(1024), view = new DataView(buffer);
    for (let i = 0; i < 512; i++) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      view.setInt16(i * 2, (seed & 65535) - 32768, true);
    }
    input.push(...samples(buffer));
    const processed = await stream.process(buffer);
    assert.equal(processed.byteLength, 1024);
    output.push(...samples(processed));
  }
  assert.deepEqual(output.slice(0, 256), Array(256).fill(0));
  for (let i = 256; i < output.length; i++) assert.ok(Math.abs(output[i] - input[i - 256]) <= 1, `PCM sample ${i}`);
});

test('STFT rejects invalid frames and invalid model output rather than transmitting corrupt audio', async () => {
  const stream = new StreamingStft(async () => new Float32Array(514).fill(NaN));
  await assert.rejects(stream.process(new ArrayBuffer(2)), /512 PCM16LE/);
  await assert.rejects(stream.process(pcm()), /Invalid GTCRN spectrum/);
});

function fixture(t) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let clock = 0;
  t.mock.method(performance, 'now', () => clock);
  const frames = [], statuses = [];
  const worker = {
    messages: [], terminated: false,
    postMessage(message) { this.messages.push(message); },
    terminate() { this.terminated = true; },
    reply(data) { this.onmessage?.({ data }); },
  };
  const reducer = new BrowserNoiseReducer(packet => frames.push(packet.frame), status => statuses.push(status), () => worker);
  t.after(() => reducer.close());
  return { reducer, worker, frames, statuses, setClock: value => { clock = value; } };
}

test('a timely worker frame is forwarded immediately, retaining the original packet for fallback', async t => {
  const { reducer, worker, frames, statuses } = fixture(t);
  worker.reply({ type: 'ready' });
  await reducer.ready;
  const original = pcm();
  reducer.push({ frame: original, rms: 0.5 });
  assert.equal(worker.messages.length, 1);
  assert.notEqual(worker.messages[0].frame, original);
  assert.deepEqual(worker.messages[0].frame, original);
  const enhanced = pcm(100);
  worker.reply({ type: 'frame', id: 0, frame: enhanced, processingMs: 2 });
  assert.equal(frames[0], enhanced);
  assert.equal(statuses.at(-1).activeMode, 'gtcrn');
  t.mock.timers.tick(32);
  assert.equal(worker.terminated, false);
});

test('initialization failure falls back to unshifted raw audio and resolves readiness', async t => {
  const { reducer, worker, frames, statuses } = fixture(t);
  worker.reply({ type: 'failed', reason: 'initialization_error' });
  await reducer.ready;
  const input = pcm();
  reducer.push({ frame: input, rms: 0.5 });
  assert.equal(frames[0], input);
  assert.equal(statuses.at(-1).fallbackReason, 'initialization_error');
  assert.equal(worker.terminated, true);
});

test('runtime failure preserves pending raw samples and the established 16 ms alignment', async t => {
  const { reducer, worker, frames } = fixture(t);
  worker.reply({ type: 'ready' });
  await reducer.ready;
  const input = [pcm(0), pcm(512), pcm(1024)];
  reducer.push({ frame: input[0], rms: 0.5 });
  worker.reply({ type: 'frame', id: 0, frame: new ArrayBuffer(1024), processingMs: 2 });
  reducer.push({ frame: input[1], rms: 0.5 });
  reducer.push({ frame: input[2], rms: 0.5 });
  worker.reply({ type: 'failed', reason: 'inference_error' });
  assert.equal(frames.length, 3);
  assert.deepEqual(samples(frames[1]), [...samples(input[0]).slice(256), ...samples(input[1]).slice(0, 256)]);
  assert.deepEqual(samples(frames[2]), [...samples(input[1]).slice(256), ...samples(input[2]).slice(0, 256)]);
});

test('a browser packet burst is processed immediately in order without any batching delay', async t => {
  const { reducer, worker, frames, setClock } = fixture(t);
  worker.reply({ type: 'ready' });
  await reducer.ready;
  reducer.push({ frame: pcm(), rms: 0.5 });
  reducer.push({ frame: pcm(512), rms: 0.5 });
  assert.equal(worker.messages.length, 1);
  setClock(4);
  const first = pcm(100), second = pcm(200);
  worker.reply({ type: 'frame', id: 0, frame: first, processingMs: 4 });
  assert.equal(worker.messages.length, 2);
  assert.deepEqual(frames, [first]);
  setClock(8);
  worker.reply({ type: 'frame', id: 1, frame: second, processingMs: 4 });
  assert.deepEqual(frames, [first, second]);
  assert.equal(worker.terminated, false);
});

test('waiting time counts toward the same 32 ms deadline', async t => {
  const { reducer, worker, frames, statuses, setClock } = fixture(t);
  worker.reply({ type: 'ready' });
  await reducer.ready;
  reducer.push({ frame: pcm(), rms: 0.5 });
  setClock(1);
  reducer.push({ frame: pcm(512), rms: 0.5 });
  setClock(20);
  worker.reply({ type: 'frame', id: 0, frame: pcm(100), processingMs: 20 });
  t.mock.timers.tick(12);
  assert.equal(frames.length, 1);
  t.mock.timers.tick(1);
  assert.equal(frames.length, 2);
  assert.equal(statuses.at(-1).fallbackReason, 'processing_overrun');
});

test('a third overlapping packet triggers ordered raw fallback instead of growing the backlog', async t => {
  const { reducer, worker, frames, statuses } = fixture(t);
  worker.reply({ type: 'ready' });
  await reducer.ready;
  const input = [pcm(), pcm(512), pcm(1024)];
  for (const frame of input) reducer.push({ frame, rms: 0.5 });
  assert.equal(worker.messages.length, 1);
  assert.deepEqual(frames, input);
  assert.equal(statuses.at(-1).fallbackReason, 'processing_overrun');
  worker.reply({ type: 'frame', id: 0, frame: pcm(999), processingMs: 1 });
  assert.equal(frames.length, 3);
});

test('32 ms deadline covers worker hangs and message scheduling, not only inference time', async t => {
  const { reducer, worker, frames, statuses } = fixture(t);
  worker.reply({ type: 'ready' });
  await reducer.ready;
  reducer.push({ frame: pcm(), rms: 0.5 });
  t.mock.timers.tick(31);
  assert.equal(frames.length, 0);
  t.mock.timers.tick(1);
  assert.equal(frames.length, 1);
  assert.equal(statuses.at(-1).fallbackReason, 'processing_overrun');
});

test('a delayed reply is rejected even if its timer has not yet executed', async t => {
  const { reducer, worker, frames, setClock } = fixture(t);
  worker.reply({ type: 'ready' });
  await reducer.ready;
  const raw = pcm();
  reducer.push({ frame: raw, rms: 0.5 });
  setClock(33);
  worker.reply({ type: 'frame', id: 0, frame: pcm(999), processingMs: 1 });
  assert.equal(frames[0], raw);
  assert.equal(worker.terminated, true);
});

test('stop discards pending audio and ignores late worker callbacks', async t => {
  const { reducer, worker, frames, statuses } = fixture(t);
  worker.reply({ type: 'ready' });
  await reducer.ready;
  reducer.push({ frame: pcm(), rms: 0.5 });
  reducer.push({ frame: pcm(512), rms: 0.5 });
  reducer.close();
  worker.reply({ type: 'frame', id: 0, frame: pcm(999), processingMs: 1 });
  worker.reply({ type: 'failed' });
  t.mock.timers.tick(10000);
  assert.equal(frames.length, 0);
  assert.equal(statuses.length, 1);
  assert.equal(worker.terminated, true);
});

test('closing or timing out initialization always settles readiness', async t => {
  const { reducer, statuses } = fixture(t);
  t.mock.timers.tick(10000);
  await reducer.ready;
  assert.equal(statuses.at(-1).fallbackReason, 'initialization_timeout');
  const pending = new BrowserNoiseReducer(() => {}, () => {}, () => ({ terminate() {} }));
  pending.close();
  await pending.ready;
});
