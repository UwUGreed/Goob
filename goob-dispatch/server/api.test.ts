import { afterEach, describe, expect, it, vi } from 'vitest';
import { handleApi, type Env } from './api';
import { MemoryStore } from './store';
import { realStops } from '../src/integrations/geography';
import { jobs } from '../src/data';
import { demoDate, stamp } from '../src/schedule';
const origin='https://dispatch.example',session='00000000-0000-4000-8000-000000000001';
function request(path:string,body?:unknown,auth=true,requestOrigin=origin){return new Request(origin+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Dispatch-Session':session,'Origin':requestOrigin,...(auth?{'oai-authenticated-user-id':'dispatcher-one'}:{})},body:body===undefined?undefined:JSON.stringify(body)});}
afterEach(()=>vi.unstubAllGlobals());
describe('protected integrations',()=>{
  it('persists new demo requests and rejects assignments overlapping calendar bookings',async()=>{
    const store=new MemoryStore(),job={...jobs[0],id:'job-00000000-0000-4000-8000-000000000001',title:'New leak'};
    expect((await handleApi(request('/api/dispatch',{type:'create',job}),{},store)).status).toBe(200);
    const saved=await(await handleApi(request('/api/dispatch'),{},store)).json();expect(saved.state.customJobs[0].title).toBe('New leak');
    const slot={date:demoDate,travelStart:stamp(demoDate,12,30),start:stamp(demoDate,12,45),end:stamp(demoDate,13,45)};
    expect((await handleApi(request('/api/dispatch',{type:'assign',techId:'chris',jobId:'maple',slot}),{},store)).status).toBe(409);
    expect((await handleApi(request('/api/dispatch',{type:'assign',techId:'maya',jobId:job.id}),{},store)).status).toBe(200);
  });
  it('exposes only browser configuration and refuses anonymous or cross-origin access',async()=>{
    const env:Env={GOOGLE_MAPS_BROWSER_KEY:'browser-key',GOOGLE_MAPS_SERVER_KEY:'server-secret-sentinel',ELEVENLABS_API_KEY:'voice-secret-sentinel'};
    const config=await(await handleApi(request('/api/config'),env)).text();expect(config).toContain('browser-key');expect(config).not.toContain('secret-sentinel');
    const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
    expect((await handleApi(request('/api/scribe-token',{},false),env,new MemoryStore())).status).toBe(401);
    expect((await handleApi(request('/api/scribe-token',{},true,'https://other.example'),env,new MemoryStore())).status).toBe(403);expect(fetch).not.toHaveBeenCalled();
  });
  it('mints single-use tokens with a shared per-user limit and no permanent key in responses',async()=>{
    const fetch=vi.fn(async(_url:string|URL|Request,_options?:RequestInit)=>Response.json({token:'temporary-token'}));vi.stubGlobal('fetch',fetch);const store=new MemoryStore();
    for(let i=0;i<5;i++){const response=await handleApi(request('/api/scribe-token',{}),{ELEVENLABS_API_KEY:'permanent-secret'},store);expect(response.status).toBe(200);expect(response.headers.get('cache-control')).toContain('no-store');expect(await response.text()).not.toContain('permanent-secret');}
    expect((await handleApi(request('/api/scribe-token',{}),{ELEVENLABS_API_KEY:'permanent-secret'},store)).status).toBe(429);expect(fetch).toHaveBeenCalledTimes(5);
    expect(fetch.mock.calls[0][0]).toBe('https://api.elevenlabs.io/v1/single-use-token/realtime_scribe');
  });
  it('uses a driving-only Routes request with a narrow field mask and rejects invalid geography',async()=>{
    const fetch=vi.fn(async(_url:string|URL|Request,_options?:RequestInit)=>Response.json({routes:[{distanceMeters:600,duration:'180s',polyline:{encodedPolyline:'mock-polyline'}}]}));vi.stubGlobal('fetch',fetch);const store=new MemoryStore(),env={GOOGLE_MAPS_SERVER_KEY:'routing-secret'};
    expect((await handleApi(request('/api/routes',{origin:{lat:0,lng:0},destination:realStops['3-2']}),env,store)).status).toBe(400);
    const response=await handleApi(request('/api/routes',{origin:realStops['0-3'],destination:realStops['3-2']}),env,store);expect(response.status).toBe(200);expect(await response.text()).not.toContain('routing-secret');
    const options=fetch.mock.calls[0][1] as RequestInit;expect(new Headers(options.headers).get('X-Goog-FieldMask')).toBe('routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline');expect(JSON.parse(options.body as string).travelMode).toBe('DRIVE');expect(response.headers.get('cache-control')).toContain('no-store');
  });
  it('rechecks skills, prevents duplicate and concurrent assignments, and separates approval from travel',async()=>{
    const store=new MemoryStore();await handleApi(request('/api/dispatch'),{},store);
    expect((await handleApi(request('/api/dispatch',{type:'assign',techId:'chris',jobId:'oak'}),{},store)).status).toBe(409);
    const responses=await Promise.all([1,2].map(()=>handleApi(request('/api/dispatch',{type:'assign',techId:'maya',jobId:'oak'}),{},store)));expect(responses.map(r=>r.status).sort()).toEqual([200,409]);
    const payload=await(await handleApi(request('/api/dispatch'),{},store)).json();expect(payload.state.technicians.maya.status).toBe('Assigned');expect(payload.state.technicians.maya.running).toBe(false);
    expect((await handleApi(request('/api/dispatch',{type:'assign',techId:'maya',jobId:'oak'}),{},store)).status).toBe(409);
    expect((await handleApi(request('/api/dispatch',{type:'work',techId:'maya'}),{},store)).status).toBe(409);
    expect((await handleApi(request('/api/dispatch',{type:'start',techId:'maya'}),{},store)).status).toBe(200);
    expect((await handleApi(request('/api/dispatch',{type:'arrive',techId:'maya'}),{},store)).status).toBe(200);
    expect((await handleApi(request('/api/dispatch',{type:'work',techId:'maya'}),{},store)).status).toBe(200);
    expect((await handleApi(request('/api/dispatch',{type:'complete',techId:'maya'}),{},store)).status).toBe(200);
    expect((await handleApi(request('/api/dispatch',{type:'return',techId:'maya'}),{},store)).status).toBe(200);
  });
  it('has useful missing-credential errors and cannot mutate inventory or accept client route data',async()=>{
    const store=new MemoryStore();expect((await handleApi(request('/api/scribe-token',{}),{},store)).status).toBe(503);
    expect((await handleApi(request('/api/routes',{origin:realStops['0-3'],destination:realStops['3-2']}),{},store)).status).toBe(503);
    expect((await handleApi(request('/api/dispatch',{type:'inventory',quantity:99}),{},store)).status).toBe(400);
    expect((await handleApi(request('/api/dispatch',{type:'assign',techId:'maya',jobId:'oak',driving:{coordinates:[]}}),{},store)).status).toBe(400);
  });
});
