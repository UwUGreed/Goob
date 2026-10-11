import { defineConfig } from '@playwright/test';
const baseURL = process.env.GOOB_E2E_BASE_URL;
if (!baseURL) throw new Error('Set GOOB_E2E_BASE_URL to an isolated test workspace. Browser tests never launch a database or use the shared cloud app implicitly.');
export default defineConfig({
  testDir:'./e2e', workers:1, timeout:60000,
  use:{baseURL,viewport:{width:1440,height:900},launchOptions:{...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{}),args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}},
  reporter:'list'
});
