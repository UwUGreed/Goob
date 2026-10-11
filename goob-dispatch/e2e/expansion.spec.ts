import {test,expect} from '@playwright/test';

test('portal exposes growth, coverage, stock, review and migration workflows',async({page})=>{
  const calls:string[]=[];
  const empty={databaseBacked:true,records:[],roster:[],stock:[],customers:[],reservations:[],bookings:{},jobs:{},technicians:{},speed:1};
  const customer={id:'customer-1',branch_id:'a',name:'Sample customer',revision:1,data:{email:'',phone:''}};
  const property={id:'property-1',branch_id:'a',name:'Oak Lane',revision:1,parent_id:'customer-1',data:{address:'124 Oak Lane'}};
  const unit={id:'unit-1',branch_id:'a',name:'Water heater',revision:1,parent_id:'property-1',data:{trade:'Plumbing',model:'',serial:''}};
  const part={id:'part-1',branch_id:'a',name:'Valve',revision:1,data:{trade:'Plumbing',barcode:'VALVE-1'}};
  const stockLocation={id:'location-1',branch_id:'a',name:'Warehouse',revision:1,data:{location_type:'warehouse'}};
  const job={id:'job-1',branch_id:'a',name:'Service visit',revision:1,customer_id:'customer-1',property_id:'property-1',equipment_id:'unit-1',data:{trade:'Plumbing',service:'repair',service_date:'2026-10-11',billing_mode:'unknown',customer_approved:false,required_materials:[],prerequisites:[],lines:[],currency:'USD'}};
  const workspace={job,customer,property,equipment:unit,coverage:{state:'uncovered'},readiness:{state:'unknown',checks:[]},notes:[],proposals:[],invoices:[],movements:[],reservations:[],events:[],parts:[],stock:[],locations:[]};
  await page.route('**/api/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;calls.push(`${request.method()} ${path}`);
    let payload:unknown=[];
    if(path==='/api/auth/session')payload={identifier:'demo',workspace:'Columbia demo',role:'owner',demo:true};
    else if(path==='/api/config')payload={authenticated:true,localDemo:false,browserKey:'',mapId:'',routes:false,voice:false};
    else if(path==='/api/dispatch')payload={state:empty};
    else if(path==='/api/v1/me')payload={branches:['a'],role:'owner'};
    else if(path==='/api/v1/records/customers')payload=[customer];
    else if(path==='/api/v1/records/properties')payload=[property];
    else if(path==='/api/v1/records/equipment')payload=[unit];
    else if(path==='/api/v1/records/skus')payload=[part];
    else if(path==='/api/v1/records/locations')payload=[stockLocation];
    else if(path==='/api/v1/records/jobs')payload=[job];
    else if(path==='/api/v1/jobs/job-1/workspace')payload=workspace;
    else if(path==='/api/v1/leads')payload={lead:{id:'lead-1',branch_id:'a',name:'New request',revision:1,customer_id:'customer-1',property_id:'property-1',data:{trade:'Plumbing',state:'reviewed'}},customer,property};
    else if(path==='/api/v1/opportunities'&&request.method()==='POST')payload={id:'opportunity-1',branch_id:'a',name:'Cross-trade service',customer_id:'customer-1',property_id:'property-1',revision:1,data:{trade:'HVAC',service:'repair',state:'reviewed'}};
    else if(path==='/api/v1/agreements'&&request.method()==='POST')payload={agreement:{id:'agreement-1',branch_id:'a',equipment_id:'unit-1',trade:'Plumbing',service:'repair',status:'active',revision:1,remaining:2}};
    else if(path==='/api/v1/agreements/agreement-1')payload={agreement:{id:'agreement-1',branch_id:'a',equipment_id:'unit-1',trade:'Plumbing',service:'repair',status:'active',revision:1},remaining:2,terms:[],ledger:[]};
    else if(path==='/api/v1/imports/csv')payload={id:'batch-1',state:'staged',rows:[{source_id:'c1',kind:'customers',name:'Imported customer',data:{email:'',phone:''},needs_review:'',resolution:''}],report:{issues:[]}};
    else if(path==='/api/v1/imports/batch-1')payload={id:'batch-1',state:'staged',rows:[{source_id:'c1',kind:'customers',name:'Imported customer',data:{email:'',phone:''},needs_review:'',resolution:''}],report:{issues:[]}};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(payload)});
  });
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/growth');await expect(page.getByRole('heading',{name:'Leads and opportunities'})).toBeVisible();
  await page.getByLabel('Customer name').fill('New request');await page.getByLabel('Service address').fill('10 Main St');await page.getByLabel('What does the customer need?').fill('Repair request');await page.getByRole('button',{name:'Capture lead'}).click();
  await expect(page.getByRole('status')).toContainText('Lead captured');expect(calls).toContain('POST /api/v1/leads');
  await page.getByRole('combobox',{name:'Customer',exact:true}).first().selectOption('customer-1');await page.getByRole('combobox',{name:'Service property'}).selectOption('property-1');await page.getByRole('textbox',{name:'Opportunity'}).fill('Offer HVAC service');await page.getByRole('button',{name:'Add opportunity'}).click();await expect(page.getByRole('status')).toContainText('Cross-trade opportunity');expect(calls).toContain('POST /api/v1/opportunities');
  for(const [path,heading] of [['memberships','Membership coverage'],['stock-ledger','Inventory movements'],['work-review','Work review'],['migration','Migration review']]){
    await page.goto('/'+path);await expect(page.getByRole('heading',{name:heading,exact:true})).toBeVisible();
  }
  await page.getByRole('button',{name:'Growth',exact:true}).click();await expect(page).toHaveURL(/\/growth$/);
  await page.goto('/memberships');await page.getByRole('combobox',{name:'Equipment',exact:true}).selectOption('unit-1');await page.getByRole('textbox',{name:'Coverage description'}).fill('Annual service');await page.getByLabel('Ends').fill('2027-10-11');await page.getByRole('button',{name:'Create agreement'}).click();await expect(page.getByRole('status')).toContainText('Agreement recorded');expect(calls).toContain('POST /api/v1/agreements');
  await page.getByRole('textbox',{name:'Plan name'}).fill('Home service care');await page.getByRole('button',{name:'Create plan'}).click();await expect(page.getByText('Service plan created.')).toBeVisible();expect(calls).toContain('POST /api/dispatch');
  await page.screenshot({path:'test-results/coverage-restored.png',fullPage:true});
  await page.goto('/stock-ledger');await page.getByRole('combobox',{name:'Part',exact:true}).selectOption('part-1');await page.getByRole('combobox',{name:'From / at location'}).selectOption('location-1');await page.getByRole('textbox',{name:'Reason'}).fill('Received supplier shipment');await page.getByRole('button',{name:'Confirm receive'}).click();await expect(page.getByRole('status')).toContainText('Receive recorded');expect(calls).toContain('POST /api/v1/inventory/commands');
  await page.goto('/migration');await page.getByRole('textbox',{name:'CSV contents'}).fill('source_id,kind,name,data\nc1,customers,Imported customer,"{""email"":"""",""phone"":""""}"');await page.getByRole('button',{name:'Stage for review'}).click();await expect(page.getByRole('status')).toContainText('Import staged');expect(calls).toContain('POST /api/v1/imports/csv');
  await page.goto('/work-review');await page.getByRole('combobox',{name:'Job'}).selectOption('job-1');await expect(page.getByText('Service visit',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Billing mode'}).selectOption('nonmember');await page.getByRole('checkbox',{name:'Customer approved the work and charges'}).check();await page.getByRole('button',{name:'Save approval and mode'}).click();expect(calls).toContain('PATCH /api/v1/records/jobs/job-1');
  await page.setViewportSize({width:390,height:844});await page.goto('/growth');await expect(page.getByRole('heading',{name:'Leads and opportunities'})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
