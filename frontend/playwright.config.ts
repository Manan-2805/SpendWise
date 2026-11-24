import { defineConfig, devices } from '@playwright/test'

const stackUrl = process.env.SPENDWISE_E2E_BASE_URL

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: stackUrl ?? 'http://localhost:3000',
    colorScheme: 'light',
    trace: 'off',
    video: 'off',
    ...devices['Desktop Chrome'],
  },
  webServer: stackUrl ? undefined : {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: false,
    timeout: 30_000,
  },
})
