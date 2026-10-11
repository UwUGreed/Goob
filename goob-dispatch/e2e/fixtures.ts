import { test as base, expect } from '@playwright/test';
// Deterministic browser checks never call real providers, even with local keys.
// Individual integration tests override this configuration with test adapters.
export const test=base.extend({page:async({page},use)=>{
  await page.route('**/api/config',route=>route.fulfill({json:{browserKey:'',mapId:'',routes:false,voice:false,authenticated:true,localDemo:true}}));
  await use(page);
}});
export { expect };
