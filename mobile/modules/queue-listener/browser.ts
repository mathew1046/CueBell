import type { NativeSnapshot, QueueEvent } from '../../src/lib/types';
import { CaptureCancelledError } from '../../src/lib/listening';
import { audioContext, clearAlerts, dismissAlert, setLanguage, setSpokenAlertsEnabled,
  showAlert, silenceAlerts, spokenAlertsEnabled } from './browser-alerts';

export { primeAudio } from './browser-alerts';

let prepared: MediaStream | null = null;
let permissionGeneration = 0;
let permissionRequest: Promise<void> | null = null;

const cancelHiddenPermission = () => {
  if (document.visibilityState === 'hidden') releasePreparedMicrophone();
};

/** Invalidate pending grants and release capture permission resources before closing a session. */
export function releasePreparedMicrophone(): void {
  permissionGeneration++;
  permissionRequest = null;
  prepared?.getTracks().forEach(track => track.stop());
  prepared = null;
  document.removeEventListener('visibilitychange', cancelHiddenPermission);
  window.removeEventListener('pagehide', releasePreparedMicrophone);
}

/** Share pending permission requests so concurrent callers cannot acquire competing streams. */
export function requestMicrophone(): Promise<void> {
  if (permissionRequest) return permissionRequest;
  const request = acquireMicrophone().finally(() => {
    if (permissionRequest === request) permissionRequest = null;
  });
  permissionRequest = request;
  return request;
}

/** Retain one stream for capture and stop a late grant after cancellation or page hiding. */
async function acquireMicrophone(): Promise<void> {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
    throw new Error('Use a supported browser over HTTPS to allow microphone access.');
  }
  if (prepared?.getAudioTracks().some(track => track.readyState === 'live')) return;
  if (document.visibilityState === 'hidden') throw new Error('Keep CueBell visible while starting the microphone.');
  const attempt = permissionGeneration;
  document.addEventListener('visibilitychange', cancelHiddenPermission);
  window.addEventListener('pagehide', releasePreparedMicrophone);
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: {
      channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: true,
    } });
    if (attempt !== permissionGeneration || document.hidden) {
      stream.getTracks().forEach(track => track.stop());
      throw new CaptureCancelledError();
    }
    prepared = stream;
  } catch (error) {
    if (attempt !== permissionGeneration || document.hidden) throw new CaptureCancelledError();
    if (error instanceof DOMException && ['NotAllowedError', 'SecurityError'].includes(error.name)) {
      throw new Error('Microphone permission was denied. Allow microphone access in your browser site settings, then retry.');
    }
    throw error;
  }
}

/** Browser implementation of the Android listener contract, with one shared audio pipeline. */
export class BrowserListener {
  private state: NativeSnapshot = { running: false, state: 'STOPPED', message: 'Microphone is off.', mode: 'monitor', events: [] };
  private observers = new Set<(event: { json: string }) => void>();
  private stream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: AudioWorkletNode | null = null;
  private socket: WebSocket | null = null;
  private generation = 0;
  private retries = 0;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private watchdog: ReturnType<typeof setInterval> | undefined;
  private lastMessage = 0;
  private lastAudio = 0;
  private url = '';
  private token = '';
  private level = 0;
  private wake: WakeLockSentinel | null = null;
  private listeningSince = 0;
  private lifecycleAttached = false;

  snapshot = (): string => JSON.stringify(this.state);
  audioLevel = (): number => this.level;
  spokenAlertsEnabled = spokenAlertsEnabled;
  setSpokenAlertsEnabled = setSpokenAlertsEnabled;
  setLanguage = setLanguage;
  dismissAlert = dismissAlert;

  /** Subscribe through the shared native event contract and return an independent cleanup handle. */
  addListener(_name: 'onEvent', observer: (event: { json: string }) => void) {
    this.observers.add(observer);
    return { remove: () => { this.observers.delete(observer); } };
  }

  /** Clear in-memory history and notifications after explicit task replacement or deletion. */
  clear(): void {
    this.state.events = [];
    clearAlerts();
  }

  /** Retain a bounded event snapshot and notify subscribers without recording microphone data. */
  private emit(event: QueueEvent): void {
    if (event.type === 'status') {
      this.state.state = event.state ?? '';
      this.state.message = event.message ?? '';
    }
    if (!['heartbeat', 'pong'].includes(event.type)) {
      this.state.events.push(event);
      if (this.state.events.length > 100) this.state.events.shift();
    }
    const json = JSON.stringify(event);
    for (const observer of this.observers) observer({ json });
  }

  /** Publish microphone health through the same status events consumed by Android screens. */
  private status(state: string, message: string): void {
    this.emit({ type: 'status', state, message });
  }

  /** Stop every microphone track and disconnect worklet, waveform level and screen wake lock. */
  private releaseAudio(): void {
    this.level = 0;
    if (this.processor) {
      this.processor.port.onmessage = null;
      this.processor.port.close();
      this.processor.onprocessorerror = null;
      this.processor.disconnect();
    }
    this.processor = null;
    this.source?.disconnect();
    this.source = null;
    this.stream?.getTracks().forEach(track => { track.onended = null; track.onmute = null; track.stop(); });
    this.stream = null;
    if (this.wake) void this.wake.release().catch(() => {});
    this.wake = null;
  }

  /** Detach stale socket callbacks and stop transport timers before releasing local capture. */
  private closeTransport(): void {
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.onerror = null;
      this.socket.onmessage = null;
      this.socket.onopen = null;
      this.socket.close(1000);
    }
    this.socket = null;
    clearTimeout(this.retryTimer);
    clearInterval(this.watchdog);
    this.releaseAudio();
  }

  /** Stop hidden-page capture and require a visible, explicit user action to restart it. */
  private pageHidden = () => {
    if (!this.state.running) return;
    if (document.visibilityState === 'hidden') {
      void this.stop().then(() => this.status('STOPPED', 'Listening paused because this page is hidden. Return and tap Start Listening.'));
    }
  };

  private pageLeaving = () => { void this.stop(); };

  /** Start a secure visible-page stream or hand completed request capture over to its monitor. */
  async start(url: string, token: string, mode: 'request' | 'monitor'): Promise<void> {
    if (!/^https:\/\//.test(url) || !token) throw new Error('A secure HTTPS backend URL is required.');
    const handoff = this.state.running && this.state.mode === 'request' && this.state.state === 'PROCESSING';
    if (document.visibilityState === 'hidden') throw new Error('Keep CueBell visible while starting the microphone.');
    if (this.state.running && !handoff) throw new Error('A listening session is already active.');
    this.generation++;
    this.closeTransport();
    this.stream = prepared;
    prepared = null;
    this.url = url;
    this.token = token;
    this.retries = 0;
    this.state.mode = mode;
    this.state.running = true;
    if (!this.lifecycleAttached) {
      document.addEventListener('visibilitychange', this.pageHidden);
      window.addEventListener('pagehide', this.pageLeaving);
      this.lifecycleAttached = true;
    }
    this.status('STARTING', 'Connecting to speech recognition…');
    try { this.connect(); }
    catch (error) { await this.stop(); throw error; }
  }

  /** Invalidate asynchronous callbacks before releasing microphone, credentials and lifecycle hooks. */
  async stop(): Promise<void> {
    this.generation++;
    this.state.running = false;
    releasePreparedMicrophone();
    this.closeTransport();
    this.token = '';
    silenceAlerts();
    if (this.lifecycleAttached) {
      document.removeEventListener('visibilitychange', this.pageHidden);
      window.removeEventListener('pagehide', this.pageLeaving);
      this.lifecycleAttached = false;
    }
    this.status('STOPPED', 'Microphone is off.');
  }

  /** Authenticate before sending audio and route relay events through guarded session callbacks. */
  private connect(): void {
    const generation = ++this.generation;
    this.status(this.retries ? 'RECONNECTING' : 'STARTING', this.retries ?
      'Reconnecting. Calls may have been missed.' : 'Connecting to speech recognition…');
    const url = new URL('/v1/stream', this.url);
    url.protocol = 'wss:';
    url.searchParams.set('mode', this.state.mode);
    const socket = new WebSocket(url);
    this.socket = socket;
    this.lastMessage = Date.now();
    socket.onopen = () => {
      if (generation !== this.generation) return;
      // Browser WebSockets cannot set Authorization headers. Never put credentials in a URL.
      socket.send(JSON.stringify({ type: 'authenticate', token: this.token, consent: 'audio-gnani;text-openai' }));
    };
    socket.onmessage = ({ data }) => {
      if (generation !== this.generation) return;
      this.lastMessage = Date.now();
      try {
        if (typeof data !== 'string' || data.length > 65536) throw new Error('Invalid stream response.');
        const event: QueueEvent = JSON.parse(data);
        if (!event || typeof event.type !== 'string') throw new Error('Invalid stream response.');
        if (event.type === 'status') {
          if (event.state === 'READY') {
            void this.capture(generation).catch(error => this.fail(generation, error instanceof Error ? error.message : 'Microphone unavailable.', true));
          } else if (event.state === 'LISTENING') {
            this.listeningSince = Date.now();
            this.emit(event);
          } else if (['DISCONNECTED', 'DEGRADED'].includes(event.state ?? '')) {
            this.releaseAudio();
            this.status('RECONNECTING', event.message ?? 'Listening interrupted. Calls may have been missed.');
          } else if (event.state !== 'STARTING') this.emit(event);
        } else if (event.type === 'transcript' && this.state.mode === 'request') {
          this.generation++;
          this.closeTransport();
          this.status('PROCESSING', 'Creating your listening task…');
          this.emit(event);
        } else if (['monitor.pause', 'monitor.stop'].includes(event.type) && this.state.mode === 'monitor') {
          void this.stop();
          this.emit(event);
        } else {
          this.emit(event);
          showAlert(event);
        }
      } catch { this.fail(generation, 'The listening service returned an invalid response. Please try again.', true); }
    };
    socket.onclose = ({ code }) => this.fail(generation, code === 4403 || code === 4401 ?
      'Your listening session is unavailable. Submit your request again.' : 'Speech stream closed. Calls may have been missed.',
    [4401, 4403, 1008].includes(code));
    socket.onerror = () => this.fail(generation, 'Cannot reach the listening service. Check your internet connection.');
    this.watchdog = setInterval(() => {
      if (generation !== this.generation) return;
      if (Date.now() - this.lastMessage > 20000 || (this.processor && Date.now() - this.lastAudio > 2000)) {
        this.fail(generation, 'Audio or connection interrupted. Calls may have been missed.');
      }
    }, 1000);
  }

  /** Share one live microphone with local RMS and bounded PCM delivery after relay readiness. */
  private async capture(generation: number): Promise<void> {
    if (this.processor) return;
    const audio = audioContext();
    await audio.resume();
    if (audio.state !== 'running') throw new Error('Audio is suspended. Tap Start Listening to retry.');
    const stream = this.stream ?? await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } });
    if (generation !== this.generation) { stream.getTracks().forEach(track => track.stop()); return; }
    this.stream = stream;
    await audio.audioWorklet.addModule('/audio/capture-worklet.js');
    if (generation !== this.generation) return;
    const source = audio.createMediaStreamSource(stream);
    const processor = new AudioWorkletNode(audio, 'cuebell-capture', { channelCount: 1, channelCountMode: 'explicit' });
    this.source = source;
    this.processor = processor;
    this.lastAudio = Date.now();
    processor.port.onmessage = ({ data }: MessageEvent<{ frame: ArrayBuffer; rms: number }>) => {
      if (generation !== this.generation || !this.socket) return;
      const now = Date.now();
      if (now - this.lastAudio > 500 || this.socket.bufferedAmount > 8192 || this.socket.readyState !== WebSocket.OPEN) {
        this.fail(generation, 'Audio frames were dropped. A call may be missed.');
        return;
      }
      this.lastAudio = now;
      this.level = data.rms;
      this.socket.send(data.frame);
      if (now - this.listeningSince > 30000 && this.state.state === 'LISTENING') this.retries = 0;
    };
    processor.onprocessorerror = () => this.fail(generation, 'Microphone processing was interrupted.', true);
    stream.getAudioTracks().forEach(track => {
      track.onended = () => this.fail(generation, 'Microphone access ended. Allow access and retry.', true);
      track.onmute = () => this.fail(generation, 'Microphone access ended. Allow access and retry.', true);
    });
    // Worklet output is silent. The connection keeps processing active without microphone playback.
    source.connect(processor).connect(audio.destination);
    if ('wakeLock' in navigator) {
      void navigator.wakeLock.request('screen').then(wake => {
        if (generation === this.generation) this.wake = wake;
        else void wake.release();
      }).catch(() => {});
    }
  }

  /** End stale capture immediately and retry eligible monitors with bounded exponential delays. */
  private fail(generation: number, reason: string, permanent = false): void {
    if (generation !== this.generation || !this.state.running) return;
    this.generation++;
    this.closeTransport();
    releasePreparedMicrophone();
    if (permanent || this.state.mode === 'request' || this.retries >= 5 || document.visibilityState === 'hidden') {
      void this.stop();
      this.status('ERROR', `${reason} Try again from the app.`);
      return;
    }
    const delay = 1000 * 2 ** this.retries++;
    this.status('RECONNECTING', `${reason} Retrying in ${delay / 1000}s.`);
    this.retryTimer = setTimeout(() => this.connect(), delay);
  }
}

export default new BrowserListener();
