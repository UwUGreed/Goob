import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';
test('cloud portal: login, routes, records, dispatch simulation, stock and sign-out',async({page})=>{
 test.setTimeout(150000);
 const credentials=JSON.parse(readFileSync(process.env.GOOB_E2E_CREDENTIALS_FILE??path.resolve('..','.demo-credentials.json'),'utf8'));
 // Keep provider billing and microphone hardware out of this persistence check.
 await page.route('**/api/config',async route=>{const response=await route.fetch();await route.fulfill({response,json:{...(await response.json()),browserKey:'',routes:false,voice:false}});});
 const failures:string[]=[];page.on('pageerror',error=>failures.push(error.message));
 await page.goto('/');await expect(page.getByRole('heading',{name:/A clearer day/})).toBeVisible();
 await page.getByRole('button',{name:/Launch demo/}).first().click();
 await page.getByLabel('Username or email').fill(credentials.identifier);await page.getByLabel('Password',{exact:true}).fill('invalid-credential');await page.getByRole('button',{name:/^Sign in/}).click();await expect(page.getByRole('alert')).toContainText('incorrect');
 await page.getByLabel('Password',{exact:true}).fill(credentials.password);await page.getByRole('button',{name:/^Sign in/}).click();await expect(page).toHaveURL(/\/overview$/);await expect(page.getByRole('heading',{name:'Overview',exact:true})).toBeVisible();
 await page.reload();await expect(page.getByRole('heading',{name:'Overview',exact:true})).toBeVisible();
 for(const route of ['customers','jobs','inventory','dispatch']){await page.goto('/'+route);await expect(page.getByRole('heading',{name:route[0].toUpperCase()+route.slice(1),exact:true})).toBeVisible();}
 await page.screenshot({path:'test-results/cloud-dispatch.png',fullPage:true});
 await page.goto('/customers');await page.getByRole('button',{name:'Add customer'}).click();
 const name='Verification '+Date.now();await page.getByLabel('Name',{exact:true}).fill(name);await page.getByLabel('Service address',{exact:true}).fill('124 Oak Lane');await page.getByRole('button',{name:'Save customer'}).click();await page.getByRole('button',{name,exact:true}).click();await page.getByRole('button',{name:'Create job',exact:true}).click();await page.getByLabel('Issue',{exact:true}).fill('Verification sink visit');await page.getByRole('button',{name:'Save job',exact:true}).click();
 await page.locator('tr').filter({hasText:'Verification sink visit'}).first().getByRole('button').first().click();await page.getByRole('button',{name:'Open in Dispatch'}).click();await expect(page.locator('.dispatch-inspector')).toContainText('Verification sink visit');
 await page.getByRole('button',{name:'Assign Maya',exact:true}).click();await expect(page.locator('.dispatch-inspector')).toContainText('Assigned');
 await page.getByRole('tab',{name:'Map',exact:true}).click();await page.getByRole('button',{name:'Start travel simulation',exact:true}).click();await page.getByRole('button',{name:'10×',exact:true}).click();await expect(page.getByRole('button',{name:'Start work',exact:true})).toBeVisible({timeout:30000});await page.getByRole('button',{name:'Start work',exact:true}).click();await page.getByRole('button',{name:'Complete job',exact:true}).click();
 await page.reload();await expect(page.locator('.dispatch-inspector')).toContainText('Completed');await page.getByRole('tab',{name:'Map',exact:true}).click();await page.getByRole('button',{name:'Return to depot',exact:true}).click();await page.getByRole('button',{name:'10×',exact:true}).click();await expect(page.locator('.sim-identity')).toContainText('Available',{timeout:30000});
 await page.goto('/inventory');const part=page.getByRole('button',{name:'Shut-off valve',exact:true}).first();await part.click();const before=await page.locator('.record-detail').innerText();await page.getByLabel('Stock adjustment (+ / -)').fill('1');await page.getByRole('button',{name:'Apply adjustment'}).click();await expect(page.getByRole('status')).toContainText('Record saved');await page.reload();expect(await page.locator('.record-detail').innerText()).not.toBe(before);
 await page.goto('/today');await expect(page).toHaveURL(/\/overview$/);await page.goto('/unknown-route');await expect(page.getByRole('heading',{name:'Page not found'})).toBeVisible();await page.goto('/sign-in');await expect(page).toHaveURL(/\/overview$/);
 await page.setViewportSize({width:390,height:844});await page.goto('/customers');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page).toHaveURL(/\/$/);await page.goto('/jobs');await expect(page).toHaveURL(/sign-in\?returnTo=/);await page.getByLabel('Username or email').fill(credentials.identifier);await page.getByLabel('Password',{exact:true}).fill(credentials.password);await page.getByRole('button',{name:/^Sign in/}).click();await expect(page).toHaveURL(/\/jobs$/);
 expect(failures).toEqual([]);
});
