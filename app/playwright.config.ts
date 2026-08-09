import { defineConfig, devices } from '@playwright/test'

// One server. api/main.py mounts app/dist at the site root, so the tests exercise the
// production bundle against the real backend, which is exactly what ships. Offline
// mode is covered by aborting /api/health inside the shell suite rather than by
// standing up a second server.
export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:8000',
    trace: 'off',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'python -m uvicorn api.main:app --host 127.0.0.1 --port 8000',
    cwd: '..',
    url: 'http://127.0.0.1:8000/api/health',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
