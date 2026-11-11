import assert from 'node:assert/strict';
import test from 'node:test';
import { PcmFramer } from '../public/audio/pcm.mjs';

for (const rate of [16000, 44100, 48000, 96000]) {
  test(`resamples ${rate} Hz to exactly 16 kHz mono PCM16LE frames`, () => {
    const frames = [];
    const levels = [];
    const framer = new PcmFramer(rate, (frame, rms) => { frames.push(frame); levels.push(rms); });
    const audio = new Float32Array(rate).fill(0.25);
    for (let offset = 0; offset < audio.length; offset += 128) framer.push(audio.subarray(offset, offset + 128));
    assert.equal(frames.length, Math.floor(16000 / 512));
    for (const frame of frames) {
      assert.equal(frame.byteLength, 1024);
      const pcm = new DataView(frame);
      for (let offset = 0; offset < 1024; offset += 2) assert.equal(pcm.getInt16(offset, true), 8192);
    }
    assert.ok(levels.every(rms => Math.abs(rms - 0.25) < 1e-7));
  });
}

test('fractional resampling preserves output across arbitrary worklet boundaries', () => {
  const audio = Float32Array.from({ length: 44100 }, (_, index) => 0.8 * Math.sin(index / 17));
  const once = [], split = [];
  new PcmFramer(44100, frame => once.push(Buffer.from(frame))).push(audio);
  const streaming = new PcmFramer(44100, frame => split.push(Buffer.from(frame)));
  for (let offset = 0; offset < audio.length; offset += 127) streaming.push(audio.subarray(offset, offset + 127));
  assert.deepEqual(split, once);
});

test('silence has zero activity and loud input remains bounded signed PCM', () => {
  const output = [];
  const framer = new PcmFramer(16000, (frame, rms) => output.push({ pcm: new DataView(frame), rms }));
  for (const value of [0, 2, -2, NaN]) framer.push(new Float32Array(512).fill(value));
  assert.deepEqual(output.map(({ pcm }) => pcm.getInt16(0, true)), [0, 32767, -32768, 0]);
  assert.deepEqual(output.map(({ rms }) => rms), [0, 1, 1, 0]);
});
