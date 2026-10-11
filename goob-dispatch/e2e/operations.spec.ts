import {test,expect} from './fixtures';
test('operations routes, customer to assignment, persisted records and stock validation',async({page})=>{
 await page.goto('/');await expect(page).toHaveURL(/\/overview$/);
 await page.getByRole('button',{name:'Customers',exact:true}).click();await page.getByRole('button',{name:'Add customer'}).click();
 await page.getByLabel('Name',{exact:true}).fill('Pat Demo');await page.getByLabel('Email',{exact:true}).fill('pat@example.test');await page.getByLabel('Service address',{exact:true}).fill('124 Oak Lane');await page.getByRole('button',{name:'Save customer'}).click();
 await page.getByRole('button',{name:'Pat Demo',exact:true}).click();await page.getByRole('button',{name:'Edit customer',exact:true}).click();await page.getByLabel('Phone',{exact:true}).fill('555-0100');await page.getByRole('button',{name:'Save customer'}).click();await expect(page.locator('.record-detail')).toContainText('555-0100');await page.getByRole('button',{name:'Create job',exact:true}).click();
 await expect(page.getByLabel('Service address',{exact:true})).toHaveValue('124 Oak Lane');await page.getByLabel('Issue',{exact:true}).fill('Pat sink repair');await page.getByRole('button',{name:'Save job',exact:true}).click();
 await page.getByRole('button',{name:/#2000/}).click();await page.getByRole('button',{name:'Edit job',exact:true}).click();await page.getByLabel('Details',{exact:true}).fill('Please inspect the supply line.');await page.getByRole('button',{name:'Save job',exact:true}).click();await page.getByRole('button',{name:'Open in Dispatch'}).click();await expect(page).toHaveURL(/dispatch\?job=job-/);await expect(page.locator('.dispatch-inspector')).toContainText('Pat sink repair');await page.getByRole('button',{name:'Assign Maya',exact:true}).click();await expect(page.locator('.dispatch-inspector')).toContainText('Assigned');
 await page.reload();await expect(page.locator('.dispatch-inspector')).toContainText('Assigned');
 await page.getByRole('button',{name:'Inventory',exact:true}).click();await page.getByRole('button',{name:/angle stop valve/,exact:false}).click();await expect(page.locator('.record-detail')).toContainText('1 reserved');
 await page.getByLabel('Stock adjustment').fill('-3');await page.getByRole('button',{name:'Apply adjustment'}).click();await expect(page.getByRole('alert').last()).toContainText('Could not save');
 await page.getByLabel('Stock adjustment').fill('2');await page.getByRole('button',{name:'Apply adjustment'}).click();await expect(page.locator('.record-detail')).toContainText('5 on hand');
 await page.goBack();await expect(page).toHaveURL(/inventory$/);await page.goForward();await expect(page).toHaveURL(/inventory\/part-0$/);await page.goto('/today');await expect(page).toHaveURL(/\/overview$/);await page.goto('/missing');await expect(page.getByRole('heading',{name:'Page not found'})).toBeVisible();
 await page.goto('/customers');await expect(page.getByRole('button',{name:'Pat Demo',exact:true})).toBeVisible();await page.screenshot({path:'test-results/customers-desktop.png'});
 await page.getByRole('button',{name:'Jobs',exact:true}).click();await page.screenshot({path:'test-results/jobs-desktop.png'});
 await page.getByRole('button',{name:'Overview',exact:true}).click();await page.screenshot({path:'test-results/overview-desktop.png'});
 await page.getByRole('button',{name:'Inventory',exact:true}).click();await page.screenshot({path:'test-results/inventory-desktop.png'});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'test-results/inventory-mobile.png'});expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('warehouse items, editing, searches and empty states',async({page})=>{
 await page.goto('/inventory');await page.getByRole('button',{name:'Add item'}).click();await page.getByLabel('Part name').fill('Demo copper fitting');await page.getByLabel('SKU').fill('DEMO-99');await page.getByLabel('Quantity',{exact:true}).fill('10');await page.getByRole('button',{name:'Save item'}).click();
 await page.getByLabel('Location',{exact:true}).selectOption('Warehouse');await expect(page.getByRole('button',{name:'Demo copper fitting'})).toBeVisible();await page.getByRole('button',{name:'Demo copper fitting'}).click();await page.getByRole('button',{name:'Edit item'}).click();await page.getByLabel('Quantity',{exact:true}).fill('12');await page.getByRole('button',{name:'Save item'}).click();await expect(page.locator('.record-detail')).toContainText('12 on hand');
 await page.getByRole('button',{name:'Inventory',exact:true}).click();await page.getByRole('textbox',{name:'Search inventory'}).fill('nothing-matches');await expect(page.getByText('No matching records.')).toBeVisible();
 await page.getByRole('button',{name:'Jobs',exact:true}).click();await page.getByLabel('Status',{exact:true}).selectOption('Completed');await expect(page.getByText('No jobs match this view.')).toBeVisible();
});
