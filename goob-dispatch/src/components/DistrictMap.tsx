import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { MapPin, Plus, Minus, LocateFixed, Navigation, Warehouse, MousePointer2 } from 'lucide-react';
import { createDistrict } from '../mapScene';
import { jobs, technicians, depot, tradeColors } from '../data';
import { nodes, findRoute, pointOnRoute } from '../routing';
import { TradeIcon } from './Icons';
import type { Preferences, Selection, Simulation } from '../types';
type Props={state:Simulation;preferences:Preferences;selection:Selection;onSelect:(s:Selection)=>void;mode:'2D'|'3D';follow:string|null;onFollow:(id:string|null)=>void;reduced:boolean};
export function DistrictMap(props:Props) {
  const host=useRef<HTMLDivElement>(null),engine=useRef<ReturnType<typeof createDistrict>|null>(null),current=useRef(props),labels=useRef(new Map<string,HTMLButtonElement>());
  const [error,setError]=useState(false);current.current=props;
  const activeId=props.selection?.type==='tech'?props.selection.id:technicians.find(t=>props.state.technicians[t.id].jobId===props.selection?.id)?.id??technicians.find(t=>t.trade===jobs.find(j=>j.id===props.selection?.id)?.trade)?.id??'maya';
  useEffect(()=>{
    let e:ReturnType<typeof createDistrict>;try {e=createDistrict(host.current!);engine.current=e;technicians.forEach(t=>e.vehicle(t.id,t.color));}catch {setError(true);return;}
    let frame=0,routeKey='';let previousFollow:string|null=null;
    function render() {
      const p=current.current;
      const selectedJob=p.selection?.type==='job'?jobs.find(j=>j.id===p.selection?.id):undefined;
      const suggested=selectedJob?technicians.find(t=>t.trade===selectedJob.trade&&['Available','Completed'].includes(p.state.technicians[t.id].status)):undefined;
      const routes=technicians.flatMap(t=>{const s=p.state.technicians[t.id];return s.route.length && ['Assigned','En route','Returning','Arrived','Working'].includes(s.status)?[{points:s.route,color:t.color,preview:false}]:[];});
      if(selectedJob&&suggested&&p.preferences.routes&&p.state.jobs[selectedJob.id]==='Unassigned')routes.push({points:findRoute(p.state.technicians[suggested.id].node,selectedJob.node),color:tradeColors[selectedJob.trade],preview:true});
      const key=JSON.stringify(routes);if(key!==routeKey){e.setRoutes(routes);routeKey=key;}
      technicians.forEach(t=>{
        const s=p.state.technicians[t.id];let progress=s.progress;if(p.reduced)progress=Math.floor(progress*12)/12;
        const pt=s.route.length?pointOnRoute(s.route,progress):{...nodes[s.node],angle:0};
        const truck=e.vehicles.get(t.id)!;truck.position.set(pt.x,0,pt.z);truck.rotation.y=pt.angle;
        truck.visible=(p.preferences.trade==='All'||p.preferences.trade===t.trade)&&(!p.preferences.available||s.status==='Available') || p.follow===t.id || (s.jobId===p.selection?.id)||p.selection?.id===t.id;
        const element=labels.current.get(t.id);if(element){position(element,pt.x,26,pt.z);element.style.display=truck.visible?'':'none';}
        if(p.follow===t.id) {
          const target=new THREE.Vector3(pt.x,0,pt.z),delta=target.clone().sub(e.controls.target);e.camera.position.add(delta);e.controls.target.copy(target);e.controls.update();
        }
      });
      if(previousFollow&&!p.follow){e.reset(p.mode);}previousFollow=p.follow;
      jobs.forEach(j=>{const el=labels.current.get(j.id);if(el)position(el,nodes[j.node].x,6,nodes[j.node].z);});
      const d=labels.current.get('depot');if(d)position(d,nodes[depot].x,2,nodes[depot].z);
      e.controls.update();e.renderer.render(e.scene,e.camera);frame=requestAnimationFrame(render);
    }
    function position(element:HTMLElement,x:number,y:number,z:number) {
      const point=new THREE.Vector3(x,y,z).project(e.camera);const w=host.current!.clientWidth,h=host.current!.clientHeight;
      element.style.left=`${(point.x+1)*w/2}px`;element.style.top=`${(1-point.y)*h/2}px`;element.style.visibility=point.z>1||point.z< -1?'hidden':'visible';
    }
    render();return ()=>{cancelAnimationFrame(frame);e.dispose();engine.current=null;};
  },[]);
  useEffect(()=>{engine.current?.reset(props.mode);},[props.mode]);
  const ref=(id:string)=>(el:HTMLButtonElement|null)=>{if(el)labels.current.set(id,el);else labels.current.delete(id);};
  return <div className="map-card">
    <div className="map-canvas" ref={host} aria-label={`${props.mode} interactive map of Goob Demo District. Drag to pan; scroll to zoom.`}/>
    {error&&<div className="map-error"><MapPin size={32}/><h3>Map rendering needs WebGL</h3><p>The dispatch workflow remains available in the jobs and team panels.</p></div>}
    <div className="district-label"><MapPin size={17}/><div><strong>Goob Demo District</strong><span>A little neighborhood. A lot in motion.</span></div></div>
    <div className="map-hint"><MousePointer2 size={12}/> Drag to explore</div>
    {!error&&<div className="map-label-layer">
      {jobs.filter(j=>(j.id!=='willow'||props.state.jobs.oak==='Completed')&&((props.preferences.trade==='All'||j.trade===props.preferences.trade)&&(props.preferences.jobStatus==='All'||props.state.jobs[j.id]===props.preferences.jobStatus)||props.selection?.id===j.id)).map(j=><button ref={ref(j.id)} key={j.id} className={`map-pin ${props.selection?.id===j.id?'selected':''}`} onClick={()=>props.onSelect({type:'job',id:j.id})} aria-label={`Select ${j.address}`}><span className="pin-dot" style={{background:tradeColors[j.trade]}}><TradeIcon trade={j.trade} size={17}/></span><span><strong>{j.address}</strong><small>{props.state.jobs[j.id]==='Completed'?'Completed':j.urgent?'Urgent · Plumbing':j.trade+' visit'}</small></span>{j.urgent&&props.state.jobs[j.id]==='Unassigned'&&<i className="urgent-dot"/>}</button>)}
      {technicians.map(t=><button ref={ref(t.id)} key={t.id} onClick={()=>props.onSelect({type:'tech',id:t.id})} className={`tech-map-label ${props.selection?.id===t.id?'selected':''}`} aria-label={`Select ${t.name}, ${props.state.technicians[t.id].status}`} style={{borderColor:`${t.color}40`}}><span className="mini-avatar" style={{background:t.color}}>{t.initials}</span>{props.preferences.names?<span><strong>{t.name.split(' ')[0]} <span>· {t.trade}</span></strong><small>{props.state.technicians[t.id].status} · {t.truck}</small></span>:<strong>{t.truck}</strong>}</button>)}
      <button className="depot-label" ref={ref('depot')} onClick={()=>props.onSelect({type:'tech',id:'maya'})}><Warehouse size={14}/> Goob Depot</button>
    </div>}
    <button className={`follow-button ${props.follow?'following':''}`} onClick={()=>props.onFollow(props.follow?null:activeId)}><Navigation size={15}/>{props.follow?`Following ${technicians.find(t=>t.id===props.follow)?.name.split(' ')[0]}`:'Follow technician'}</button>
    <div className="map-controls"><button title="Zoom in" aria-label="Zoom in" onClick={()=>{const e=engine.current;if(e){e.camera.zoom=Math.min(3,e.camera.zoom*1.2);e.camera.updateProjectionMatrix();}}}><Plus size={20}/></button><button title="Zoom out" aria-label="Zoom out" onClick={()=>{const e=engine.current;if(e){e.camera.zoom=Math.max(.65,e.camera.zoom/1.2);e.camera.updateProjectionMatrix();}}}><Minus size={20}/></button><button title="Reset map view" aria-label="Reset map view" onClick={()=>{props.onFollow(null);engine.current?.reset(props.mode);}}><LocateFixed size={19}/></button></div>
    <div className="map-legend">{technicians.map(t=><button key={t.id} onClick={()=>props.onSelect({type:'tech',id:t.id})}><TradeIcon trade={t.trade} bubble size={19}/><span><strong>{t.trade}</strong><small>1 technician</small></span></button>)}</div>
    <div className="simulation-label"><span/> Simulation — fictional locations <span className="gps-note">· No live GPS</span></div>
  </div>;
}
