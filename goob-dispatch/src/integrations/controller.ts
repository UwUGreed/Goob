import { useEffect, useRef, useState } from 'react';
import { useSimulation, reducer, type Action } from '../simulation';
import { allJobs } from '../schedule';
import { depot, technicians, teamRecords } from '../data';
import { api, disconnectedConfig, fetchDrivingRoute, type IntegrationConfig } from './api';
import { findRoute, routeLength } from '../routing';
import { geoPosition, realStops, type DrivingRoute } from './geography';
import type { Job, JobStatus, Selection, Simulation } from '../types';
export function useDispatchController(selection:Selection,realMap:boolean){
  const {state,dispatch:local,motion}=useSimulation({databaseBacked:true,records:[],roster:[],stock:[],customers:[],jobs:{},technicians:{},speed:1}),current=useRef(state);current.current=motion.getState();
  const [config,setConfig]=useState<IntegrationConfig>(disconnectedConfig),[configLoaded,setConfigLoaded]=useState(false),[ready,setReady]=useState(false),[pending,setPending]=useState(false),[error,setError]=useState('');
  const locked=useRef(false),arrivals=useRef(new Set<string>()),arrivalRequests=useRef(new Map<string,Promise<boolean>>()),alive=useRef(true);
  useEffect(()=>{alive.current=true;api<IntegrationConfig>('/api/config').then(async c=>{if(!alive.current)return;setConfig(c);setConfigLoaded(true);if(!c.authenticated)throw new Error('Sign in to open database records.');const saved=await api<{state:Simulation}>('/api/dispatch');const hydrated={...saved.state,technicians:{...saved.state.technicians}};for(const [id,t] of Object.entries(hydrated.technicians)){const visit=allJobs(hydrated).find(j=>j.id===t.jobId);const destination=t.status==='Returning'?depot:visit?.node;if(destination&&realStops[t.node]&&realStops[destination]&&['Assigned','En route','Returning'].includes(t.status)){const route=findRoute(t.node,destination);hydrated.technicians[id]={...t,route,duration:Math.max(10,routeLength(route)/20),running:false};}}local({type:'replace',state:hydrated});if(alive.current)setReady(true);}).catch(e=>{if(alive.current){setConfigLoaded(true);setError(e.message);}});return()=>{alive.current=false;};},[]);
  useEffect(()=>{
    let request=0;
    const refresh=()=>{
      if(!ready)return;
      const number=++request;
      api<{state:Simulation}>('/api/dispatch').then(saved=>{
        if(!alive.current||number!==request)return;
        const current=motion.getState();
        local({type:'replace',state:{...saved.state,technicians:Object.fromEntries(Object.entries(saved.state.technicians).map(([id,t])=>[id,current.technicians[id]?.status===t.status&&current.technicians[id]?.jobId===t.jobId?current.technicians[id]:t])),speed:current.speed}});
      }).catch(e=>{if(alive.current&&number===request)setError(e.message);});
    };
    const events=['goob-records-changed','goob-navigation','focus'];
    events.forEach(event=>window.addEventListener(event,refresh));
    return()=>{request++;events.forEach(event=>window.removeEventListener(event,refresh));};
  },[ready]);
  const [selectionError,setSelectionError]=useState(''),[selectionLoading,setSelectionLoading]=useState(false);
  const selectedId=selection?.type==='job'?selection.id:'';
  const present=!!selectedId&&allJobs(state).some(j=>j.id===selectedId);
  useEffect(()=>{
    setSelectionError('');setSelectionLoading(false);
    if(!ready||!selectedId||present)return;
    const abort=new AbortController();setSelectionLoading(true);
    fetch('/api/dispatch/jobs/'+encodeURIComponent(selectedId),{credentials:'same-origin',signal:abort.signal}).then(async response=>{
      if(!response.ok)throw new Error(response.status===404?'Job not found.':response.status===403?'Access denied for this job.':'Unable to load this job. Please retry.');
      const value=await response.json() as {job:Job;status:JobStatus};
      if(abort.signal.aborted)return;
      const latest=motion.getState();local({type:'replace',state:{...latest,records:[...(latest.records??[]).filter(j=>j.id!==value.job.id),value.job],jobs:{...latest.jobs,[value.job.id]:value.status}}});
    }).catch(e=>{if(!abort.signal.aborted)setSelectionError(e.message);}).finally(()=>{if(!abort.signal.aborted)setSelectionLoading(false);});
    return()=>abort.abort();
  },[ready,selectedId,present]);
  const technicians=teamRecords(state),jobs=allJobs(state);
  const explicit=selection?.type==='job'?jobs.find(j=>j.id===selection.id):undefined;
  const tech=selection?.type==='tech'?technicians.find(t=>t.id===selection.id):technicians.find(t=>state.technicians[t.id]?.jobId===explicit?.id)??technicians.find(t=>t.trade===explicit?.trade);
  const job=explicit??jobs.find(j=>j.id===(tech&&state.technicians[tech.id].jobId));
  const ts=tech?state.technicians[tech.id]:undefined;
  const routeKey=realMap&&config.browserKey&&job&&tech&&ts&&realStops[ts.node]&&realStops[job.node]&&state.jobs[job.id]==='Unassigned'&&['Available','Completed'].includes(ts.status)?`${tech.id}/${ts.node}/${job.id}`:'';
  useEffect(()=>{
    if(!routeKey){local({type:'preview',preview:undefined});return;}
    const abort=new AbortController(),origin=realStops[ts!.node],destination=realStops[job!.node];local({type:'preview',preview:{route:null,loading:true,error:'',key:routeKey}});
    if(!config.routes){local({type:'preview',preview:{route:null,loading:false,error:'Google driving routes are not configured. Configure the server key or choose the fictional demo map.',key:routeKey}});return;}
    fetchDrivingRoute(origin,destination,abort.signal).then(route=>{if(!abort.signal.aborted)local({type:'preview',preview:{route,loading:false,error:'',key:routeKey}});}).catch(e=>{if(!abort.signal.aborted)local({type:'preview',preview:{route:null,loading:false,error:`${e.message} No road route is being simulated.`,key:routeKey}});});
    return()=>abort.abort();
  },[routeKey,config.routes]);
  // Simulation interpolation is local and ephemeral. The backend owns approval
  // and status validation, and never persists Google route responses.
  useEffect(()=>{Object.entries(state.technicians).forEach(([id,t])=>{if(t.progress!==1||t.running||!['Arrived','Available'].includes(t.status)||!t.route.length||arrivals.current.has(id))return;arrivals.current.add(id);arrivalRequests.current.set(id,api('/api/dispatch',{type:'arrive',techId:id}).then(()=>true).catch(e=>{if(alive.current)setError(`${e.message} Retry status sync before starting work.`);return false;}));});},[state]);
  async function dispatch(action:Action):Promise<boolean>{
    current.current=motion.getState();
    if(action.type==='tick'||action.type==='replace'||action.type==='preview')return false;
    // Replay is a local presentation action, never a second dispatch approval.
    if(action.type==='replay'||(('techId' in action)&&current.current.technicians[action.techId]?.replay&&['start','pause'].includes(action.type))){if(locked.current)return false;local(action);return true;}
    if(action.type==='speed'){local(action);return true;}if(action.type==='reset'){for(const [id,t] of Object.entries(current.current.technicians)){if(t.running&&!t.replay&&!(await dispatch({type:'pause',techId:id})))return false;}local(action);return true;}
    if(locked.current)return false;if(!ready){setError('The authenticated dispatch server is unavailable. Assignments require server confirmation.');return false;}
    locked.current=true;setPending(true);setError('');
    try{
      if('techId' in action&&arrivalRequests.current.has(action.techId)){const synced=await arrivalRequests.current.get(action.techId);if(!synced)await api('/api/dispatch',{type:'arrive',techId:action.techId});arrivalRequests.current.delete(action.techId);}
      let driving:DrivingRoute|undefined;
      if(realMap&&config.browserKey&&(action.type==='assign'||action.type==='return')){
        if(action.type==='assign'){driving=current.current.preview?.route??undefined;if(!driving||current.current.preview?.key!==`${action.techId}/${current.current.technicians[action.techId].node}/${action.jobId}`)throw new Error('Wait for a verified Google driving route, or switch to the fictional demo map before confirming.');}
        else{const t=current.current.technicians[action.techId],origin=t.driving?geoPosition(t.driving.coordinates,1):realStops[t.node];driving=await fetchDrivingRoute(origin,realStops[depot]);}
      }
      // Remove any client-provided route data from requests to the approval API.
      const operational=["membership","property","movement","job-review","create","edit","customer","stock","image"].includes(action.type);
      const body=operational?action:action.type==='assign'?{type:action.type,techId:action.techId,jobId:action.jobId,...(action.slot?{slot:action.slot}:{})}:action.type==='create'||action.type==='edit'||action.type==='customer'||action.type==='stock'?action:{type:action.type,techId:"techId" in action?action.techId:undefined};
      const saved=await api<{state:Simulation}>('/api/dispatch',body);if(operational){local({type:'replace',state:{...saved.state,technicians:Object.fromEntries(Object.entries(saved.state.technicians).map(([id,t])=>[id,current.current.technicians[id]?.status===t.status&&current.current.technicians[id]?.jobId===t.jobId?current.current.technicians[id]:t])),speed:current.current.speed}});return true;}
      const visual=reducer(current.current,action.type==='assign'||action.type==='return'?{...action,driving}:action);local({type:'replace',state:{...saved.state,technicians:visual.technicians,speed:visual.speed}});if(action.type==='assign'||action.type==='return')arrivals.current.delete(action.techId);return true;
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:'Dispatch action failed.');return false;}
    finally{locked.current=false;if(alive.current)setPending(false);}
  }
  const hasGoogleJourney=Object.values(state.technicians).some(t=>t.driving&&['Assigned','En route','Arrived','Working','Returning'].includes(t.status));
  return{state,dispatch,motion,config,configLoading:!configLoaded,ready,pending,error,clearError:()=>setError(''),hasGoogleJourney,selectionError,selectionLoading};
}
