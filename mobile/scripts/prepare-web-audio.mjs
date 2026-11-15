import { createHash } from 'node:crypto';
import { copyFile, mkdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const runtime = new URL('node_modules/onnxruntime-web/', root);
const assets = new URL('modules/queue-listener/android/src/main/assets/noise-reduction/', root);
const output = new URL('public/audio/vendor/', root);
const model = await readFile(new URL('gtcrn_simple.onnx', assets));
const expected = 'e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534';
if (createHash('sha256').update(model).digest('hex') !== expected) throw new Error('GTCRN model checksum mismatch');

await mkdir(new URL('licenses/', output), { recursive: true });
await Promise.all([
  ...['ort.wasm.min.mjs', 'ort-wasm-simd-threaded.mjs', 'ort-wasm-simd-threaded.wasm'].map(name =>
    copyFile(new URL(`dist/${name}`, runtime), new URL(name, output))),
  copyFile(new URL('gtcrn_simple.onnx', assets), new URL('gtcrn_simple.onnx', output)),
  copyFile(new URL('licenses/GTCRN-MIT.txt', assets), new URL('licenses/GTCRN-MIT.txt', output)),
  copyFile(new URL('licenses/ONNX-Runtime-MIT.txt', assets), new URL('licenses/ONNX-Runtime-MIT.txt', output)),
]);
console.log(`Prepared same-origin GTCRN and ONNX Runtime Web assets in ${fileURLToPath(output)}`);
