import { test, expect } from './fixtures';
import { mockGoogle, encodeTestRoute } from './google.mock';

test('availability replies speak actual status and never assign a visit',async({page})=>{
  let assignments=0;page.on('request',r=>{if(r.url().endsWith('/api/dispatch')&&r.postDataJSON()?.type==='assign')assignments++;});
  await page.addInitScript(()=>{
    const replies:string[]=[];(window as any).__spoken=replies;
    class Utterance{constructor(public text:string){}onend:any=null;onerror:any=null;}
    Object.defineProperty(window,'SpeechSynthesisUtterance',{value:Utterance});
    Object.defineProperty(window,'speechSynthesis',{value:{speak:(u:any)=>{replies.push(u.text);setTimeout(()=>u.onend?.(),10);},cancel:()=>{}}});
  });
  await page.goto('/');await page.getByRole('button',{name:'Voice or type commands'}).click();
  await page.getByLabel('Editable command').fill('Who is avaliable for electrical?');await page.getByRole('button',{name:'Run command'}).click();
  await expect(page.locator('.command-feedback')).toHaveText('No electrician is available right now. Jordan Lee is on a job.');
  await expect.poll(()=>page.evaluate(()=>(window as any).__spoken)).toEqual(['No electrician is available right now. Jordan Lee is on a job.']);
  await page.getByLabel('Editable command').fill('Who is available for plumbing?');await page.getByRole('button',{name:'Run command'}).click();
  await expect(page.locator('.command-feedback')).toHaveText('Maya Chen is available for plumbing.');expect(assignments).toBe(0);
  await expect(page.getByRole('button',{name:'Replay reply'})).toBeVisible();await page.getByRole('button',{name:'Replay reply'}).click();
  await expect.poll(()=>page.evaluate(()=>(window as any).__spoken.length)).toBe(3);
});

test('compact Google pins select visits, quiet 2D styling preserves roads, and mobile details fit',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await mockGoogle(page);
  await page.route('**/api/config',r=>r.fulfill({json:{browserKey:'test-browser-key',mapId:'',routes:true,voice:false,authenticated:true,localDemo:true}}));
  await page.route('**/api/routes',r=>{const {origin,destination}=r.request().postDataJSON();r.fulfill({json:{encodedPolyline:encodeTestRoute([origin,{lat:destination.lat,lng:origin.lng},destination]),distanceMeters:600,durationSeconds:180}});});
  await page.goto('/');await page.getByRole('button',{name:'3D',exact:true}).click();await expect(page.locator('gmp-map-3d')).toBeVisible({timeout:15000});await page.getByRole('button',{name:'2D',exact:true}).click();
  await expect(page.locator('.desk-map-heading')).toContainText('Columbia, SC');await expect(page.locator('.map-legend')).toHaveCount(0);
  const options=await page.evaluate(()=>(window as any).__googleTest.options2);expect(options.renderingType).toBe('RASTER');expect(options.styles).toContainEqual({featureType:'poi.business',elementType:'labels',stylers:[{visibility:'off'}]});expect(options.styles.some((s:any)=>s.featureType==='road'&&s.stylers.some((v:any)=>v.visibility==='off'))).toBe(false);
  const chris=page.locator('.google-pin[data-map-marker="chris"]');await chris.hover();await expect(page.locator('.google-pin-details').filter({hasText:'Chris Davis'})).toBeVisible();await chris.click();await expect(page.getByRole('heading',{name:'Chris Davis',exact:true})).toBeVisible();
  await page.locator('.google-pin[data-map-marker="oak"]').click();await expect(page.getByRole('heading',{name:'Kitchen sink leak'})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>(window as any).__googleTest.lines2.filter((l:any)=>l.options.map).some((l:any)=>l.options.strokeWeight===10))).toBe(true);
  await page.getByRole('button',{name:'Assign Maya',exact:true}).click();await expect(page.locator('.desk-notice')).toBeVisible();await expect(page.locator('.sim-identity small')).toContainText('Assigned');
  await page.getByRole('tab',{name:'Map',exact:true}).click();await page.getByRole('button',{name:'Start',exact:true}).click();await expect.poll(async()=>Number((await page.locator('.journey-progress strong').innerText()).replace('%',''))).toBeGreaterThan(0).catch(error=>{throw new Error(`${error.message}\nBrowser errors: ${errors.join('; ')}`);});
  await page.getByRole('button',{name:'Pause',exact:true}).click();await expect(page.getByRole('button',{name:'Resume',exact:true})).toBeEnabled();const progress=await page.locator('.journey-progress strong').innerText();
  await page.getByRole('button',{name:'3D',exact:true}).click();await page.getByRole('button',{name:'2D',exact:true}).click();expect(await page.locator('.journey-progress strong').innerText()).toBe(progress);expect(await page.evaluate(()=>(window as any).__googleTest.mapCount)).toBe(1);
  await page.setViewportSize({width:390,height:844});await page.locator('.dispatch-inspector').scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);expect(errors).toEqual([]);
});

 test('Ask Goob typed requests review recommendations without assigning, and handle unknown requests',async({page})=>{
  let assignments=0;page.on('request',r=>{if(r.url().endsWith('/api/dispatch')&&r.postDataJSON()?.type==='assign')assignments++;});
  await page.goto('/');const input=page.getByRole('textbox',{name:'Ask Goob'});
  await input.fill('Find an available plumber for Oak Lane and check parts readiness.');await page.getByRole('button',{name:'Ask',exact:true}).click();
  await expect(page.locator('.ask-result')).toContainText('Proposal interpreted');await expect(page.locator('.ask-result')).toContainText('Maya Chen');await expect(page.locator('.ask-result')).toContainText('required part is reserved on Truck P-02');
  await expect(page.locator('.sim-identity small')).toContainText('Available');await expect(page.getByRole('button',{name:'Assign Maya',exact:true})).toBeEnabled();expect(assignments).toBe(0);
  await input.fill('Who is available for electrical?');await input.press('Enter');await expect(page.locator('.ask-result')).toContainText('No electrician is available right now. Jordan Lee is on a job.');
  await input.fill('Do a backflip');await input.press('Enter');await expect(page.locator('.ask-error')).toBeVisible();expect(assignments).toBe(0);
  await input.fill('Open the Oak Lane job.');await input.press('Enter');await expect(page.getByRole('heading',{name:'Kitchen sink leak'})).toBeVisible();
});
