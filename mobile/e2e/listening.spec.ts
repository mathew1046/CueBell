import { expect, test, type Page, type WebSocketRoute } from '@playwright/test';
import catalogs from '../src/lib/i18n/catalogs.json';

const service = process.env.EXPO_PUBLIC_API_URL || 'https://cuebell.mathewjoseph.xyz';
const intent = { intent: 'monitor_announcement', context: 'hospital_pharmacy', token: '42',
  alert_preferences: ['visual', 'vibration', 'sound'], clarification: null };
const rule = { id: 'rule-42', token: '42', status: 'ACTIVE', alert_preferences: intent.alert_preferences };

/** Mock provider output at the relay boundary; exercise real browser capture and rendering. */
async function relay(page: Page, options: { busyAttempts?: number } = {}) {
  const sockets: WebSocketRoute[] = [];
  const frames: number[] = [];
  const calls: string[] = [];
  let busyAttempts = options.busyAttempts ?? 0;
  let active = false;
  await page.addInitScript(() => {
    const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    const streams: MediaStream[] = [];
    Object.defineProperty(window, 'cuebellTestStreams', { value: streams });
    navigator.mediaDevices.getUserMedia = async constraints => {
      const stream = await capture(constraints);
      streams.push(stream);
      return stream;
    };
  });
  await page.route(`${service}/**`, async route => {
    const path = new URL(route.request().url()).pathname;
    calls.push(path);
    const data = path === '/v1/sessions' ? { token: 'browser-test-session', expires_at: Date.now() / 1000 + 3600 } :
      path === '/v1/intent' ? { status: 'confirm', proposal_id: 'proposal-42', intent } :
      path === '/v1/state' ? { rule: active ? rule : null, history: [], alerts: [] } :
      path === '/v1/control' && route.request().postDataJSON()?.action === 'acknowledge' ?
        { type: 'alert.acknowledged', sequence: 101, alert: { id: 'alert-42', token: '42', counter: '3', state: 'acknowledged', alert_preferences: ['visual'] } } :
      { type: 'monitor.created', rule };
    if (path === '/v1/confirm') active = true;
    await route.fulfill({ json: data, headers: { 'Access-Control-Allow-Origin': '*' } });
  });
  await page.routeWebSocket(`${service.replace(/^http/, 'ws')}/v1/stream*`, socket => {
    sockets.push(socket);
    let sentListening = false;
    socket.onMessage(message => {
      if (typeof message === 'string') {
        const auth = JSON.parse(message);
        expect(auth).toEqual({ type: 'authenticate', token: 'browser-test-session', consent: 'audio-gnani;text-openai' });
        expect(new URL(socket.url()).searchParams.has('token')).toBe(false);
        if (busyAttempts-- > 0) {
          socket.close({ code: 4409 });
          return;
        }
        socket.send(JSON.stringify({ type: 'status', state: 'STARTING' }));
        socket.send(JSON.stringify({ type: 'status', state: 'READY' }));
      } else {
        frames.push(message.byteLength);
        if (!sentListening) { socket.send(JSON.stringify({ type: 'status', state: 'LISTENING' })); sentListening = true; }
      }
    });
  });
  return { sockets, frames, calls };
}

async function typedTask(page: Page) {
  await page.goto('/token');
  await page.getByRole('checkbox', { name: 'Allow audio & text processing' }).click();
  await page.getByLabel('Listen for…').fill('Tell me when token 42 is called with vibration and sound.');
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Stop');
}

test('initial Home is accessible, installable, and never asks for the microphone', async ({ page }) => {
  await page.addInitScript(() => {
    const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    Object.defineProperty(window, 'captureRequests', { value: [] });
    navigator.mediaDevices.getUserMedia = constraints => {
      (window as unknown as { captureRequests: unknown[] }).captureRequests.push(constraints);
      return capture(constraints);
    };
  });
  await page.goto('/');
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start');
  expect(await page.evaluate(() => (window as unknown as { captureRequests: unknown[] }).captureRequests)).toEqual([]);
  await expect(page.getByText('Listening in your browser')).toBeVisible();
  expect((await (await page.request.get('/manifest.webmanifest')).json()).display).toBe('standalone');
  await expect(async () => {
    await page.getByRole('button', { name: 'History', exact: true }).focus();
    await expect(page.getByRole('button', { name: 'History', exact: true })).toBeFocused({ timeout: 500 });
  }).toPass();
});

test.describe('real-time browser noise reduction', () => {
test('browser restores opt-in noise reduction, runs the real model, and releases its worker on stop', async ({ page }) => {
  const mock = await relay(page);
  await page.addInitScript(() => {
    localStorage.setItem('cuebell.noise-reduction.v1', 'gtcrn');
    const workers = { outputs: 0, terminated: 0, events: [] as unknown[] };
    Object.defineProperty(window, 'cuebellTestWorkers', { value: workers });
    const Original = Worker;
    window.Worker = class extends Original {
      constructor(url: string | URL, options?: WorkerOptions) {
        super(url, options);
        workers.events.push(['created']);
        this.addEventListener('message', ({ data }) => {
          workers.events.push([data?.type, data?.reason, data?.processingMs]);
          if (data?.type === 'frame') workers.outputs++;
        });
        this.addEventListener('error', error => workers.events.push(['error', error.message]));
      }
      terminate() { workers.terminated++; workers.events.push(['terminated', new Error().stack]); super.terminate(); }
    };
  });
  await page.goto('/settings');
  await expect(page.getByRole('switch', { name: 'Spoken alerts' })).toBeVisible();
  await expect(page.getByRole('switch', { name: 'Noise reduction', exact: true })).toBeChecked();
  await expect(page.getByText('Noise reduction could not be restored. Off is selected.', { exact: true })).toHaveCount(0);
  await typedTask(page);
  await expect.poll(() => page.evaluate(() => (window as unknown as { cuebellTestWorkers: { outputs: number } }).cuebellTestWorkers.outputs)).toBeGreaterThan(5)
    .catch(async error => { console.log('GTCRN capture diagnostics:', await page.evaluate(() => (window as unknown as { cuebellTestWorkers: unknown }).cuebellTestWorkers)); throw error; });
  await expect(page.getByText('Noise reduction is unavailable. Listening continues without it.', { exact: true })).toHaveCount(0);
  expect(mock.frames.every(size => size === 1024)).toBe(true);
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Start', exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { cuebellTestWorkers: { terminated: number } }).cuebellTestWorkers.terminated)).toBe(1);
});

test('real GTCRN worker processes fixed packets with bounded latency and fresh recurrent state', async ({ page }) => {
  test.setTimeout(60000);
  await page.goto('/');
  const result = await page.evaluate(async () => {
    const input = Array.from({ length: 80 }, (_, frame) => {
      const pcm = new Int16Array(512);
      for (let n = 0; n < pcm.length; n++) {
        const i = frame * 512 + n;
        pcm[n] = Math.round(2500 * Math.sin(2 * Math.PI * 440 * i / 16000) + 1200 * Math.sin(i * 1.7));
      }
      return pcm.buffer;
    });
    async function run(count: number) {
      const worker = new Worker('/audio/gtcrn-worker.mjs', { type: 'module' });
      const outputs: number[][] = [], timings: number[] = [], roundTrips: number[] = [];
      const started = performance.now();
      try {
        await new Promise<void>((resolve, reject) => {
          worker.onerror = () => reject(new Error('Worker failed'));
          worker.onmessage = ({ data }) => data.type === 'ready' ? resolve() : reject(new Error(data.reason));
        });
        const startupMs = performance.now() - started;
        for (let i = 0; i < count; i++) {
          const sent = performance.now();
          const result = await new Promise<{ frame: ArrayBuffer; processingMs: number }>((resolve, reject) => {
            worker.onmessage = ({ data }) => data.type === 'frame' && data.id === i ? resolve(data) : reject(new Error(data.reason));
            const copy = input[i].slice(0);
            worker.postMessage({ type: 'frame', id: i, frame: copy }, [copy]);
          });
          roundTrips.push(performance.now() - sent);
          timings.push(result.processingMs);
          outputs.push(Array.from(new Int16Array(result.frame)));
          // Match the microphone's 32 ms cadence instead of creating an artificial CPU backlog.
          await new Promise(resolve => setTimeout(resolve, Math.max(0, 32 - (performance.now() - sent))));
        }
        return { outputs, timings, roundTrips, startupMs };
      } finally { worker.terminate(); }
    }
    const first = await run(input.length), second = await run(3);
    const sorted = [...first.roundTrips].sort((a, b) => a - b);
    return {
      modelMs: first.timings.reduce((a, b) => a + b, 0) / first.timings.length,
      roundTripMedianMs: sorted[Math.floor(sorted.length * 0.5)], roundTripP95Ms: sorted[Math.floor(sorted.length * 0.95)],
      startupMs: first.startupMs, resetMatches: JSON.stringify(first.outputs.slice(0, 3)) === JSON.stringify(second.outputs),
      allPacketSizes: first.outputs.every(frame => frame.length === 512),
      padding: first.outputs[0].slice(0, 256).every(value => value === 0),
      inputEnergy: input.reduce((sum, frame) => sum + Array.from(new Int16Array(frame)).reduce((total, value) => total + value * value, 0), 0),
      outputEnergy: first.outputs.flat().reduce((sum, value) => sum + value * value, 0),
    };
  });
  console.log('GTCRN browser benchmark:', JSON.stringify(result));
  expect(result.allPacketSizes).toBe(true);
  expect(result.padding).toBe(true);
  expect(result.resetMatches).toBe(true);
  expect(result.outputEnergy).toBeGreaterThan(0);
  expect(result.outputEnergy).toBeLessThan(result.inputEnergy);
  expect(result.roundTripP95Ms).toBeLessThan(32);
});

for (const fault of ['missing-model', 'slow-worker'] as const) {
  test(`browser denoising fails open without accumulating audio: ${fault}`, async ({ page, context }) => {
    const mock = await relay(page);
    await page.addInitScript(() => localStorage.setItem('cuebell.noise-reduction.v1', 'gtcrn'));
    if (fault === 'missing-model') {
      await context.route('**/audio/vendor/gtcrn_simple.onnx', route => route.fulfill({ status: 404, body: 'Not found' }));
    } else {
      await page.route('**/audio/gtcrn-worker.mjs', route => route.fulfill({ contentType: 'text/javascript', body:
        "self.onmessage = ({data}) => setTimeout(() => self.postMessage({...data, processingMs: 50}, [data.frame]), 50); self.postMessage({type:'ready'});" }));
    }
    await typedTask(page);
    await expect(page.getByText('Noise reduction is unavailable. Listening continues without it.', { exact: true }).first()).toBeVisible();
    await expect.poll(() => mock.frames.length).toBeGreaterThan(8);
    expect(mock.sockets.length).toBe(1);
    expect(mock.frames.every(size => size === 1024)).toBe(true);
    await page.getByTestId('listening-control').click();
    await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start');
  });
}

test('stopping while the model initializes never starts a late microphone stream', async ({ page }) => {
  const mock = await relay(page);
  await page.addInitScript(() => {
    localStorage.setItem('cuebell.noise-reduction.v1', 'gtcrn');
    const Original = Worker;
    window.Worker = class extends Original {
      constructor(url: string | URL, options?: WorkerOptions) {
        super(url, options);
        Object.defineProperty(window, 'cuebellInitializingWorker', { value: this, configurable: true });
      }
    };
  });
  await page.route('**/audio/gtcrn-worker.mjs', route => route.fulfill({ contentType: 'text/javascript', body:
    "self.onmessage = () => self.postMessage({type:'ready'});" }));
  await page.goto('/token');
  await page.getByRole('checkbox', { name: 'Allow audio & text processing' }).click();
  await page.getByLabel('Listen for…').fill('Token 42');
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect.poll(() => page.evaluate(() => 'cuebellInitializingWorker' in window)).toBe(true);
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toHaveCount(0);
  await page.evaluate(async () => {
    const worker = (window as unknown as { cuebellInitializingWorker: Worker }).cuebellInitializingWorker;
    worker.dispatchEvent(new MessageEvent('message', { data: { type: 'ready' } }));
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  expect(mock.sockets.length).toBe(0);
  expect(await page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] }).cuebellTestStreams.every(stream =>
    stream.getTracks().every(track => track.readyState === 'ended')))).toBe(true);
});
});

test('typed request streams real PCM, renders captions and alerts, and stops on Home', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
  await expect.poll(() => mock.frames.length).toBeGreaterThan(3);
  expect(mock.frames.every(size => size === 1024)).toBe(true);
  expect(await page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] }).cuebellTestStreams.length)).toBe(1);
  await expect.poll(() => page.locator('canvas').evaluate((canvas: HTMLCanvasElement) => {
    const pixels = canvas.getContext('2d')!.getImageData(0, 0, canvas.width, canvas.height).data;
    let first = canvas.height, last = 0;
    for (let y = 0; y < canvas.height; y++) {
      for (let x = 0; x < canvas.width; x++) {
        if (pixels[(y * canvas.width + x) * 4 + 3] > 100) { first = Math.min(first, y); last = Math.max(last, y); }
      }
    }
    return last - first;
  })).toBeGreaterThan(8);
  const socket = mock.sockets.at(-1)!;
  const transcript = { type: 'transcript', mode: 'monitor', segment: { id: 'english-42', text: 'Token forty-two, counter three.', received_at: Date.now() / 1000 } };
  socket.send(JSON.stringify(transcript));
  socket.send(JSON.stringify(transcript));
  await expect(page.getByText(transcript.segment.text, { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Captions', exact: true }).click();
  await expect(page.getByText(transcript.segment.text, { exact: true })).toHaveCount(1);
  socket.send(JSON.stringify({ type: 'alert', sequence: 100, alert: { id: 'alert-42', token: '42', counter: '3', state: 'unacknowledged', alert_preferences: ['visual'] } }));
  await expect(page.getByText("It's your turn!", { exact: true }).first()).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Seen', exact: true }).click();
  await page.getByTestId('listening-control').click();
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start');
  const stoppedFrames = mock.frames.length;
  await page.waitForTimeout(250);
  expect(mock.frames.length).toBe(stoppedFrames);
  expect(await page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] })
    .cuebellTestStreams.every(stream => stream.getTracks().every(track => track.readyState === 'ended')))).toBe(true);
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await expect(page.getByText(transcript.segment.text, { exact: true })).toBeVisible();
});

test('spoken setup hands off to monitoring, preserves Malayalam captions, and obeys voice stop', async ({ page }) => {
  const mock = await relay(page);
  await page.goto('/');
  await page.getByTestId('listening-control').click();
  await page.getByRole('checkbox', { name: 'Allow audio & text processing' }).click();
  await page.getByTestId('listening-control').click();
  await expect.poll(() => mock.frames.length).toBeGreaterThan(1);
  mock.sockets[0].send(JSON.stringify({ type: 'transcript', mode: 'request', segment: {
    id: 'request-42', text: 'Listen for token 42', received_at: Date.now() / 1000,
  } }));
  await expect.poll(() => mock.sockets.length).toBe(2);
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Stop');
  await page.getByRole('button', { name: 'Captions', exact: true }).click();
  mock.sockets[1].send(JSON.stringify({ type: 'transcript', mode: 'monitor', segment: {
    id: 'malayalam-42', text: 'ടോക്കൺ നാല്പത്തിരണ്ട് കൗണ്ടർ മൂന്നിലേക്ക് വരിക.', received_at: Date.now() / 1000,
  } }));
  await expect(page.getByText('ടോക്കൺ നാല്പത്തിരണ്ട് കൗണ്ടർ മൂന്നിലേക്ക് വരിക.', { exact: true })).toBeVisible();
  mock.sockets[1].send(JSON.stringify({ type: 'monitor.pause', rule: { ...rule, status: 'PAUSED' } }));
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start');
});

test('network reconnection retains completed captions and resumes PCM', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
  await page.getByRole('button', { name: 'Captions', exact: true }).click();
  await expect.poll(() => mock.frames.length).toBeGreaterThan(1);
  mock.sockets[0].send(JSON.stringify({ type: 'transcript', mode: 'monitor', segment: {
    id: 'before-gap', text: 'Please wait for your token.', received_at: Date.now() / 1000,
  } }));
  mock.sockets[0].close({ code: 1011 });
  await expect(page.getByText('Reconnecting...', { exact: true })).toBeVisible();
  await expect.poll(() => mock.sockets.length).toBe(2);
  await expect(page.getByText('Please wait for your token.', { exact: true })).toBeVisible();
  const previous = mock.frames.length;
  await expect.poll(() => mock.frames.length).toBeGreaterThan(previous + 2);
});

test('task activation retries a busy stream without recreating the session or task', async ({ page }) => {
  const mock = await relay(page, { busyAttempts: 2 });
  await typedTask(page);
  await expect.poll(() => mock.frames.length).toBeGreaterThan(2);
  expect(mock.sockets).toHaveLength(3);
  for (const path of ['/v1/sessions', '/v1/intent', '/v1/confirm']) {
    expect(mock.calls.filter(call => call === path)).toHaveLength(1);
  }
  await expect(page.getByText(/Your listening session is unavailable/)).toHaveCount(0);
  await page.getByTestId('listening-control').click();
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start');
});

test('provider authentication failure keeps its explanation instead of claiming the session expired', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
  const message = 'Gnani authentication rejected. Ask the backend operator to check the provider credentials and access configuration before reconnecting.';
  mock.sockets[0].send(JSON.stringify({ type: 'status', state: 'DEGRADED', message }));
  mock.sockets[0].close({ code: 4403 });
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Retry');
  await expect(page.getByText(`${message} Try again from the app.`, { exact: true })).toBeVisible();
  await expect(page.getByText(/Your listening session is unavailable/)).toHaveCount(0);
  expect(await page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] })
    .cuebellTestStreams.every(stream => stream.getTracks().every(track => track.readyState === 'ended')))).toBe(true);
  await page.waitForTimeout(1100);
  expect(mock.sockets).toHaveLength(1);
});

test('an expired session stops capture and does not retry its rejected credential', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
  mock.sockets[0].close({ code: 4401 });
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Retry');
  await expect(page.getByText(/Your listening session is unavailable/)).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] })
    .cuebellTestStreams.every(stream => stream.getTracks().every(track => track.readyState === 'ended')))).toBe(true);
  await page.waitForTimeout(1100);
  expect(mock.sockets).toHaveLength(1);
});

test('denied microphone produces browser guidance and no audio stream', async ({ page }) => {
  const mock = await relay(page);
  await page.goto('/token');
  await page.evaluate(() => {
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Denied', 'NotAllowedError'); };
  });
  await page.getByRole('checkbox', { name: 'Allow audio & text processing' }).click();
  await page.getByLabel('Listen for…').fill('Listen for token 42');
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect(page.getByText(/Microphone permission was denied/)).toBeVisible();
  await expect(page.getByText(/Open the site controls beside the address bar/)).toBeVisible();
  expect(mock.frames).toEqual([]);
  expect(mock.sockets).toEqual([]);
});

test('hiding the page releases microphone tracks and requires an explicit restart', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
  await expect.poll(() => mock.frames.length).toBeGreaterThan(1);
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start');
  expect(await page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] })
    .cuebellTestStreams.every(stream => stream.getTracks().every(track => track.readyState === 'ended')))).toBe(true);
  const count = mock.sockets.length;
  await page.waitForTimeout(200);
  expect(mock.sockets.length).toBe(count);
});

test('cancelling a pending permission cannot start a microphone after the user stops', async ({ page }) => {
  const mock = await relay(page);
  await page.goto('/');
  await page.getByTestId('listening-control').click();
  await page.getByRole('checkbox', { name: 'Allow audio & text processing' }).click();
  await page.evaluate(() => {
    const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = constraints => new Promise(resolve => {
      Object.defineProperty(window, 'grantTestMicrophone', { configurable: true, value: async () => resolve(await capture(constraints)) });
    });
  });
  await page.getByTestId('listening-control').click();
  await expect(page.getByTestId('listening-control').getByText('Waiting for permission', { exact: true })).toBeVisible();
  await page.getByTestId('listening-control').click();
  await page.evaluate(() => (window as unknown as { grantTestMicrophone: () => Promise<void> }).grantTestMicrophone());
  expect(await page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] }).cuebellTestStreams.length)).toBe(1);
  await expect.poll(() => page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] })
    .cuebellTestStreams.every(stream => stream.getTracks().every(track => track.readyState === 'ended')))).toBe(true);
  expect(mock.sockets).toEqual([]);
  expect(mock.frames).toEqual([]);
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start');
  await expect(page.getByText('Listening cancelled.', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('blocked browser storage still permits task activation and microphone capture', async ({ page }) => {
  const mock = await relay(page);
  await page.addInitScript(() => {
    for (const name of ['sessionStorage', 'localStorage']) {
      Object.defineProperty(window, name, { configurable: true, get() { throw new DOMException('Blocked', 'SecurityError'); } });
    }
  });
  await typedTask(page);
  await expect.poll(() => mock.frames.length).toBeGreaterThan(1);
  await page.getByTestId('listening-control').click();
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start');
  await page.getByTestId('listening-control').click();
  await expect.poll(() => mock.sockets.length).toBe(2);
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Stop');
});

test('alert preferences independently control sound and vibration and suppress repeated delivery', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
  await expect.poll(() => mock.frames.length).toBeGreaterThan(1);
  await page.evaluate(() => {
    const output = { tones: 0, vibrations: [] as (number | number[])[] };
    Object.defineProperty(window, 'testAlerts', { value: output });
    const oscillator = AudioContext.prototype.createOscillator;
    AudioContext.prototype.createOscillator = function () { output.tones++; return oscillator.call(this); };
    Object.defineProperty(navigator, 'vibrate', { configurable: true, value: (pattern: number | number[]) => {
      output.vibrations.push(pattern); return true;
    } });
  });
  const alert = { type: 'alert', sequence: 201, alert: { id: 'preferences', token: '42', counter: '3',
    state: 'unacknowledged', alert_preferences: ['sound', 'vibration'] } };
  mock.sockets[0].send(JSON.stringify(alert));
  mock.sockets[0].send(JSON.stringify(alert));
  await expect.poll(() => page.evaluate(() => (window as unknown as { testAlerts: { tones: number } }).testAlerts.tones)).toBe(3);
  const vibration = await page.evaluate(() => (window as unknown as { testAlerts: { vibrations: unknown[] } }).testAlerts.vibrations);
  expect(vibration).toEqual([[400, 200, 400, 200, 700]]);
  mock.sockets[0].send(JSON.stringify({ ...alert, sequence: 202, alert: { ...alert.alert, id: 'silent', alert_preferences: ['visual'] } }));
  await expect(page.getByLabel('Additional alerts waiting: 1', { exact: true })).toHaveText('+1');
  expect(await page.evaluate(() => (window as unknown as { testAlerts: { tones: number } }).testAlerts.tones)).toBe(3);
});

test('mobile layout supports large text, dark theme and reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await page.goto('/');
  await page.addStyleTag({ content: 'html { font-size: 24px; }' });
  await expect(page.getByTestId('listening-control')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/home-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Keep CueBell visible', exact: true })).toBeVisible();
});

test('event details are optional and a deferred correction replaces the old directions', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
  const alert = { id: 'alert-42', token: null, counter: null, summary: 'Train 014922 arrived · Platform 03',
    location: 'Platform 03', evidence_text: 'Attention passengers. Train 014922 has arrived at Platform 03.',
    state: 'unacknowledged', alert_preferences: ['visual'] };
  mock.sockets[0].send(JSON.stringify({ type: 'alert', sequence: 100, alert }));
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText(alert.summary, { exact: true })).toBeVisible();
  await expect(dialog.getByText(alert.location, { exact: true })).toHaveCount(0);
  await expect(dialog.getByText(alert.evidence_text, { exact: true })).toHaveCount(0);
  const details = dialog.getByRole('button', { name: 'Details', exact: true });
  await expect(details).toHaveAttribute('aria-expanded', 'false');
  await details.focus();
  await page.keyboard.press('Enter');
  await expect(details).toHaveAttribute('aria-expanded', 'true');
  await expect(dialog.getByText(alert.evidence_text, { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Back to app', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  mock.sockets[0].send(JSON.stringify({ type: 'alert.corrected', sequence: 102, alert: { ...alert, state: 'corrected' } }));
  await expect(dialog.getByText('Alert changed', { exact: true })).toBeVisible();
  await expect(dialog.getByText('Check the official source.', { exact: true })).toBeVisible();
  await expect(dialog.getByText(alert.summary, { exact: true })).toHaveCount(0);
  await expect(details).toHaveAttribute('aria-expanded', 'false');
  await details.click();
  await expect(dialog.getByText('Previous alert', { exact: true })).toBeVisible();
  await expect(dialog.getByText(alert.summary, { exact: true })).toBeVisible();
});

test('uncertainty stays visible with captions collapsed', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
  mock.sockets[0].send(JSON.stringify({ type: 'observation', sequence: 100, observation: {
    id: 'unclear-42', type: 'UNCERTAIN', token_normalized: '42', counter: null,
    evidence_text: 'Token forty…', ambiguity_reason: 'Incomplete token',
  } }));
  await expect(page.getByRole('button', { name: 'Captions', exact: true })).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByText('Unclear announcement. Check the display.', { exact: true })).toBeVisible();
});

for (const [language, messages] of Object.entries(catalogs)) {
  test(`compact alerts and disclosures fit a small screen in ${language}`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 740 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const mock = await relay(page);
    await page.addInitScript(locale => localStorage.setItem('cuebell.language.v1', locale), language);
    await page.goto('/token');
    await expect(page.locator('html')).toHaveAttribute('dir', ['ur', 'sd'].includes(language) ? 'rtl' : 'ltr');
    await page.getByRole('checkbox', { name: messages['Allow audio & text processing'] }).click();
    await page.getByLabel(messages['What should I listen for?']).fill('Listen for A-001234');
    await page.getByRole('button', { name: messages['Start Listening'], exact: true }).click();
    await expect(page.getByTestId('listening-control')).toHaveAccessibleName(messages['Stop Listening']);
    await expect(page.getByRole('button', { name: messages['Live captions'], exact: true })).toHaveAttribute('aria-expanded', 'false');
    mock.sockets[0].send(JSON.stringify({ type: 'alert', sequence: 100, alert: {
      id: 'alert-42', token: 'A-001234', counter: '03', state: 'unacknowledged',
      evidence_text: 'A-001234, counter 03.', alert_preferences: ['visual'],
    } }));
    const dialog = page.getByRole('dialog');
    const seen = dialog.getByRole('button', { name: messages['I’ve seen this'], exact: true });
    await expect(seen).toBeInViewport();
    await expect(dialog.getByTestId('alert-token')).toHaveText('A-001234');
    await expect(dialog.getByTestId('alert-token')).toHaveCSS('direction', 'ltr');
    // Check descendant bounds, not just document overflow (the modal can scroll independently).
    expect(await dialog.evaluate(root => Array.from(root.querySelectorAll<HTMLElement>('[role="button"], [dir="auto"]')).every(node => {
      const box = node.getBoundingClientRect();
      return box.left >= 0 && box.right <= innerWidth + 1;
    }))).toBe(true);
    if (['en', 'ml', 'ur', 'mni-Mtei'].includes(language)) {
      await page.screenshot({ path: `test-results/alert-${language}.png`, fullPage: true });
    }
    const details = dialog.getByRole('button', { name: messages.Details, exact: true });
    await details.click();
    await expect(dialog.getByText('A-001234, counter 03.', { exact: true })).toBeVisible();
    await details.click();
    await seen.click();
    await page.getByTestId('listening-control').click();
    await expect(page.getByTestId('listening-control')).toHaveAccessibleName(messages['Start Listening']);
  });
}
