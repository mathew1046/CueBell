/** GTCRN's fixed streaming contract: 16 kHz, periodic sqrt-Hann, 512 FFT, 256 hop. */
export const FFT_SIZE = 512;
export const HOP_SIZE = 256;

/** Radix-2 transform with double-precision intermediates and float32 model boundaries. */
export class RealFft {
  constructor() {
    this.real = new Float64Array(FFT_SIZE);
    this.imag = new Float64Array(FFT_SIZE);
    this.cos = Float64Array.from({ length: HOP_SIZE }, (_, i) => Math.cos(2 * Math.PI * i / FFT_SIZE));
    this.sin = Float64Array.from({ length: HOP_SIZE }, (_, i) => Math.sin(2 * Math.PI * i / FFT_SIZE));
    this.reverse = Uint16Array.from({ length: FFT_SIZE }, (_, i) => {
      let reversed = 0;
      for (let bit = 0; bit < 9; bit++) { reversed = reversed * 2 + (i & 1); i >>= 1; }
      return reversed;
    });
  }

  transform(inverse) {
    const { real, imag, reverse, cos, sin } = this;
    for (let i = 0; i < FFT_SIZE; i++) {
      const j = reverse[i];
      if (j > i) {
        [real[i], real[j]] = [real[j], real[i]];
        [imag[i], imag[j]] = [imag[j], imag[i]];
      }
    }
    for (let size = 2; size <= FFT_SIZE; size *= 2) {
      const half = size / 2, stride = FFT_SIZE / size;
      for (let base = 0; base < FFT_SIZE; base += size) {
        for (let k = 0; k < half; k++) {
          const a = base + k, b = a + half, index = k * stride;
          const s = inverse ? sin[index] : -sin[index];
          const r = real[b] * cos[index] - imag[b] * s;
          const im = real[b] * s + imag[b] * cos[index];
          real[b] = real[a] - r; imag[b] = imag[a] - im;
          real[a] += r; imag[a] += im;
        }
      }
    }
  }

  forward(input) {
    this.real.set(input);
    this.imag.fill(0);
    this.transform(false);
    const spectrum = new Float32Array((HOP_SIZE + 1) * 2);
    for (let k = 0; k <= HOP_SIZE; k++) {
      spectrum[2 * k] = this.real[k]; spectrum[2 * k + 1] = this.imag[k];
    }
    return spectrum;
  }

  inverse(spectrum) {
    for (let k = 0; k <= HOP_SIZE; k++) {
      this.real[k] = spectrum[2 * k];
      this.imag[k] = k === 0 || k === HOP_SIZE ? 0 : spectrum[2 * k + 1];
      if (k > 0 && k < HOP_SIZE) {
        this.real[FFT_SIZE - k] = this.real[k]; this.imag[FFT_SIZE - k] = -this.imag[k];
      }
    }
    this.transform(true);
    return Float32Array.from(this.real, value => value / FFT_SIZE);
  }
}

/** Two sequential model hops per relay packet, retaining 16 ms of sample alignment. */
export class StreamingStft {
  constructor(infer) {
    this.infer = infer;
    this.fft = new RealFft();
    this.window = Float32Array.from({ length: FFT_SIZE }, (_, i) =>
      Math.sqrt(Math.fround(0.5 - 0.5 * Math.cos(2 * Math.PI * i / FFT_SIZE))));
    this.analysis = new Float32Array(FFT_SIZE);
    this.overlap = new Float32Array(FFT_SIZE);
    this.windowed = new Float32Array(FFT_SIZE);
    this.started = false;
  }

  async process(frame) {
    if (frame.byteLength !== FFT_SIZE * 2) throw new Error('Expected 512 PCM16LE samples');
    const input = new DataView(frame), output = new ArrayBuffer(FFT_SIZE * 2), pcm = new DataView(output);
    for (let offset = 0; offset < FFT_SIZE; offset += HOP_SIZE) {
      this.analysis.copyWithin(0, HOP_SIZE);
      for (let i = 0; i < HOP_SIZE; i++) this.analysis[HOP_SIZE + i] = input.getInt16((offset + i) * 2, true) / 32768;
      for (let i = 0; i < FFT_SIZE; i++) this.windowed[i] = this.analysis[i] * this.window[i];
      const spectrum = await this.infer(this.fft.forward(this.windowed));
      if (!(spectrum instanceof Float32Array) || spectrum.length !== 514 || !spectrum.every(Number.isFinite)) {
        throw new Error('Invalid GTCRN spectrum');
      }
      const wave = this.fft.inverse(spectrum);
      this.overlap.copyWithin(0, HOP_SIZE);
      this.overlap.fill(0, HOP_SIZE);
      for (let i = 0; i < FFT_SIZE; i++) this.overlap[i] += Math.fround(wave[i] * this.window[i]);
      if (this.started) {
        for (let i = 0; i < HOP_SIZE; i++) {
          const value = this.overlap[i];
          if (!Number.isFinite(value)) throw new Error('Invalid GTCRN waveform');
          pcm.setInt16((offset + i) * 2, Math.round(Math.max(-1, Math.min(32767 / 32768, value)) * 32768), true);
        }
      }
      // The first hop has no preceding speech. Leave precisely 256 samples of startup padding.
      this.started = true;
    }
    return output;
  }
}
