// A stock consumer Playwright config: the export writes into testDir, and the
// app is started by webServer, which waits on a URL rather than sleeping.
// QA_FIXTURE_NO_SERVER=1 leaves the app down - the "unavailable" arm.
import { defineConfig } from '@playwright/test';

const port = Number(process.env.FIXTURE_PORT || 4391);
const noServer = process.env.QA_FIXTURE_NO_SERVER === '1';

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './test-results',
  retries: 0,
  workers: 1,
  use: { baseURL: `http://127.0.0.1:${port}` },
  webServer: noServer
    ? undefined
    : {
        command: 'node server.mjs',
        url: `http://127.0.0.1:${port}/healthz`,
        reuseExistingServer: false,
        timeout: 30_000,
        env: {
          FIXTURE_PORT: String(port),
          FIXTURE_STATE: process.env.FIXTURE_STATE || 'buggy',
        },
      },
});
