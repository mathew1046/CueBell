import type { NativeNoiseReduction } from '../../src/lib/types';

type Packet = { frame: ArrayBuffer; rms: number };
type Pending = Packet & { id: number; sentAt: number };

/** One inference plus one browser-burst packet, both bounded by a 32 ms arrival-to-output deadline. */
export class BrowserNoiseReducer {
  readonly ready: Promise<void>;
  private settleReady!: () => void;
  private worker: Worker | null = null;
  private pending: Pending | null = null;
  private waiting: Pending | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private active = false;
  private closed = false;
  private failure: string | null = null;
  private nextId = 0;
  private delayed = false;
  private rawTail = new Uint8Array(512);
  private emit: (packet: Packet) => void;
  private changed: (status: NativeNoiseReduction) => void;

  constructor(
    emit: (packet: Packet) => void,
    changed: (status: NativeNoiseReduction) => void,
    createWorker: () => Worker = () => new Worker('/audio/gtcrn-worker.mjs', { type: 'module', name: 'cuebell-gtcrn' }),
  ) {
    this.emit = emit;
    this.changed = changed;
    this.ready = new Promise(resolve => { this.settleReady = resolve; });
    try {
      this.worker = createWorker();
      this.timer = setTimeout(() => this.fallback('initialization_timeout'), 10000);
      this.worker.onmessage = ({ data }) => {
        if (this.closed || this.failure) return;
        if (data?.type === 'ready' && !this.active) {
          clearTimeout(this.timer);
          this.active = true;
          this.changed(this.status);
          this.settleReady();
        } else if (data?.type === 'frame') {
          const packet = this.pending;
          if (!packet || data.id !== packet.id || !(data.frame instanceof ArrayBuffer) || data.frame.byteLength !== 1024 ||
            !Number.isFinite(data.processingMs) || data.processingMs < 0) {
            this.fallback('invalid_output'); return;
          }
          // Include message scheduling in the deadline, not just the model's own timer.
          if (performance.now() - packet.sentAt >= 32 || data.processingMs >= 32) {
            this.fallback('processing_overrun'); return;
          }
          clearTimeout(this.timer);
          this.pending = null;
          this.rawTail.set(new Uint8Array(packet.frame, 512));
          this.delayed = true;
          this.emit({ frame: data.frame, rms: packet.rms });
          const next = this.waiting;
          this.waiting = null;
          if (next) this.dispatch(next);
        } else {
          this.fallback(data?.type === 'failed' && data.reason === 'initialization_error' ? 'initialization_error' : 'inference_error');
        }
      };
      this.worker.onerror = event => { event.preventDefault(); this.fallback('worker_error'); };
      this.worker.onmessageerror = () => this.fallback('worker_message_error');
    } catch { this.fallback('worker_unavailable'); }
  }

  get status(): NativeNoiseReduction {
    return { requestedMode: 'gtcrn', activeMode: this.active && !this.closed ? 'gtcrn' : 'off', fallbackReason: this.failure };
  }

  push(packet: Packet): void {
    if (this.closed) return;
    if (packet.frame.byteLength !== 1024) throw new Error('Expected 512 PCM16LE samples');
    // Worklet messages can arrive in a burst. Allow one waiting packet, never an accumulating backlog.
    if (this.waiting) this.fallback('processing_overrun');
    if (this.closed) return;
    if (!this.active || !this.worker) { this.emitRaw(packet); return; }
    const next = { ...packet, id: this.nextId++, sentAt: performance.now() };
    if (this.pending) { this.waiting = next; return; }
    this.dispatch(next);
  }

  private dispatch(packet: Pending): void {
    if (this.closed || !this.worker) return;
    this.pending = packet;
    // Waiting does not reset the deadline: every packet is measured from its arrival.
    const remaining = 32 - (performance.now() - packet.sentAt);
    if (remaining <= 0) { this.fallback('processing_overrun'); return; }
    this.timer = setTimeout(() => this.fallback('processing_overrun'), remaining);
    const copy = packet.frame.slice(0); // Retain the original until success so fail-open cannot lose audio.
    try { this.worker.postMessage({ type: 'frame', id: packet.id, frame: copy }, [copy]); }
    catch { this.fallback('worker_message_error'); }
  }

  private emitRaw(packet: Packet): void {
    if (this.closed) return;
    if (!this.delayed) { this.emit(packet); return; }
    const bytes = new Uint8Array(packet.frame), output = new Uint8Array(1024);
    output.set(this.rawTail);
    output.set(bytes.subarray(0, 512), 512);
    this.rawTail.set(bytes.subarray(512));
    this.emit({ frame: output.buffer, rms: packet.rms });
  }

  private fallback(reason: string): void {
    if (this.closed || this.failure) return;
    this.failure = reason;
    this.active = false;
    clearTimeout(this.timer);
    this.worker?.terminate();
    this.worker = null;
    this.changed(this.status);
    this.settleReady();
    const packet = this.pending;
    const waiting = this.waiting;
    this.pending = null;
    this.waiting = null;
    if (packet) this.emitRaw(packet);
    if (waiting) this.emitRaw(waiting);
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.active = false;
    clearTimeout(this.timer);
    this.worker?.terminate();
    this.worker = null;
    this.pending = null;
    this.waiting = null;
    this.rawTail.fill(0);
    this.settleReady();
  }
}
