import * as ort from './vendor/ort.wasm.min.mjs';
import { StreamingStft } from './gtcrn-dsp.mjs';

const shapes = { conv_cache: [2, 1, 16, 16, 33], tra_cache: [2, 3, 1, 1, 16], inter_cache: [2, 1, 33, 16] };
let session, states, stream;
let busy = false;

function resetStates() {
  for (const tensor of Object.values(states ?? {})) tensor.dispose();
  states = Object.fromEntries(Object.entries(shapes).map(([name, shape]) =>
    [name, new ort.Tensor('float32', new Float32Array(shape.reduce((a, b) => a * b, 1)), shape)]));
  stream = new StreamingStft(infer);
}

async function infer(spectrum) {
  const mix = new ort.Tensor('float32', spectrum, [1, 257, 1, 2]);
  let result;
  try { result = await session.run({ mix, ...states }); }
  finally { mix.dispose(); }
  for (const [name, previous] of Object.entries(states)) {
    previous.dispose();
    states[name] = result[`${name}_out`];
  }
  const output = new Float32Array(result.enh.data);
  result.enh.dispose();
  return output;
}

async function initialize() {
  // A dedicated worker owns inference. Single-threaded WASM also works without COOP/COEP.
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.proxy = false;
  ort.env.wasm.wasmPaths = new URL('./vendor/', import.meta.url).href;
  const response = await fetch(new URL('./vendor/gtcrn_simple.onnx', import.meta.url));
  if (!response.ok) throw new Error('Model unavailable');
  const model = await response.arrayBuffer();
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', model)), value => value.toString(16).padStart(2, '0')).join('');
  if (hash !== 'e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534') throw new Error('Model checksum mismatch');
  session = await ort.InferenceSession.create(model, { executionProviders: ['wasm'], graphOptimizationLevel: 'all' });
  const expected = { mix: [1, 257, 1, 2], ...shapes };
  if (session.inputMetadata.length !== 4 || session.inputMetadata.some(input =>
    input.type !== 'float32' || JSON.stringify(input.shape) !== JSON.stringify(expected[input.name]))) {
    throw new Error('Unexpected model contract');
  }
  resetStates();
  // Compile and warm up before microphone frames arrive, then discard all recurrent state.
  for (let i = 0; i < 4; i++) await stream.process(new ArrayBuffer(1024));
  resetStates();
  self.postMessage({ type: 'ready' });
}

self.onmessage = async ({ data }) => {
  if (data?.type !== 'frame' || !stream || busy) { self.postMessage({ type: 'failed', reason: 'invalid_worker_state' }); return; }
  busy = true;
  try {
    const start = performance.now();
    const frame = await stream.process(data.frame);
    self.postMessage({ type: 'frame', id: data.id, frame, processingMs: performance.now() - start }, [frame]);
  } catch { self.postMessage({ type: 'failed', reason: 'inference_error' }); }
  finally { busy = false; }
};

void initialize().catch(() => self.postMessage({ type: 'failed', reason: 'initialization_error' }));
