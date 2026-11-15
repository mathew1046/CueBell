import { defineConfig, devices } from '@playwright/test';

const port = process.env.PORT || '4173';
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  // Real-time audio deadlines and CPU latency measurements need an uncontended browser.
  workers: 1,
  timeout: 30000,
  projects: [
    { name: 'ui', grepInvert: /real-time browser noise reduction/ },
    // Trace snapshots stall worker delivery past the production 32 ms deadline.
    { name: 'audio', grep: /real-time browser noise reduction/, use: { trace: 'off' } },
  ],
  use: {
    baseURL,
    ...devices['Desktop Chrome'],
    launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
    permissions: ['microphone'],
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run build:web -- --max-workers 2 && npm run preview:web',
    url: baseURL,
    env: { PORT: port },
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
