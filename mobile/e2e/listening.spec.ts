import { expect, test, type Page, type WebSocketRoute } from '@playwright/test';

const service = 'https://cuebell.mathewjoseph.xyz';
const intent = { intent: 'monitor_announcement', context: 'hospital_pharmacy', token: '42',
  alert_preferences: ['visual', 'vibration', 'sound'], clarification: null };
const rule = { id: 'rule-42', token: '42', status: 'ACTIVE', alert_preferences: intent.alert_preferences };

/** Mock provider output at the relay boundary; exercise real browser capture and rendering. */
async function relay(page: Page) {
  const sockets: WebSocketRoute[] = [];
  const frames: number[] = [];
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
    const data = path === '/v1/sessions' ? { token: 'browser-test-session', expires_at: Date.now() / 1000 + 3600 } :
      path === '/v1/intent' ? { status: 'confirm', proposal_id: 'proposal-42', intent } :
      path === '/v1/state' ? { rule: active ? rule : null, history: [], alerts: [] } :
      path === '/v1/control' && route.request().postDataJSON()?.action === 'acknowledge' ?
        { type: 'alert.acknowledged', sequence: 101, alert: { id: 'alert-42', token: '42', counter: '3', state: 'acknowledged', alert_preferences: ['visual'] } } :
      { type: 'monitor.created', rule };
    if (path === '/v1/confirm') active = true;
    await route.fulfill({ json: data, headers: { 'Access-Control-Allow-Origin': '*' } });
  });
  await page.routeWebSocket(`${service.replace('https:', 'wss:')}/v1/stream*`, socket => {
    sockets.push(socket);
    let sentListening = false;
    socket.onMessage(message => {
      if (typeof message === 'string') {
        const auth = JSON.parse(message);
        expect(auth).toEqual({ type: 'authenticate', token: 'browser-test-session', consent: 'audio-gnani;text-openai' });
        expect(new URL(socket.url()).searchParams.has('token')).toBe(false);
        socket.send(JSON.stringify({ type: 'status', state: 'STARTING' }));
        socket.send(JSON.stringify({ type: 'status', state: 'READY' }));
      } else {
        frames.push(message.byteLength);
        if (!sentListening) { socket.send(JSON.stringify({ type: 'status', state: 'LISTENING' })); sentListening = true; }
      }
    });
  });
  return { sockets, frames };
}

async function typedTask(page: Page) {
  await page.goto('/token');
  await page.getByRole('checkbox', { name: 'Allow audio & text processing' }).click();
  await page.getByLabel('What should I listen for?').fill('Tell me when token 42 is called with vibration and sound.');
  await page.getByRole('button', { name: 'Start Listening', exact: true }).click();
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Stop Listening');
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
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start Listening');
  expect(await page.evaluate(() => (window as unknown as { captureRequests: unknown[] }).captureRequests)).toEqual([]);
  await expect(page.getByText('Listening in your browser')).toBeVisible();
  expect((await (await page.request.get('/manifest.webmanifest')).json()).display).toBe('standalone');
  await page.getByRole('button', { name: 'History', exact: true }).focus();
  await expect(page.getByRole('button', { name: 'History', exact: true })).toBeFocused();
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
  await expect(page.getByText(transcript.segment.text, { exact: true })).toHaveCount(1);
  socket.send(JSON.stringify({ type: 'alert', sequence: 100, alert: { id: 'alert-42', token: '42', counter: '3', state: 'unacknowledged', alert_preferences: ['visual'] } }));
  await expect(page.getByText("It's your turn!", { exact: true }).first()).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'I’ve seen this', exact: true }).click();
  await page.getByTestId('listening-control').click();
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start Listening');
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
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Stop Listening');
  mock.sockets[1].send(JSON.stringify({ type: 'transcript', mode: 'monitor', segment: {
    id: 'malayalam-42', text: 'ടോക്കൺ നാല്പത്തിരണ്ട് കൗണ്ടർ മൂന്നിലേക്ക് വരിക.', received_at: Date.now() / 1000,
  } }));
  await expect(page.getByText('ടോക്കൺ നാല്പത്തിരണ്ട് കൗണ്ടർ മൂന്നിലേക്ക് വരിക.', { exact: true })).toBeVisible();
  mock.sockets[1].send(JSON.stringify({ type: 'monitor.pause', rule: { ...rule, status: 'PAUSED' } }));
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start Listening');
});

test('network reconnection retains completed captions and resumes PCM', async ({ page }) => {
  const mock = await relay(page);
  await typedTask(page);
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

test('denied microphone produces browser guidance and no audio stream', async ({ page }) => {
  const mock = await relay(page);
  await page.goto('/token');
  await page.evaluate(() => {
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Denied', 'NotAllowedError'); };
  });
  await page.getByRole('checkbox', { name: 'Allow audio & text processing' }).click();
  await page.getByLabel('What should I listen for?').fill('Listen for token 42');
  await page.getByRole('button', { name: 'Start Listening', exact: true }).click();
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
  await expect(page.getByTestId('listening-control')).toHaveAccessibleName('Start Listening');
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
  await expect(page.getByText('Waiting for permission', { exact: true })).toBeVisible();
  await page.getByTestId('listening-control').click();
  await page.evaluate(() => (window as unknown as { grantTestMicrophone: () => Promise<void> }).grantTestMicrophone());
  expect(await page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] }).cuebellTestStreams.length)).toBe(1);
  await expect.poll(() => page.evaluate(() => (window as unknown as { cuebellTestStreams: MediaStream[] })
    .cuebellTestStreams.every(stream => stream.getTracks().every(track => track.readyState === 'ended')))).toBe(true);
  expect(mock.sockets).toEqual([]);
  expect(mock.frames).toEqual([]);
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
  await expect(page.getByText('Additional alerts waiting: 1', { exact: true })).toBeVisible();
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
  await expect(page.getByText('Keep CueBell visible', { exact: true })).toBeVisible();
});
