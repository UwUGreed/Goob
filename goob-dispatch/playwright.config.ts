import { defineConfig } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('..', import.meta.url));
export default defineConfig({
  testDir:'./e2e', timeout:60000,
  use:{baseURL:'http://127.0.0.1:8082',viewport:{width:1440,height:900},launchOptions:{...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{}),args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}},
  webServer:{command:`npm --prefix goob-dispatch run build && ${process.platform==='win32'?'python':'python3'} -m operations.server`,cwd:root,url:'http://127.0.0.1:8082',reuseExistingServer:false,env:{GOOB_DEMO_PORT:'8082',GOOB_DEMO_DB:join(tmpdir(),`goob-e2e-${process.pid}.sqlite3`)},timeout:120000},
  reporter:'list'
});
