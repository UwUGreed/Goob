import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./e2e',testMatch:'invoices.spec.ts',workers:1,timeout:90000,
 use:{baseURL:process.env.GOOB_INVOICE_TEST_URL??'http://127.0.0.1:8092',headless:true,
 launchOptions:process.platform==='win32'?{executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'}:{}},
 reporter:'list'});
