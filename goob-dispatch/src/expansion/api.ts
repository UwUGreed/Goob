import { useCallback, useEffect, useState } from 'react';

export type Row = {id:string; branch_id:string; name:string; revision:number; data:Record<string, any>; parent_id?:string|null; customer_id?:string|null; property_id?:string|null; equipment_id?:string|null};
export type Agreement = {id:string; branch_id:string; equipment_id:string; trade:string; service:string; status:string; canceled_on:string|null; revision:number; remaining:number};
export type Balance = {id:string; sku_id:string; location_id:string; on_hand:number; reserved:number; available:number; minimum:number; target:number; replenish:number};
export type JobWorkspace = {job:Row; customer:Row; property:Row; equipment:Row; coverage:Record<string, any>; readiness:{state:string;checks:Array<{id:string;state:string;reason?:string;required?:number;reserved_or_issued?:number}>}; notes:Array<Record<string,any>>;proposals:Array<Record<string,any>>;invoices:Array<Record<string,any>>;movements:Array<Record<string,any>>;reservations:Array<Record<string,any>>;events:Array<Record<string,any>>;parts:Row[];stock:Balance[];locations:Row[]};

export async function api<T>(path:string, body?:unknown, method?:'POST'|'PATCH'):Promise<T>{
  const write=body!==undefined||method!==undefined;
  const response=await fetch('/api/v1'+path,{method:method??(write?'POST':'GET'),credentials:'same-origin',headers:write?{'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()}:undefined,body:write?JSON.stringify(body??{}):undefined});
  if(response.status===401){window.dispatchEvent(new Event('goob-session-expired'));throw new Error('Your session expired. Sign in again.');}
  if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('Operations API is unavailable.');
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||`Request failed (${response.status}).`);
  if(write)window.dispatchEvent(new Event('goob-records-changed'));
  return result as T;
}

export function useResource<T>(path:string){
  const [data,setData]=useState<T|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
  const reload=useCallback(async()=>{setLoading(true);try{setData(await api<T>(path));setError('');}catch(e){setError(e instanceof Error?e.message:'Could not load records.');}finally{setLoading(false);}},[path]);
  useEffect(()=>{void reload();},[reload]);
  return {data,loading,error,reload};
}

export function asText(value:unknown){return value==null?'':String(value);}
export function label(rows:Row[]|null|undefined,id:string|null|undefined){return rows?.find(r=>r.id===id)?.name||id||'Not recorded';}
export function today(){return new Date().toLocaleDateString('en-CA');}
