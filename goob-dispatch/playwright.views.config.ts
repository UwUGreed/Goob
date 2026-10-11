import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./e2e',testMatch:'views.spec.ts',workers:1,timeout:60000,use:{baseURL:'http://127.0.0.1:8093',viewport:{width:1440,height:1000},launchOptions:{executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'}}});
