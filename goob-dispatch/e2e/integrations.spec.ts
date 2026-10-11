import { test, expect } from './fixtures';
import { mockGoogle, encodeTestRoute } from './google.mock';
test('typed proposals require confirmation and missing voice credentials remain honest',async({page})=>{
  let tokenCalls=0,assignments=0;page.on('request',request=>{if(request.url().endsWith('/api/scribe-token'))tokenCalls++;if(request.url().endsWith('/api/dispatch')&&request.postDataJSON()?.type==='assign')assignments++;});
  await page.goto('/');await page.getByRole('button',{name:'Voice or type commands'}).click();
  await expect(page.getByText('Typed commands · Microphone not configured')).toBeVisible();
  await page.getByLabel('Editable command').fill('Find an available plumber for Oak Lane and check parts readiness.');await page.getByRole('button',{name:'Run command'}).click();
  await expect(page.locator('.command-feedback')).toContainText('Maya Chen is proposed');expect(assignments).toBe(0);await expect(page.locator('.sim-identity small')).toContainText('Available');
  await page.getByRole('button',{name:'Start microphone'}).click();await expect(page.locator('.command-feedback')).toContainText('Voice is not configured');expect(tokenCalls).toBe(0);
  await page.getByLabel('Editable command').fill('Follow Maya or Chris');await page.getByRole('button',{name:'Run command'}).click();await expect(page.getByText('Which technician do you mean?')).toBeVisible();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();await expect(page.getByLabel('Editable command')).toHaveValue('');
  await page.getByRole('button',{name:'Close dialog'}).click();await page.getByRole('button',{name:'Assign Maya'}).click();expect(assignments).toBe(1);await expect(page.locator('.sim-identity small')).toContainText('Assigned');
});
test('Google adapters share driving coordinates and progress without refetching on view changes',async({page})=>{
  await mockGoogle(page);let routes=0;
  await page.route('**/api/config',route=>route.fulfill({json:{browserKey:'test-browser-key',mapId:'DEMO_MAP_ID',routes:true,voice:false,authenticated:true,localDemo:true}}));
  await page.route('**/api/routes',route=>{routes++;const {origin,destination}=route.request().postDataJSON();route.fulfill({json:{encodedPolyline:encodeTestRoute([origin,{lat:destination.lat,lng:origin.lng},destination]),distanceMeters:600,durationSeconds:180}});});
  await page.goto('/');await page.getByRole('button',{name:'3D',exact:true}).click();await expect(page.locator('gmp-map-3d')).toBeVisible({timeout:15000});await expect(page.getByText('Columbia, SC',{exact:false})).toBeVisible();
  await expect(page.getByRole('button',{name:'Assign Maya'})).toBeEnabled();await page.getByRole('button',{name:'Assign Maya'}).click();await page.getByRole('tab',{name:'Map',exact:true}).click();await page.getByRole('button',{name:'Start travel simulation'}).click();
  await expect.poll(async()=>Number((await page.locator('.journey-progress strong').innerText()).replace('%',''))).toBeGreaterThan(0);
  await page.getByRole('button',{name:'Pause',exact:true}).click();await expect(page.getByRole('button',{name:'Resume',exact:true})).toBeEnabled();const progress=await page.locator('.journey-progress strong').innerText();
  const positions=await page.evaluate(()=>{const data=(window as any).__googleTest;return[data.markers2.find((m:any)=>m.title.startsWith('Select Maya Chen')).position,data.markers3.find((m:any)=>m.title.startsWith('Select Maya Chen')).position];});expect(positions[0].lat).toBeCloseTo(positions[1].lat,8);expect(positions[0].lng).toBeCloseTo(positions[1].lng,8);
  await page.getByRole('button',{name:'2D',exact:true}).click();await expect(page.locator('[aria-label="Google 2D map of Columbia"]')).toBeVisible();expect(await page.locator('.journey-progress strong').innerText()).toBe(progress);
  await page.getByRole('button',{name:'3D',exact:true}).click();expect(await page.locator('.journey-progress strong').innerText()).toBe(progress);expect(routes).toBe(1);
  await page.getByRole('button',{name:'Fit route',exact:true}).click();await page.getByRole('button',{name:'Zoom in',exact:true}).click();await page.getByRole('button',{name:'Reset map view',exact:true}).click();
  await page.getByRole('button',{name:'Follow technician',exact:true}).click();await expect(page.getByRole('button',{name:'Stop following technician'})).toBeVisible();await page.locator('gmp-map-3d').dispatchEvent('wheel');await expect(page.getByRole('button',{name:'Follow technician',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'10×',exact:true}).click();await page.getByRole('button',{name:'Resume',exact:true}).click();await expect(page.getByRole('button',{name:'Start work',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Start work',exact:true}).click();await page.getByRole('button',{name:'Complete job',exact:true}).click();await page.getByRole('button',{name:'Return to depot',exact:true}).click();await expect(page.locator('.sim-identity small')).toContainText('Available');expect(routes).toBe(2);
});
test('3D initialization errors fall back to Google 2D and routing errors offer the fictional demo',async({page})=>{
  await mockGoogle(page,true);await page.route('**/api/config',route=>route.fulfill({json:{browserKey:'test-browser-key',mapId:'DEMO_MAP_ID',routes:true,voice:false,authenticated:true,localDemo:true}}));
  await page.route('**/api/routes',route=>route.fulfill({status:502,json:{error:'Google driving route failed. The fictional demo is available.'}}));
  await page.goto('/');await page.getByRole('button',{name:'3D',exact:true}).click();await expect(page.getByRole('button',{name:'2D',exact:true})).toHaveAttribute('aria-pressed','true');await expect(page.locator('.desk-service-message')).toContainText('No road route is being simulated');await expect(page.getByRole('button',{name:'Assign Maya'})).toBeDisabled();
  await page.getByRole('button',{name:'Use demo map'}).click();await expect(page.locator('.map-canvas canvas')).toBeVisible();await expect(page.locator('.desk-demo')).toContainText('Demo');await expect(page.getByRole('button',{name:'Assign Maya'})).toBeEnabled();
});
test('denied microphone access disconnects Scribe and preserves the typed alternative',async({page})=>{
  await page.route('**/api/config',route=>route.fulfill({json:{browserKey:'',mapId:'',routes:false,voice:true,authenticated:true,localDemo:true}}));
  await page.route('**/api/scribe-token',route=>route.fulfill({json:{token:'test-single-use-token'}}));
  await page.addInitScript(()=>{Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>{throw new DOMException('Permission denied','NotAllowedError');}});});
  await page.routeWebSocket('wss://api.elevenlabs.io/**',()=>{});
  await page.goto('/');await page.getByRole('button',{name:'Voice or type commands'}).click();await page.getByRole('button',{name:'Start microphone'}).click();
  await expect(page.locator('.command-feedback')).toContainText('permission was denied');await expect(page.locator('.voice-phase')).toContainText('Error');await expect(page.getByRole('button',{name:'Stop',exact:true})).toBeDisabled();
  await page.getByLabel('Editable command').fill('Show available plumbers.');await page.getByRole('button',{name:'Run command'}).click();await expect(page.locator('.command-feedback')).toContainText('Showing available plumbing technicians');
});
