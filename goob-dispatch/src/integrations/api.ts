import { decodePolyline, type DrivingRoute, type GeoPoint } from './geography';
export type IntegrationConfig={browserKey:string;mapId:string;routes:boolean;voice:boolean;authenticated:boolean;localDemo:boolean};
export const disconnectedConfig:IntegrationConfig={browserKey:'',mapId:'',routes:false,voice:false,authenticated:false,localDemo:false};
export async function api<T>(path:string,body?:unknown,signal?:AbortSignal):Promise<T>{
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',cache:'no-store',signal});
  if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('Dispatch server is unavailable. Start the full application server.');
  const value=await response.json();if(response.status===401)window.dispatchEvent(new Event('goob-session-expired'));if(!response.ok)throw new Error(value.error??'The service could not complete this request.');return value as T;
}
export async function fetchDrivingRoute(origin:GeoPoint,destination:GeoPoint,signal?:AbortSignal):Promise<DrivingRoute>{
  const route=await api<{encodedPolyline:string;distanceMeters:number;durationSeconds:number}>('/api/routes',{origin,destination,options:{avoidTolls:false,avoidHighways:false,avoidFerries:false}},signal);
  const coordinates=decodePolyline(route.encodedPolyline);if(coordinates.length<2||!Number.isFinite(route.distanceMeters)||!Number.isFinite(route.durationSeconds)||route.durationSeconds<=0)throw new Error('Google returned an unusable driving route.');
  return{...route,coordinates,origin,destination,source:'google'};
}
