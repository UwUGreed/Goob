import { useEffect, useRef, useState } from 'react';
import { preset, resolveView, validConfiguration, type Account, type Configuration, type Page, type ViewList } from './config';

async function request<T>(path: string, body?: unknown, method='POST', key?: string): Promise<T> {
 const response=await fetch('/api/v1/workspace-views'+path,{method:body===undefined?'GET':method,credentials:'same-origin',headers:body===undefined?undefined:{'Content-Type':'application/json','Idempotency-Key':key??crypto.randomUUID()},body:body===undefined?undefined:JSON.stringify(body)});
 if(response.status===401)window.dispatchEvent(new Event('goob-session-expired'));
 if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('Workspace settings service is unavailable.');
 const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not save workspace settings.');return data;
}
const empty: ViewList={views:[],teamDefault:null,activeViewId:null};
export function useWorkspace(page: Page, account: Account) {
 const [data,setData]=useState<ViewList>(empty),[configuration,setConfiguration]=useState(()=>preset(page)),[editing,setEditing]=useState(false),[name,setName]=useState('My '+(page==='overview'?'overview':'dispatch')),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState(''),[loaded,setLoaded]=useState(false);
 const baseline=useRef(configuration),baselineName=useRef(name),cache='goob-workspace-v1:'+account.tenant+':'+account.userId+':'+page;
 const requestKey=useRef<{payload:string;key:string}|null>(null);
 const origin=useRef('default');
 const active=data.views.find(v=>v.id===data.activeViewId&&v.id===origin.current);
 function accept(next: ViewList, apply=true) {
  if([...next.views,...(next.teamDefault?[next.teamDefault]:[])].some(v=>!validConfiguration(v.configuration,page)))throw new Error('Saved workspace settings are incompatible. Use a starter layout and save a new view.');
  setData(next);setLoaded(true);
  if(apply){const c=resolveView(next,page);setConfiguration(c);setName(next.views.find(v=>v.id===next.activeViewId)?.name??next.teamDefault?.name??'My '+page);origin.current=next.activeViewId??'default';}
  try{localStorage.setItem(cache,JSON.stringify(next));}catch{/* Cloud persistence is authoritative. */}
 }
 useEffect(()=>{
  let alive=true;setLoaded(false);setEditing(false);setData(empty);setConfiguration(preset(page));setError('');
  request<ViewList>('?page='+page).then(next=>{if(alive)accept(next);}).catch(e=>{if(!alive)return;setLoaded(true);setError(e.message);try{const cached=JSON.parse(localStorage.getItem(cache)||'null');if(cached)accept(cached);}catch{/* Retain a safe starter. */}});
  return()=>{alive=false;};
 },[cache,page]);
 function change(update: Configuration | ((c:Configuration)=>Configuration)) {setConfiguration(update);setMessage('');}
 function begin(){baseline.current=structuredClone(configuration);baselineName.current=name;setEditing(true);setMessage('');}
 function cancel(){setConfiguration(baseline.current);setName(baselineName.current);setEditing(false);setError('');}
 async function run(operation: ()=>Promise<void>) {setBusy(true);setError('');try{await operation();}catch(e){setError(e instanceof Error?e.message:'Could not save settings.');}finally{setBusy(false);}}
 async function reload(){await run(async()=>{accept(await request<ViewList>('?page='+page),!editing);setMessage(editing?'Saved views refreshed. Your draft is retained; retry Save to replace the current revision.':'Saved views refreshed.');});}
 function save(asNew=false) {return run(async()=>{
  const updating=!asNew&&origin.current===active?.id;
  const path=updating?'/'+active!.id:'',method=updating?'PATCH':'POST';
  const body=updating?{revision:active!.revision,name,configuration}:{page,name,configuration};
  const payload=JSON.stringify([path,body,method]);if(requestKey.current?.payload!==payload)requestKey.current={payload,key:crypto.randomUUID()};
  const saved=await request<{id:string}>(path,body,method,requestKey.current!.key);
  if(updating)await request('/selection',{page,view_id:saved.id});
  accept(await request<ViewList>('?page='+page));setEditing(false);requestKey.current=null;setMessage('View saved to your account.');
 });}
 function select(value: string) {return run(async()=>{
  if(value.startsWith('preset:')){const kind=value.slice(7) as 'balanced'|'dispatch'|'owner';origin.current=value;setConfiguration(preset(page,kind));setName(kind[0].toUpperCase()+kind.slice(1));setMessage('Starter loaded. Save as new to keep a personal copy.');return;}
  await request('/selection',{page,view_id:value==='default'?null:value});accept(await request<ViewList>('?page='+page));setMessage(value==='default'?'Following the team default.':'Saved view opened.');
 });}
 function remove(){if(!active)return Promise.resolve();return run(async()=>{await request('/'+active.id,{revision:active.revision},'DELETE');accept(await request<ViewList>('?page='+page));setEditing(false);setMessage('Personal view deleted. Following the team default.');});}
 function publish(){return run(async()=>{await request('/team-default',{page,name,configuration,revision:data.teamDefault?.revision??0});accept(await request<ViewList>('?page='+page),false);setMessage('Team default published. Personal views were preserved.');});}
 function duplicate(){if(!active)return Promise.resolve();return run(async()=>{await request('',{page,name:(active.name+' copy').slice(0,80),configuration:active.configuration});accept(await request<ViewList>('?page='+page));setMessage('Personal view duplicated.');});}
 return {page,configuration,change,data,active,name,setName,editing,begin,cancel,busy,error,message,loaded,save,select,remove,publish,reload,duplicate,selected:origin.current};
}
export type Workspace = ReturnType<typeof useWorkspace>;
