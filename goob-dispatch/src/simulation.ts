import { useCallback, useEffect, useRef, useState } from 'react';
import { depot, jobs, technicians, stockFixtures, customerFixtures, teamRecords } from './data';
import { findRoute, routeLength, nodes } from './routing';
import { allJobs, proposedSlot, slotAllowed } from './schedule';
import type { Job, Customer, StockItem, ScheduleSlot, Simulation, TechState } from './types';
import type { DrivingRoute } from './integrations/geography';
export type Action = {type:"membership";operation:string;values:Record<string,unknown>}|{type:"property"|"movement"|"job-review"|"image";values:Record<string,unknown>}|{type:'customer';customer:Customer}|{type:'stock';item:StockItem}|{type:'edit';job:Job}| {type:'assign';techId:string;jobId:string;slot?:ScheduleSlot;driving?:DrivingRoute} | {type:'start'|'pause'|'replay'|'work'|'complete'|'return';techId:string;driving?:DrivingRoute} | {type:'create';job:Job} | {type:'tick';dt:number} | {type:'speed';speed:number} | {type:'reset'} | {type:'replace';state:Simulation} | {type:'preview';preview:Simulation['preview']};
export function initialState():Simulation {
  return {customers:customerFixtures,stock:stockFixtures,speed:1,technicians:Object.fromEntries(technicians.map(t=>[t.id,{status:t.id==='jordan'?'Working':'Available',node:t.start,jobId:t.id==='jordan'?'cedar':undefined,route:[],progress:0,running:false,duration:0}])),jobs:Object.fromEntries(jobs.map(j=>[j.id,j.id==='cedar'?'Working':'Unassigned']))};
}
export function freshDemoState():Simulation {
 const base=initialState();return {...base,databaseBacked:false,demoSandbox:true,jobs:Object.fromEntries(jobs.map(j=>[j.id,'Unassigned'])),technicians:Object.fromEntries(technicians.map(t=>[t.id,{status:'Available',node:t.start,route:[],progress:0,running:false,duration:0}]))};
}
export const stockRecords=(state:Simulation):StockItem[]=>state.stock??stockFixtures;
export function reservedCount(state:Simulation,truck:string,part:string,exclude?:string){if(state.reservations)return state.reservations.filter(r=>r.truck===truck&&r.part===part&&r.jobId!==exclude).reduce((n,r)=>n+r.quantity,0);return Object.entries(state.technicians).filter(([id,t])=>teamRecords(state).find(x=>x.id===id)?.truck===truck&&t.jobId!==exclude&&['Assigned','En route','Arrived','Working'].includes(t.status)&&allJobs(state).find(j=>j.id===t.jobId)?.part===part).length;}
export function partsReady(state:Simulation,truck:string,part:string,jobId?:string){return stockRecords(state).some(i=>i.truck===truck&&i.part===part&&i.quantity-reservedCount(state,truck,part,jobId)>0);}
export function eligible(state:Simulation,techId:string,jobId:string) {
  const tech=teamRecords(state).find(t=>t.id===techId),job=allJobs(state).find(j=>j.id===jobId),ts=state.technicians[techId];
  return !!(tech && job && ts && (ts.status==='Available'||ts.status==='Completed') && state.jobs[jobId]==='Unassigned' && tech.trade===job.trade && (!state.databaseBacked||tech.branchId===job.branchId) && (job.requirements?job.requirements.every(n=>stockRecords(state).some(i=>i.truck===tech.truck&&i.part===n.part&&i.skuId===n.skuId&&i.locationId===tech.locationId&&i.quantity-reservedCount(state,tech.truck,n.part,jobId)>=n.quantity)):partsReady(state,tech.truck,job.part,jobId)) && (jobId!=='willow'||state.jobs.oak==='Completed'));
}
function travel(ts:TechState,destination:string,driving?:DrivingRoute):TechState {
  const route=findRoute(ts.node,destination);
  return {...ts,route,driving,progress:0,running:false,duration:driving?Math.max(12,Math.min(90,driving.durationSeconds/20)):Math.max(10,routeLength(route)/20)};
}
export function reducer(state:Simulation,action:Action):Simulation {
  if(action.type==='customer'){
    const c=action.customer;if(!c||typeof c.id!=='string'||![c.name,c.email,c.phone,c.address].every(v=>typeof v==='string')||!c.name.trim()||!c.address.trim()||c.name.length>80||c.address.length>200||(c.email&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c.email)))return state;
    return {...state,customers:[...(state.customers??customerFixtures).filter(x=>x.id!==c.id),c]};
  }
  if(action.type==='stock'){
    const i=action.item;if(!i||typeof i.id!=='string'||![i.part,i.sku,i.truck].every(v=>typeof v==='string'&&!!v.trim())||!['Plumbing','HVAC','Electrical'].includes(i.trade)||!['Warehouse',...technicians.map(t=>t.truck)].includes(i.truck)||!Number.isSafeInteger(i.quantity)||i.quantity<0||!Number.isSafeInteger(i.threshold)||i.threshold<0)return state;
    if(i.quantity<reservedCount(state,i.truck,i.part))return state;
    const stock=state.stock??stockFixtures,original=stock.find(x=>x.id===i.id);if(original&&reservedCount(state,original.truck,original.part)>0&&(original.truck!==i.truck||original.part!==i.part))return state;if(stock.some(x=>x.id!==i.id&&x.part===i.part&&x.truck===i.truck))return state;
    return {...state,stock:[...stock.filter(x=>x.id!==i.id),i]};
  }
  if(action.type==='create'||action.type==='edit'){
    const job=action.job;if(!job||typeof job!=='object'||!['id','title','address','customer','description','part','node','trade','time'].every(k=>typeof job[k as keyof Job]==='string'))return state;
    if(!jobs.some(j=>j.node===job.node)||!['Plumbing','HVAC','Electrical'].includes(job.trade)||!job.title.trim()||!job.address.trim()||!job.customer.trim()||!job.part.trim()||job.title.length>80||job.description.length>500||job.customer.length>80)return state;
    if(job.address!==jobs.find(j=>j.node===job.node)?.address&&!(state.customers??customerFixtures).some(c=>c.id===job.customerId&&c.address===job.address))return state;
    if(action.type==='create'&&(!/^job-[a-f0-9-]{36}$/.test(job.id)||allJobs(state).some(j=>j.id===job.id)))return state;
    if(action.type==='edit'&&state.jobs[job.id]!=='Unassigned')return state;
    return {...state,customJobs:[...(state.customJobs??[]).filter(j=>j.id!==job.id),job],jobs:{...state.jobs,[job.id]:state.jobs[job.id]??'Unassigned'}};
  }
  if(action.type==='replace')return action.state;
  if(action.type==='preview')return{...state,preview:action.preview};
  if(action.type==='reset') return state.demoSandbox?freshDemoState():state.databaseBacked?{...state,speed:1,preview:undefined,technicians:Object.fromEntries(Object.entries(state.technicians).map(([id,t])=>[id,{...t,running:false,replay:undefined}]))}:initialState();
  if(action.type==='speed') return [1,5,10].includes(action.speed)?{...state,speed:action.speed}:state;
  if(action.type==='tick') {
    const next={...state,technicians:{...state.technicians},jobs:{...state.jobs}};
    Object.entries(state.technicians).forEach(([id,t])=>{
      // Replays only move the presentation; the approved visit remains arrived.
      if(t.replay?.running){const progress=Math.min(1,t.replay.progress+action.dt*state.speed/t.duration);next.technicians[id]={...t,replay:{progress,running:progress<1}};return;}
      if(!t.running) return;
      const progress=Math.min(1,t.progress+action.dt*state.speed/t.duration);
      next.technicians[id]={...t,progress};
      if(progress===1) {
        const returning=t.status==='Returning';
        next.technicians[id]={...t,progress:1,running:false,node:returning?depot:allJobs(state).find(j=>j.id===t.jobId)!.node,status:returning?'Available':'Arrived',jobId:returning?undefined:t.jobId};
        if(!returning && t.jobId) next.jobs[t.jobId]='Arrived';
      }
    });
    return next;
  }
  if (!("techId" in action)) return state;
  const t=state.technicians[action.techId]; if(!t) return state;
  let updated={...t}; const jobStates={...state.jobs};
  if(action.type==='assign') {
    if(!eligible(state,action.techId,action.jobId)) return state;
    const slot=action.slot??proposedSlot(state,action.techId,action.jobId);if(!slot||!slotAllowed(state,action.techId,slot))return state;
    const assigned={...state.bookings,[action.jobId]:{...slot,techId:action.techId}};
    updated={...travel(t,allJobs(state).find(j=>j.id===action.jobId)!.node,action.driving),status:'Assigned',jobId:action.jobId};jobStates[action.jobId]='Assigned';return {...state,bookings:assigned,technicians:{...state.technicians,[action.techId]:updated},jobs:jobStates};
  } else if(action.type==='replay') {
    if(!['Arrived','Working','Completed'].includes(t.status)||t.running||t.replay?.running)return state;
    if(!t.route.length){
      const destination=allJobs(state).find(j=>j.id===t.jobId)?.node;
      if(!destination||!nodes[destination])return state;
      updated={...t,route:findRoute(depot,destination),driving:undefined};
    }
    updated.duration=Math.max(10,t.duration||routeLength(updated.route)/20);
    updated.replay={progress:0,running:true};
  } else if(action.type==='start') {
    if(t.replay&&['Arrived','Working','Completed'].includes(t.status)&&t.replay.progress<1){updated.replay={...t.replay,running:true};return {...state,technicians:{...state.technicians,[action.techId]:updated}};}
    if(!['Assigned','En route','Returning'].includes(t.status)||t.running) return state;
    updated={...t,running:true,status:t.status==='Returning'?'Returning':'En route'};
    if(t.jobId && t.status!=='Returning') jobStates[t.jobId]='En route';
  } else if(action.type==='pause') {updated.running=false;if(t.replay)updated.replay={...t.replay,running:false};
  } else if(action.type==='work') {
    if(t.status!=='Arrived'||!t.jobId) return state;
    updated.status='Working';updated.replay=undefined;jobStates[t.jobId]='Working';
  } else if(action.type==='complete') {
    if(t.status!=='Working'||!t.jobId) return state;
    updated.status='Completed';jobStates[t.jobId]='Completed';const part=allJobs(state).find(j=>j.id===t.jobId)?.part,truck=technicians.find(x=>x.id===action.techId)?.truck;state={...state,stock:stockRecords(state).map(i=>i.part===part&&i.truck===truck?{...i,quantity:Math.max(0,i.quantity-1)}:i)};
  } else if(action.type==='return') {
    if(t.status!=='Completed') return state;
    updated={...travel(t,depot,action.driving),status:'Returning',running:true};
  }
  return {...state,technicians:{...state.technicians,[action.techId]:updated},jobs:jobStates};
}
export type MotionSource={getState:()=>Simulation;subscribe:(listener:(state:Simulation,dt:number,now:number)=>void)=>()=>void};
export function useSimulation(seed?:Simulation) {
  const [state,setState]=useState(()=>seed??initialState()),live=useRef(state),listeners=useRef(new Set<(state:Simulation,dt:number,now:number)=>void>());
  const motion=useRef<MotionSource>({getState:()=>live.current,subscribe:listener=>{listeners.current.add(listener);return()=>{listeners.current.delete(listener);};}}).current;
  const dispatch=useCallback((action:Action)=>{live.current=reducer(live.current,action);setState(live.current);},[]);
  useEffect(()=>{
    let frame=0,last=performance.now(),published=last;
    const animate=(now:number)=>{
      try {
      const dt=Math.min(.1,Math.max(0,(now-last)/1000));last=now;
      const before=live.current;
      if(Object.values(before.technicians).some(t=>t.running||t.replay?.running)){
        live.current=reducer(before,{type:'tick',dt});
        const arrived=Object.entries(before.technicians).some(([id,t])=>t.status!==live.current.technicians[id].status||t.replay?.running!==live.current.technicians[id].replay?.running);
        // Paint vehicles every frame; publish readable progress to React at 5 Hz.
        if(arrived||now-published>=200){setState(live.current);published=now;}
      }
      listeners.current.forEach(listener=>listener(live.current,dt,now));
      } finally {frame=requestAnimationFrame(animate);}
    };
    frame=requestAnimationFrame(animate);return()=>cancelAnimationFrame(frame);
  },[]);
  return {state,dispatch,motion};
}
