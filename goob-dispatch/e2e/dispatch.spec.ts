import {test,expect} from '@playwright/test';
test('complete Oak Lane while switching maps, return to depot, and retain preferences',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Dispatch.'})).toBeVisible();await expect(page.locator('.map-canvas canvas')).toBeVisible();await expect(page.locator('.map-error')).toHaveCount(0);
  await expect(page.getByText('1 reserved on Truck P-02')).toBeVisible();
  await page.getByRole('button',{name:'Why this technician?'}).click();await expect(page.getByText(/HVAC skills do not match/)).toBeVisible();await expect(page.getByText(/Already on a job/)).toBeVisible();
  await page.screenshot({path:'test-results/goob-3d.png',fullPage:true});
  await page.getByRole('button',{name:'2D',exact:true}).click();await page.screenshot({path:'test-results/goob-2d.png',fullPage:true});
  await page.getByRole('button',{name:'Assign visit',exact:true}).click();await expect(page.getByRole('button',{name:'Assign visit',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Start travel simulation'}).click();await page.getByRole('button',{name:'10×',exact:true}).click();
  await expect.poll(async()=>Number((await page.locator('.journey-progress strong').innerText()).replace('%',''))).toBeGreaterThan(0);
  await page.getByRole('button',{name:'Pause',exact:true}).click();const paused=await page.locator('.journey-progress strong').innerText();await page.waitForTimeout(300);expect(await page.locator('.journey-progress strong').innerText()).toBe(paused);
  await page.getByRole('button',{name:'3D',exact:true}).click();expect(await page.locator('.journey-progress strong').innerText()).toBe(paused);
  await page.getByRole('button',{name:'Resume',exact:true}).click();await page.getByRole('button',{name:'Follow technician',exact:true}).click();
  await expect(page.getByRole('button',{name:'Start work',exact:true})).toBeEnabled({timeout:20000});await expect(page.getByRole('button',{name:'Pause',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Start work',exact:true}).click();await page.getByRole('button',{name:'Complete job',exact:true}).click();await expect(page.getByText('Another customer taken care of.')).toBeVisible();
  await page.getByRole('button',{name:'Return to depot',exact:true}).click();await page.getByRole('button',{name:'2D',exact:true}).click();await expect(page.locator('.sim-identity small')).toContainText('Available',{timeout:20000});
  await page.getByRole('button',{name:'Customize view'}).click();await page.getByLabel('Technician names').uncheck();await page.getByRole('button',{name:'Compact',exact:true}).click();await page.getByRole('button',{name:'Done',exact:true}).click();await page.reload();
  await expect(page.locator('.app-shell')).toHaveClass(/density-compact/);await page.getByRole('button',{name:'Customize view'}).click();await expect(page.getByLabel('Technician names')).not.toBeChecked();await page.getByRole('button',{name:'Reset default view'}).click();await page.getByRole('button',{name:'Done',exact:true}).click();
  expect(errors).toEqual([]);
});
test('mobile navigation and demo recommendation are usable',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
  await expect(page.locator('.map-canvas canvas')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Close details'}).click();await page.getByRole('button',{name:'Try demo command'}).click();await expect(page.getByRole('heading',{name:'Urgent plumbing visit'})).toBeVisible();
  await page.getByRole('button',{name:'Customers',exact:true}).click();await page.getByPlaceholder('Find a customer or address').fill('Morgan');await expect(page.getByRole('button',{name:/Alex Morgan/})).toBeVisible();await page.getByRole('button',{name:/Alex Morgan/}).click();
  await page.getByRole('button',{name:'Inventory',exact:true}).click();await expect(page.getByText('Truck P-02 · 3 in stock')).toBeVisible();await page.getByRole('button',{name:'Close dialog'}).click();await page.screenshot({path:'test-results/goob-mobile.png',fullPage:true});
});
