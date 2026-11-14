import type { NoiseReductionMode } from '../../modules/queue-listener';
import type { CaptureOperation } from './listening';
import type { NativeSnapshot } from './types';

export function readNoiseReductionMode(value: unknown): NoiseReductionMode {
  return value === 'gtcrn' ? 'gtcrn' : 'off';
}

/** Keep the selection fixed through permission prompts, setup and request handoff. */
export function canChangeNoiseReduction(
  native: Pick<NativeSnapshot, 'running'>,
  operation: CaptureOperation | null,
  busy: boolean,
): boolean {
  return !native.running && !operation && !busy;
}

export function isNoiseReductionFallback(native: Pick<NativeSnapshot, 'running' | 'noiseReduction'>): boolean {
  const status = native.noiseReduction;
  return native.running && status?.requestedMode === 'gtcrn' && status.activeMode === 'off' && !!status.fallbackReason;
}
