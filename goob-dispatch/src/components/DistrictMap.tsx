import { teamRecords } from '../data';
import { allJobs } from '../schedule';
import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { MapPin, Plus, Minus, LocateFixed, Navigation, Warehouse } from 'lucide-react';
import { createDistrict } from '../mapScene';
import { layoutLabels, type ScreenLabel, type ScreenRect } from '../mapLayout';
import { jobs, technicians, depot, tradeColors } from '../data';
import { nodes, findRoute, pointOnRoute } from '../routing';
import { TradeIcon } from './Icons';
import type { MotionSource } from '../simulation';
import type { Point, Preferences, Selection, Simulation } from '../types';
type Props={state:Simulation;motion:MotionSource;preferences:Preferences;selection:Selection;onSelect:(s:Selection)=>void;mode:'2D'|'3D';follow:string|null;onFollow:(id:string|null)=>void;reduced:boolean};

function context(p:Props) {
  const technicians=teamRecords(p.state);
  const explicit=p.selection?.type==='job'?allJobs(p.state).find(j=>j.id===p.selection?.id):undefined;
  const found=p.selection?.type==='tech'?technicians.find(t=>t.id===p.selection?.id):explicit?(technicians.find(t=>p.state.technicians[t.id]?.jobId===explicit.id)??technicians.find(t=>t.trade===explicit.trade)):technicians.find(t=>t.id===p.follow)??technicians[0];
  const tech=found??technicians[0];
  const state=p.state.technicians[tech.id];
  const job=explicit??allJobs(p.state).find(j=>j.id===state.jobId);
  const destination=state.status==='Returning'?nodes[depot]:job?nodes[job.node]:null;
  const route=state.route.length&&['Assigned','En route','Arrived','Working','Returning'].includes(state.status)?state.route:job&&nodes[state.node]&&nodes[job.node]&&p.state.jobs[job.id]==='Unassigned'&&['Available','Completed'].includes(state.status)?findRoute(state.node,job.node):[];
  return {tech:tech!,job,destination,route};
}

export function DistrictMap(props:Props) {
  const technicians=teamRecords(props.state);
  const host=useRef<HTMLDivElement>(null),card=useRef<HTMLDivElement>(null),engine=useRef<ReturnType<typeof createDistrict>|null>(null),current=useRef(props);
  const hovered=useRef<string|null>(null);
  const labels=useRef(new Map<string,HTMLButtonElement>()),connectors=useRef(new Map<string,SVGPathElement>()),manual=useRef(false),[error,setError]=useState(false);
  current.current=props;const selected=context(props),activeId=selected.tech.id;
  useEffect(()=>{
    let e:ReturnType<typeof createDistrict>;
    try{e=createDistrict(host.current!);engine.current=e;technicians.forEach(t=>e.vehicle(t.id,t.color,t.trade));}catch{setError(true);return;}
    const canvas=e.renderer.domElement;canvas.tabIndex=0;canvas.setAttribute('aria-label','Interactive district. Drag or use arrow keys to pan; scroll to zoom.');
    let routeKey='',framingKey='',previousMode='',metricsKey='',statsTime=0;
    const metrics=new Map<string,{width:number;height:number}>();let reserved:ScreenRect[]=[];
    let pointer:{x:number;y:number;dragged:boolean}|null=null;
    const raycaster=new THREE.Raycaster(),pointerVector=new THREE.Vector2(),projected=new THREE.Vector3();
    const pauseFollow=()=>{manual.current=true;e.cancelCamera();if(current.current.follow)current.current.onFollow(null);};
    const onDown=(event:PointerEvent)=>{pointer={x:event.clientX,y:event.clientY,dragged:false};};
    const onMove=(event:PointerEvent)=>{if(pointer&&Math.hypot(event.clientX-pointer.x,event.clientY-pointer.y)>4){pointer.dragged=true;pauseFollow();}};
    const onUp=(event:PointerEvent)=>{
      if(pointer&&!pointer.dragged){const bounds=canvas.getBoundingClientRect();pointerVector.set((event.clientX-bounds.left)/bounds.width*2-1,1-(event.clientY-bounds.top)/bounds.height*2);raycaster.setFromCamera(pointerVector,e.camera);const hits=raycaster.intersectObjects([...e.vehicles.values()].filter(v=>v.visible),true);const hit=hits[0];if(hit){let parent:THREE.Object3D|null=hit.object;while(parent&&![...e.vehicles.values()].includes(parent as THREE.Group))parent=parent.parent;const entry=[...e.vehicles.entries()].find(([,group])=>group===parent);if(entry)current.current.onSelect({type:'tech',id:entry[0]});}}
      pointer=null;
    };
    const onWheel=()=>pauseFollow(),onKey=(event:KeyboardEvent)=>{if(event.key.startsWith('Arrow')){event.preventDefault();pauseFollow();}};
    canvas.addEventListener('pointerdown',onDown);canvas.addEventListener('pointermove',onMove);canvas.addEventListener('pointerup',onUp);canvas.addEventListener('wheel',onWheel,{passive:true});canvas.addEventListener('keydown',onKey);
    function project(point:Point,y=8){projected.set(point.x,y,point.z).project(e.camera);return{x:(projected.x+1)*host.current!.clientWidth/2,y:(1-projected.y)*host.current!.clientHeight/2};}
    function render(state:Simulation,dt:number,now:number){
      // DOM removal can precede passive subscription cleanup by one frame.
      if(!host.current||!card.current||!engine.current)return;
      const p={...current.current,state},c=context(p),w=host.current!.clientWidth,h=host.current!.clientHeight;
      if(previousMode!==p.mode){e.setMode(p.mode);previousMode=p.mode;framingKey='';}
      const routes=technicians.flatMap(t=>{const s=p.state.technicians[t.id];return s.route.length&&['Assigned','En route','Arrived','Working','Returning'].includes(s.status)?[{points:s.route,color:p.selection&&c.tech.id===t.id?t.color:'#9b939f',preview:false}]:[];});
      if(c.job&&p.preferences.routes&&p.state.jobs[c.job.id]==='Unassigned'&&c.route.length)routes.push({points:c.route,color:c.tech.color,preview:true});
      const nextRouteKey=JSON.stringify(routes);if(nextRouteKey!==routeKey){e.setRoutes(routes);routeKey=nextRouteKey;}
      const points=new Map<string,Point>();
      technicians.forEach(t=>{
        const s=p.state.technicians[t.id],visualProgress=s.replay?.progress??s.progress,progress=p.reduced?Math.floor(visualProgress*12)/12:visualProgress;
        const pt=s.route.length?pointOnRoute(s.route,progress):{...nodes[s.node],angle:0};points.set(t.id,pt);
        const truck=e.vehicles.get(t.id)!;truck.position.set(pt.x,0,pt.z);truck.rotation.y+=Math.atan2(Math.sin(pt.angle-truck.rotation.y),Math.cos(pt.angle-truck.rotation.y))*(p.reduced?1:1-Math.exp(-dt*9));
        truck.visible=(p.preferences.trade==='All'||p.preferences.trade===t.trade)&&(!p.preferences.available||['Available','Completed'].includes(s.status))||p.follow===t.id||p.selection?.id===t.id||!!p.selection&&c.tech.id===t.id;
      });
      e.highlight(p.selection||p.follow?c.tech.id:null,c.destination,c.tech.color);
      const nextFramingKey=`${p.mode}/${p.selection?.type}/${p.selection?.id}/${c.route.map(pt=>`${pt.x},${pt.z}`).join(';')}/${w}/${h}`;
      if(nextFramingKey!==framingKey&&!p.follow&&!manual.current){
        // Include all important visible markers as context, as well as every
        // route turn. This prevents padding from clipping a technician or pin.
        const focus=[...c.route,...[...points.entries()].filter(([id])=>e.vehicles.get(id)!.visible).map(([,point])=>point),...allJobs(p.state).filter(j=>labels.current.has(j.id)).map(j=>nodes[j.node])];
        if(c.destination)focus.push(c.destination);focus.push(nodes[depot]);
        e.framePoints(focus,{left:w<500?34:85,right:w<500?48:90,top:42,bottom:64},framingKey===''||p.reduced);framingKey=nextFramingKey;
      }
      if(p.follow&&!manual.current)e.followPoint(points.get(p.follow)!,dt,p.reduced);else e.stepCamera(dt,p.reduced);
      e.controls.update();e.camera.updateMatrixWorld();
      const nextMetricsKey=`${w}/${h}/${JSON.stringify(p.preferences)}/${p.selection?.id}/${p.follow}/${hovered.current}/${Object.values(p.state.technicians).map(t=>t.status).join('/')}`;
      if(metricsKey!==nextMetricsKey){
        metrics.clear();labels.current.forEach((el,id)=>metrics.set(id,{width:el.offsetWidth,height:el.offsetHeight}));
        const bounds=card.current!.getBoundingClientRect();reserved=Array.from(card.current!.querySelectorAll<HTMLElement>('[data-map-obstacle]')).map(el=>{const r=el.getBoundingClientRect();return{x:r.left-bounds.left-5,y:r.top-bounds.top-5,width:r.width+10,height:r.height+10};});metricsKey=nextMetricsKey;
      }
      const inputs:ScreenLabel[]=[];
      labels.current.forEach((element,id)=>{
        const isTech=points.has(id),point=isTech?points.get(id)!:id==='depot'?nodes[depot]:nodes[allJobs(p.state).find(j=>j.id===id)!.node];
        const visible=!isTech||e.vehicles.get(id)!.visible;element.style.visibility='hidden';connectors.current.get(id)?.setAttribute('visibility','hidden');if(!visible)return;
        const size=metrics.get(id)!;const anchor=project(point,isTech?22:7);
        element.dataset.anchorX=anchor.x.toFixed(2);element.dataset.anchorY=anchor.y.toFixed(2);
        const important=(isTech&&c.tech.id===id&&!!p.selection)||p.selection?.id===id||(c.destination===nodes[depot]&&id==='depot');
        inputs.push({id,anchor,width:size.width,height:size.height,above:isTech,priority:important?20:isTech?10:id==='depot'?1:5});
      });
      const placements=layoutLabels(inputs,w,h,reserved);
      placements.forEach(label=>{
        const element=labels.current.get(label.id)!;element.style.left=`${label.x}px`;element.style.top=`${label.y}px`;element.style.visibility='visible';
        const line=connectors.current.get(label.id);if(line){const x=Math.max(4,Math.min(w-4,label.anchor.x)),y=Math.max(4,Math.min(h-4,label.anchor.y)),endX=Math.max(label.x+8,Math.min(label.x+label.width-8,x)),endY=Math.max(label.y+4,Math.min(label.y+label.height-4,y));line.setAttribute('d',`M${x},${y} L${endX},${endY}`);line.setAttribute('visibility','visible');}
      });
      e.renderer.render(e.scene,e.camera);if(now-statsTime>1000){host.current!.dataset.drawCalls=String(e.renderer.info.render.calls);statsTime=now;}

    }
    const unsubscribe=props.motion.subscribe(render);
    return()=>{unsubscribe();canvas.removeEventListener('pointerdown',onDown);canvas.removeEventListener('pointermove',onMove);canvas.removeEventListener('pointerup',onUp);canvas.removeEventListener('wheel',onWheel);canvas.removeEventListener('keydown',onKey);e.dispose();engine.current=null;};
  },[]);
  useEffect(()=>{manual.current=false;if(props.follow&&props.follow!==activeId)props.onFollow(activeId);},[props.selection?.id]);
  const ref=(id:string)=>(element:HTMLButtonElement|null)=>{if(element)labels.current.set(id,element);else labels.current.delete(id);};
  const visibleJobs=allJobs(props.state).filter(j=>!!nodes[j.node]&&(j.id!=='willow'||props.state.jobs.oak==='Completed')&&((props.preferences.trade==='All'||j.trade===props.preferences.trade)&&(props.preferences.jobStatus==='All'||props.state.jobs[j.id]===props.preferences.jobStatus)||props.selection?.id===j.id));
  function manualZoom(factor:number){manual.current=true;props.onFollow(null);const e=engine.current;if(e){e.cancelCamera();e.camera.zoom=Math.max(.45,Math.min(3,e.camera.zoom*factor));e.camera.updateProjectionMatrix();}}
  return <div className="map-card" ref={card}>
    <div className="map-canvas" ref={host} aria-label={`${props.mode} interactive map of Goob Demo District. Drag to pan; scroll to zoom.`}/>
    {error&&<div className="map-error"><MapPin size={32}/><h3>Map rendering needs WebGL</h3><p>The dispatch workflow remains available in the jobs and team panels.</p></div>}
    {!error&&<><svg className="label-connectors" aria-hidden="true">{[...technicians.map(t=>t.id),...visibleJobs.map(j=>j.id),'depot'].map(id=><path key={id} ref={el=>{if(el)connectors.current.set(id,el);else connectors.current.delete(id);}} stroke={technicians.find(t=>t.id===id)?.color??'#817b71'}/>)}</svg><div className="map-label-layer">
      {visibleJobs.map(j=>{const expanded=props.selection?.id===j.id||props.selection?.type==='tech'&&selected.job?.id===j.id;return <button ref={ref(j.id)} key={j.id} data-map-marker={j.id} onMouseEnter={()=>{hovered.current=j.id;}} onMouseLeave={()=>{hovered.current=null;}} title={`${j.address} · ${j.trade}`} className={`map-pin ${expanded?'selected expanded':'compact'}`} onClick={()=>props.onSelect({type:'job',id:j.id})} aria-label={`Select ${j.address}`}><span className="pin-dot" style={{background:tradeColors[j.trade]}}><TradeIcon trade={j.trade} size={15}/></span><span><strong>{j.address}</strong><small>{j.trade}{expanded?` · ${props.state.jobs[j.id]==='Unassigned'&&j.urgent?'Urgent':props.state.jobs[j.id]}`:''}</small></span>{j.urgent&&props.state.jobs[j.id]==='Unassigned'&&<i className="urgent-dot"/>}</button>;})}
      {technicians.map(t=>{const expanded=(!!props.selection&&activeId===t.id)||props.follow===t.id;return <button ref={ref(t.id)} key={t.id} data-map-marker={t.id} onMouseEnter={()=>{hovered.current=t.id;}} onMouseLeave={()=>{hovered.current=null;}} title={`${t.name} · ${t.trade}`} onClick={()=>props.onSelect({type:'tech',id:t.id})} className={`tech-map-label ${expanded?'selected expanded':'compact'}`} aria-label={`Select ${t.name}, ${props.state.technicians[t.id].status}`} style={{borderColor:`${t.color}${expanded?'99':'40'}`}}><TradeIcon trade={t.trade} bubble size={16}/><span><strong>{props.preferences.names?(expanded?t.name:t.name.split(' ')[0]):`Truck ${t.truck}`}<span> · {t.trade}</span></strong>{expanded&&<small>{props.state.technicians[t.id].status} · Truck {t.truck}</small>}</span></button>;})}
      <button className="depot-label" data-map-marker="depot" ref={ref('depot')} onClick={()=>props.onSelect({type:'tech',id:technicians[0].id})}><Warehouse size={14}/> Goob Depot</button>
    </div></>}
    <div className="map-controls" data-map-obstacle><button title="Zoom in" aria-label="Zoom in" onClick={()=>manualZoom(1.2)}><Plus size={20}/></button><button title="Zoom out" aria-label="Zoom out" onClick={()=>manualZoom(1/1.2)}><Minus size={20}/></button><button title="Reset map view" aria-label="Reset map view" onClick={()=>{manual.current=false;props.onFollow(null);engine.current?.reset(props.mode);}}><LocateFixed size={19}/></button><button className={props.follow?'following':''} aria-label={props.follow?'Stop following technician':'Follow technician'} aria-pressed={!!props.follow} title={props.follow?'Stop following technician':'Follow technician'} onClick={()=>{manual.current=false;props.onFollow(props.follow?null:activeId);}}><Navigation size={18}/></button></div>
  </div>;
}
