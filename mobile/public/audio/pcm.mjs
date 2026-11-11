/** Streaming area resampler. Preserve fractional sample weights across audio quanta. */
export class PcmFramer {
  /** Allocate one PCM frame and retain fractional resampling state across worklet quanta. */
  constructor(sampleRate, emit) {
    if (!Number.isFinite(sampleRate) || sampleRate < 16000) throw new Error('Unsupported sample rate');
    this.ratio = sampleRate / 16000;
    this.emit = emit;
    this.sum = 0;
    this.weight = 0;
    this.offset = 0;
    this.energy = 0;
    this.frame = new ArrayBuffer(1024);
    this.view = new DataView(this.frame);
  }

  /** Downsample finite bounded input and emit complete 512-sample little-endian frames with RMS. */
  push(samples) {
    for (let index = 0; index < samples.length; index++) {
      const sample = Number.isFinite(samples[index]) ? Math.max(-1, Math.min(1, samples[index])) : 0;
      let remaining = 1;
      while (remaining > 1e-8) {
        const take = Math.min(remaining, this.ratio - this.weight);
        this.sum += sample * take;
        this.weight += take;
        remaining -= take;
        if (this.weight >= this.ratio - 1e-8) {
          const value = this.sum / this.ratio;
          this.view.setInt16(this.offset, Math.round(value * (value < 0 ? 32768 : 32767)), true);
          this.energy += value * value;
          this.offset += 2;
          this.sum = 0;
          this.weight = 0;
          if (this.offset === 1024) {
            this.emit(this.frame, Math.sqrt(this.energy / 512));
            this.frame = new ArrayBuffer(1024);
            this.view = new DataView(this.frame);
            this.offset = 0;
            this.energy = 0;
          }
        }
      }
    }
  }
}
