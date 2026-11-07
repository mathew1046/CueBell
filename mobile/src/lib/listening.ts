import type { NativeSnapshot } from './types';

export type ListeningPhase =
  | 'IDLE' | 'REQUESTING_PERMISSION' | 'CONNECTING' | 'LISTENING'
  | 'PROCESSING' | 'RECONNECTING' | 'STOPPING' | 'ERROR';

export type CaptureOperation = {
  mode: 'request' | 'monitor';
  phase: 'REQUESTING_PERMISSION' | 'CONNECTING' | 'PROCESSING' | 'STOPPING';
};

export function listeningPhase(
  native: Pick<NativeSnapshot, 'state' | 'running'>,
  operation: CaptureOperation | null,
  failed: boolean,
): ListeningPhase {
  if (operation) return operation.phase;
  if (native.state === 'ERROR' || native.state === 'DISCONNECTED') return 'ERROR';
  if (!native.running) return failed ? 'ERROR' : 'IDLE';
  switch (native.state) {
    case 'PROCESSING': return 'PROCESSING';
    case 'LISTENING': return 'LISTENING';
    case 'DEGRADED':
    case 'RECONNECTING': return 'RECONNECTING';
    case 'STOPPING': return 'STOPPING';
    default: return 'CONNECTING';
  }
}
