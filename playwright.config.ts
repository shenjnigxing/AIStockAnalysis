import { defineConfig } from '@playwright/test';

const port = Number(process.env.ASTOCK_PORT || '8091');
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${port}`;
const serverCommand = process.env.PLAYWRIGHT_SERVER_CMD || 'python run_api.py';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 45_000,
  use: {
    baseURL,
    headless: true,
  },
  webServer: {
    command: serverCommand,
    port,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      ASTOCK_PORT: String(port),
      DISABLE_STARTUP_JOBS: process.env.DISABLE_STARTUP_JOBS || '1',
    },
  },
});
