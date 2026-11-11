import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  workers: 2,
  timeout: 30000,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    ...devices['Desktop Chrome'],
    launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
    permissions: ['microphone'],
    trace: 'retain-on-failure',
  },
  webServer: { command: 'npm run preview:web', url: 'http://127.0.0.1:4173', reuseExistingServer: !process.env.CI },
});
