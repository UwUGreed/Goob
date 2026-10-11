import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';
// Read-only rendered review of the connected demo; mutations are tested in a unique PostgreSQL schema.
test('every portal route, property coverage, charge review, forms and responsive layouts',async({page})=>{
 const credentials=JSON.parse(readFileSync(process.env.GOOB_E2E_CREDENTIALS_FILE??path.resolve('..','.demo-credentials.json'),'utf8'));
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/config',async route=>{const response=await route.fetch();await route.fulfill({response,json:{...(await response.json()),browserKey:'',routes:false,voice:false}});});
 await page.goto('/memberships');await expect(page).toHaveURL(/sign-in\?returnTo=/);
 await page.getByLabel('Username or email').fill(credentials.identifier);await page.getByLabel('Password',{exact:true}).fill(credentials.password);await page.getByRole('button',{name:/^Sign in/}).click();
 await expect(page.getByRole('heading',{name:'Memberships',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Configure plan',exact:true}).click();await expect(page.getByRole('dialog')).toContainText('Included maintenance visits');await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByRole('button',{name:'Enroll customer',exact:true}).click();await page.getByRole('combobox',{name:'Customer',exact:true}).selectOption({label:'Alex Morgan'});await page.getByRole('combobox',{name:'Covered property',exact:true}).selectOption({label:'Home · 82 Maple Avenue'});await page.getByRole('combobox',{name:'Covered equipment',exact:true}).selectOption({label:'Home heat pump · HVAC'});await expect(page.getByLabel('Term starts')).not.toBeEmpty();await page.keyboard.press('Escape');
 await page.screenshot({path:'test-results/memberships-desktop.png',fullPage:true});
 const response=await page.request.get('/api/dispatch');expect(response.ok()).toBe(true);const state=(await response.json()).state;
 const customer=state.customers.find((c:any)=>c.name==='Alex Morgan');const repair=state.records.find((j:any)=>j.title==='Covered HVAC repair');const membership=state.memberships.find((m:any)=>m.customerId===customer.id);
 expect(repair.chargeProposal.totalCents).toBe(19800);expect(membership.remaining).toBe(2);
 await page.goto('/customers/'+customer.id);await expect(page.getByRole('heading',{name:'Alex Morgan',exact:true})).toBeVisible();await expect(page.locator('.coverage-card')).toContainText('2 maintenance visits remaining');
 await page.getByRole('button',{name:'Rental 210 Cedar Street',exact:true}).click();await expect(page.locator('.coverage-card')).toContainText('This property has no membership coverage');await expect(page.locator('.ops-equipment')).toContainText('Rental air conditioner');await page.reload();await expect(page.locator('.coverage-card')).toContainText('This property has no membership coverage');
 await page.getByRole('button',{name:'Create job',exact:true}).last().click();await expect(page.getByRole('combobox',{name:'Customer',exact:true})).toHaveValue(customer.id);await expect(page.getByRole('combobox',{name:'Property',exact:true})).toHaveValue('210 Cedar Street');await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Home 82 Maple Avenue',exact:true}).click();await page.getByRole('button',{name:'Edit property',exact:true}).click();await expect(page.getByLabel('Property name')).toHaveValue('Home');await page.keyboard.press('Escape');
 await page.screenshot({path:'test-results/customers-desktop.png',fullPage:true});
 await page.goto('/jobs/'+repair.id);await expect(page.getByRole('heading',{name:/Covered HVAC repair/})).toBeVisible();await expect(page.locator('#review-3')).toContainText('Proposed total $198.00');await expect(page.locator('#review-0')).toContainText('Repair leaves maintenance visits unchanged');
 await page.reload();await expect(page.locator('#review-3')).toContainText('$198.00');await page.screenshot({path:'test-results/job-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'Open in Dispatch',exact:true}).click();await expect(page).toHaveURL(new RegExp('/dispatch\\?job='+repair.id));await expect(page.locator('.dispatch-inspector')).toContainText('Covered HVAC repair');
 await page.goto('/inventory');await expect(page.getByRole('heading',{name:'Movement ledger',exact:true})).toBeVisible();await page.getByRole('button',{name:'H-01',exact:true}).click();await page.reload();await expect(page.getByRole('button',{name:'H-01',exact:true})).toHaveAttribute('aria-pressed','true');await page.getByRole('button',{name:'Record movement',exact:true}).first().click();await page.getByRole('combobox',{name:'Movement type',exact:true}).selectOption('transfer');await expect(page.getByRole('combobox',{name:'Destination',exact:true})).toBeVisible();await page.keyboard.press('Escape');await page.screenshot({path:'test-results/inventory-desktop.png',fullPage:true});
 await page.goto('/memberships/'+membership.id);await expect(page.getByRole('heading',{name:'Benefits and linked visits'})).toBeVisible();await page.getByRole('button',{name:'Manual renewal',exact:true}).click();await expect(page.getByRole('dialog')).toContainText('Unused visits do not roll over');await page.keyboard.press('Escape');
 await page.goto('/jobs');await expect(page.getByRole('group',{name:'Job status'})).toBeVisible();await expect(page.locator('.ops-workspace')).not.toContainText('Verification sink visit');await page.getByLabel('Include verification records').check();
 await page.goto('/overview');await expect(page.getByRole('heading',{name:'A clear view of the day.'})).toBeVisible();await page.screenshot({path:'test-results/overview-desktop.png',fullPage:true});
 await page.goto('/today');await expect(page).toHaveURL(/overview$/);await page.goto('/unknown-route');await expect(page.getByRole('heading',{name:'Page not found'})).toBeVisible();
 await page.setViewportSize({width:390,height:844});
 for(const route of ['/overview','/customers/'+customer.id,'/jobs','/jobs/'+repair.id,'/inventory','/memberships','/memberships/'+membership.id]){
  await page.goto(route);await expect(page.locator('.ops-workspace h1')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/mobile-'+route.split('/')[1]+(route.split('/')[2]?'-detail':'')+'.png',fullPage:true});
 }
 expect(errors).toEqual([]);
});
