import { initialState, reducer, type Action } from '../src/simulation';
import { realStops, type GeoPoint } from '../src/integrations/geography';
import { allJobs } from '../src/schedule';
import { depot } from '../src/data';
import { D1Store, type Database, type DispatchStore } from './store';
import type { Simulation } from '../src/types';
export type Env={GOOGLE_MAPS_BROWSER_KEY?:string;GOOGLE_MAP_ID?:string;GOOGLE_MAPS_SERVER_KEY?:string;ELEVENLABS_API_KEY?:string;DB?:Database};
const json=(value:unknown,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
const configured=(value?:string)=>!!value&&!value.startsWith('your_');
export async function handleApi(request:Request,env:Env,localStore?:DispatchStore):Promise<Response>{
  const url=new URL(request.url),owner=request.headers.get('oai-authenticated-user-id');
  if(url.pathname==='/api/config')return json({browserKey:configured(env.GOOGLE_MAPS_BROWSER_KEY)?env.GOOGLE_MAPS_BROWSER_KEY:'',mapId:configured(env.GOOGLE_MAP_ID)?env.GOOGLE_MAP_ID:'',routes:configured(env.GOOGLE_MAPS_SERVER_KEY),voice:configured(env.ELEVENLABS_API_KEY),authenticated:!!owner,localDemo:!!localStore});
  if(!owner)return json({error:'Sign in as a dispatcher to use routes, assignments, or the microphone.'},401);
  if(request.method==='POST'&&(request.headers.get('origin')!==url.origin||request.headers.get('sec-fetch-site')==='cross-site'))return json({error:'This request must come from the dispatch dashboard.'},403);
  const store=localStore??(env.DB?new D1Store(env.DB):null);if(!store)return json({error:'Dispatch storage is not configured. Configure the server database binding.'},503);
  const bucket=Math.floor(Date.now()/60000),operation=url.pathname==='/api/scribe-token'?'voice':url.pathname==='/api/routes'?'routes':'dispatch';
  try{
    if(!await store.limit(`${owner}:${operation}`,bucket,operation==='voice'?5:operation==='routes'?30:120))return json({error:'Too many requests. Wait a minute and try again.'},429);
    if(operation==='voice'&&!await store.limit(`ip:${request.headers.get('cf-connecting-ip')??owner}:voice`,bucket,20))return json({error:'Microphone token request limit reached. Try again in a minute.'},429);
    if(url.pathname==='/api/scribe-token'&&request.method==='POST'){
      if(!configured(env.ELEVENLABS_API_KEY))return json({error:'Voice is not configured. Use a typed command, or configure ELEVENLABS_API_KEY on the server.'},503);
      const response=await fetch('https://api.elevenlabs.io/v1/single-use-token/realtime_scribe',{method:'POST',headers:{'xi-api-key':env.ELEVENLABS_API_KEY!},signal:AbortSignal.timeout(8000)});
      if(!response.ok)return json({error:response.status===429?'ElevenLabs quota or rate limit reached. Try a typed command.':'ElevenLabs could not authorize transcription. Check server configuration and account permissions.'},502);
      const token=await response.json() as {token?:string};if(!token.token)return json({error:'ElevenLabs did not return a microphone token.'},502);return json({token:token.token});
    }
    if(url.pathname==='/api/routes'&&request.method==='POST'){
      if(!configured(env.GOOGLE_MAPS_SERVER_KEY))return json({error:'Driving routes are not configured. Configure GOOGLE_MAPS_SERVER_KEY, or choose the fictional demo map.'},503);
      const body=await smallBody(request) as {origin?:GeoPoint;destination?:GeoPoint;options?:Record<string,unknown>};
      const valid=(p?:GeoPoint)=>p&&Number.isFinite(p.lat)&&Number.isFinite(p.lng)&&p.lat>33.96&&p.lat<34.06&&p.lng>-81.1&&p.lng<-80.98;
      if(!valid(body.origin)||!valid(body.destination))return json({error:'Routes must use valid demo locations within Columbia.'},400);
      if(body.options&&Object.entries(body.options).some(([key,value])=>!['avoidTolls','avoidHighways','avoidFerries'].includes(key)||typeof value!=='boolean'))return json({error:'Unsupported routing options.'},400);
      const response=await fetch('https://routes.googleapis.com/directions/v2:computeRoutes',{method:'POST',headers:{'Content-Type':'application/json','X-Goog-Api-Key':env.GOOGLE_MAPS_SERVER_KEY!,'X-Goog-FieldMask':'routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline'},body:JSON.stringify({origin:{location:{latLng:{latitude:body.origin!.lat,longitude:body.origin!.lng}}},destination:{location:{latLng:{latitude:body.destination!.lat,longitude:body.destination!.lng}}},travelMode:'DRIVE',routingPreference:'TRAFFIC_UNAWARE',polylineQuality:'HIGH_QUALITY',routeModifiers:body.options??{}}),signal:AbortSignal.timeout(10000)});
      if(!response.ok)return json({error:response.status===429?'Google Routes quota reached. Retry later or use the fictional demo map.':'Google driving route failed. Check the Routes key, billing, and API configuration; the fictional demo is available.'},502);
      const value=await response.json() as {routes?:{distanceMeters:number;duration:string;polyline:{encodedPolyline:string}}[]};const route=value.routes?.[0];
      if(!route?.polyline?.encodedPolyline)return json({error:'No driving route was found. The fictional demo is available.'},502);
      const durationSeconds=Number(route.duration?.replace(/s$/,''));if(!Number.isFinite(durationSeconds)||durationSeconds<=0)return json({error:'Google returned an invalid driving duration.'},502);
      // Route content is returned once with no-store; never written to D1/logs.
      return json({encodedPolyline:route.polyline.encodedPolyline,distanceMeters:route.distanceMeters,durationSeconds});
    }
    if(url.pathname==='/api/dispatch'){
      const session=request.headers.get('x-dispatch-session');if(!session||!/^[-a-f0-9]{36}$/i.test(session))return json({error:'A valid dispatch session is required.'},400);
      const id=`${owner}:${session}`;let row=await store.get(id);if(!row){await store.create(id,JSON.stringify(initialState()));row=await store.get(id);}if(!row)throw new Error('Storage unavailable');
      const state=JSON.parse(row.state) as Simulation;
      if(request.method==='GET')return json({state,revision:row.revision});
      if(request.method!=='POST')return json({error:'Unsupported request method.'},405);
      const action=await smallBody(request) as Record<string,unknown>;
      let next:Simulation;
      if(action.type==='arrive'){
        const techId=String(action.techId),tech=state.technicians[techId];if(!tech||!tech.running||!['En route','Returning'].includes(tech.status))return json({error:'This technician has no active journey to finish.'},409);
        const returning=tech.status==='Returning',node=returning?depot:allJobs(state).find(j=>j.id===tech.jobId)?.node;if(!node||!realStops[node])return json({error:'Unknown destination.'},400);
        next={...state,technicians:{...state.technicians,[techId]:{...tech,node,progress:1,running:false,status:returning?'Available':'Arrived',jobId:returning?undefined:tech.jobId}},jobs:{...state.jobs,...(!returning&&tech.jobId?{[tech.jobId]:'Arrived' as const}:{})}};
      }else{
        if(!['customer','stock','edit','assign','create','start','pause','work','complete','return','speed','reset'].includes(String(action.type))||Object.keys(action).some(k=>!['type','techId','jobId','speed','slot','job','customer','item'].includes(k)))return json({error:'Unsupported dispatch action.'},400);
        if(!['customer','stock','edit','create'].includes(String(action.type))&&action.type!=='reset'&&action.type!=='speed'&&typeof action.techId!=='string')return json({error:'Choose a technician.'},400);
        if(action.type==='assign'&&typeof action.jobId!=='string')return json({error:'Choose a job.'},400);
        next=reducer(state,action as Action);if(next===state)return json({error:'Assignment or status changed. Recheck qualifications, availability, job status, and parts before confirming.'},409);
      }
      if(!await store.put(id,row.revision,JSON.stringify(next)))return json({error:'Another dispatch action completed first. Refresh the proposal and try again.'},409);
      return json({state:next,revision:row.revision+1});
    }
    return json({error:'Endpoint not found.'},404);
  }catch{return json({error:'The service is temporarily unavailable. No assignment was approved by this request. Retry or use a typed command.'},502);}
}
async function smallBody(request:Request){const text=await request.text();if(text.length>4096)throw new Error('Request too large');return JSON.parse(text);}
