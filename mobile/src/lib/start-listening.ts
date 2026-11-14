import type { NoiseReductionMode } from '../../modules/queue-listener';

/** A cancelled/permission-revoked activation must never reopen the microphone later. */
export async function startListeningIfCurrent(
  current: () => boolean,
  activate: () => Promise<void>,
  start: (options: { noiseReductionMode: NoiseReductionMode }) => Promise<void>,
  noiseReductionMode: NoiseReductionMode = 'off',
): Promise<void> {
  if (!current()) return;
  await activate();
  if (!current()) return;
  await start({ noiseReductionMode });
}
