import { defineConfig } from '@playwright/test';
if(!process.env.GOOB_E2E_BASE_URL)throw new Error('Set GOOB_E2E_BASE_URL to the portal under review.');
export default defineConfig({testDir:'./e2e',testMatch:'service-memberships.spec.ts',workers:1,timeout:90000,use:{actionTimeout:12000,baseURL:process.env.GOOB_E2E_BASE_URL,viewport:{width:1440,height:900},launchOptions:{...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{}),args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}},reporter:'list'});
