import { defineConfig } from '@playwright/test';
const baseURL = process.env.GOOB_E2E_BASE_URL;
if (!baseURL) throw new Error('Set GOOB_E2E_BASE_URL to an isolated test workspace. Browser tests never launch a database or use the shared cloud app implicitly.');
export default defineConfig({
  // The other browser specs target the retired unauthenticated fixture UI.
  // Connected-demo membership review has its own config and credentials file.
  testMatch:process.env.GOOB_CLOUD_E2E?'portal-cloud.spec.ts':'expansion.spec.ts',
  testDir:'./e2e', workers:1, timeout:60000,
  use:{baseURL,viewport:{width:1440,height:900},launchOptions:{...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{}),args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}},
  reporter:'list'
});
