/* global AudioWorkletProcessor, sampleRate, registerProcessor */
import { PcmFramer } from './pcm.mjs';

class CueBellCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.framer = new PcmFramer(sampleRate, (frame, rms) => {
      this.port.postMessage({ frame, rms }, [frame]);
    });
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) this.framer.push(channel);
    return true;
  }
}

registerProcessor('cuebell-capture', CueBellCapture);
