import { useEffect, useReducer } from 'react';
import { depot, jobs, technicians, inventory } from './data';
import { findRoute, routeLength } from './routing';
import type { Simulation, TechState } from './types';
export type Action = {type:'assign';techId:string;jobId:string} | {type:'start'|'pause'|'work'|'complete'|'return';techId:string} | {type:'tick';dt:number} | {type:'speed';speed:number} | {type:'reset'};
export function initialState():Simulation {
  return {speed:1,technicians:Object.fromEntries(technicians.map(t=>[t.id,{status:t.id==='jordan'?'Working':'Available',node:t.start,jobId:t.id==='jordan'?'cedar':undefined,route:[],progress:0,running:false,duration:0}])),jobs:Object.fromEntries(jobs.map(j=>[j.id,j.id==='cedar'?'Working':'Unassigned']))};
}
export function eligible(state:Simulation,techId:string,jobId:string) {
  const tech=technicians.find(t=>t.id===techId),job=jobs.find(j=>j.id===jobId),ts=state.technicians[techId];
  return !!(tech && job && ts && (ts.status==='Available'||ts.status==='Completed') && state.jobs[jobId]==='Unassigned' && tech.trade===job.trade && inventory.some(i=>i.part===job.part&&i.truck===tech.truck&&i.quantity>0) && (jobId!=='willow'||state.jobs.oak==='Completed'));
}
function travel(ts:TechState,destination:string):TechState {
  const route=findRoute(ts.node,destination);
  return {...ts,route,progress:0,running:false,duration:Math.max(10,routeLength(route)/20)};
}
export function reducer(state:Simulation,action:Action):Simulation {
  if(action.type==='reset') return initialState();
  if(action.type==='speed') return [1,5,10].includes(action.speed)?{...state,speed:action.speed}:state;
  if(action.type==='tick') {
    const next={...state,technicians:{...state.technicians},jobs:{...state.jobs}};
    Object.entries(state.technicians).forEach(([id,t])=>{
      if(!t.running) return;
      const progress=Math.min(1,t.progress+action.dt*state.speed/t.duration);
      next.technicians[id]={...t,progress};
      if(progress===1) {
        const returning=t.status==='Returning';
        next.technicians[id]={...t,progress:1,running:false,node:returning?depot:jobs.find(j=>j.id===t.jobId)!.node,status:returning?'Available':'Arrived',jobId:returning?undefined:t.jobId};
        if(!returning && t.jobId) next.jobs[t.jobId]='Arrived';
      }
    });
    return next;
  }
  const t=state.technicians[action.techId]; if(!t) return state;
  let updated={...t}; const jobStates={...state.jobs};
  if(action.type==='assign') {
    if(!eligible(state,action.techId,action.jobId)) return state;
    updated={...travel(t,jobs.find(j=>j.id===action.jobId)!.node),status:'Assigned',jobId:action.jobId};jobStates[action.jobId]='Assigned';
  } else if(action.type==='start') {
    if(!['Assigned','En route','Returning'].includes(t.status)||t.running) return state;
    updated={...t,running:true,status:t.status==='Returning'?'Returning':'En route'};
    if(t.jobId && t.status!=='Returning') jobStates[t.jobId]='En route';
  } else if(action.type==='pause') {updated.running=false;
  } else if(action.type==='work') {
    if(t.status!=='Arrived'||!t.jobId) return state;
    updated.status='Working';jobStates[t.jobId]='Working';
  } else if(action.type==='complete') {
    if(t.status!=='Working'||!t.jobId) return state;
    updated.status='Completed';jobStates[t.jobId]='Completed';
  } else if(action.type==='return') {
    if(t.status!=='Completed') return state;
    updated={...travel(t,depot),status:'Returning',running:true};
  }
  return {...state,technicians:{...state.technicians,[action.techId]:updated},jobs:jobStates};
}
export function useSimulation() {
  const [state,dispatch]=useReducer(reducer,undefined,initialState);
  const moving=Object.values(state.technicians).some(t=>t.running);
  useEffect(()=>{
    if(!moving) return;
    let last=performance.now();
    const timer=window.setInterval(()=>{const now=performance.now();dispatch({type:'tick',dt:Math.min((now-last)/1000,.5)});last=now;},50);
    return ()=>clearInterval(timer);
  },[moving]);
  return {state,dispatch};
}
