import { teamRecords } from '../data';
import { allJobs } from '../schedule';
import { useEffect, useRef, useState } from 'react';
import { importLibrary, setOptions } from '@googlemaps/js-api-loader';
import { Navigation, Plus, Minus, LocateFixed, Route } from 'lucide-react';
import { depot, jobs, technicians, tradeColors } from '../data';
import { validMapPoint, columbia, geoPosition, meters, realStops, type GeoPoint } from '../integrations/geography';
import { layoutLabels, overlaps, type ScreenRect } from '../mapLayout';
import type { MotionSource } from '../simulation';
import type { IntegrationConfig } from '../integrations/api';
import type { Preferences, Selection, Simulation, Trade } from '../types';
type Props={state:Simulation;motion:MotionSource;preferences:Preferences;selection:Selection;onSelect:(s:Selection)=>void;mode:'2D'|'3D';follow:string|null;onFollow:(id:string|null)=>void;reduced:boolean;config:IntegrationConfig;on2DFallback:(message:string)=>void;onMapError:(message:string)=>void};
type Marker2={point:GeoPoint;visible:boolean;selected:boolean;button:HTMLButtonElement;tooltip:HTMLDivElement;heading:number;tech:boolean};
type Marker3={marker:google.maps.maps3d.Marker3DInteractiveElement;pin:google.maps.marker.PinElement};
const definitionsFor=(state:Simulation)=>[...teamRecords(state).map(t=>({id:t.id,tech:true,trade:t.trade,name:t.name,node:t.start})),...allJobs(state).filter(j=>!!realStops[j.node]).map(j=>({id:j.id,tech:false,trade:j.trade,name:j.address,node:j.node})),{id:'custom-destination',tech:false,trade:'Plumbing' as Trade,name:'New visit',node:'3-2'},{id:'depot',tech:false,trade:'HVAC' as Trade,name:'Goob Depot',node:depot}];
// Inline styling is supported on raster maps without a Map ID. Vector/3D
// maps use the published cloud style associated with the configured Map ID.
const quietStreets:google.maps.MapTypeStyle[]=[
  {featureType:'poi.business',elementType:'labels',stylers:[{visibility:'off'}]},
  {featureType:'poi.medical',elementType:'labels',stylers:[{visibility:'off'}]},
  {featureType:'transit',elementType:'labels',stylers:[{visibility:'off'}]},
  {featureType:'landscape',elementType:'geometry',stylers:[{color:'#efeee5'}]},
  {featureType:'road',elementType:'geometry',stylers:[{color:'#fffdf7'}]},
  {featureType:'road',elementType:'labels.text.fill',stylers:[{color:'#63545f'}]},
  {featureType:'poi.park',elementType:'geometry',stylers:[{color:'#dbe6ce'}]},
  {featureType:'water',elementType:'geometry',stylers:[{color:'#bad8e4'}]},
];
const vehicleGlyph='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28"><path d="M3 7h13v13H3zM16 11h5l4 5v4h-9z" fill="white"/><path d="M18 12h3l2 4h-5z" fill="#483349"/><circle cx="8" cy="21" r="3" fill="#483349" stroke="white"/><circle cx="21" cy="21" r="3" fill="#483349" stroke="white"/></svg>');
let configuredKey='';
function selectedTech(p:Props){const technicians=teamRecords(p.state);return p.selection?.type==='tech'?(technicians.find(t=>t.id===p.selection!.id)??technicians[0]):technicians.find(t=>p.state.technicians[t.id]?.jobId===p.selection?.id)??technicians.find(t=>t.trade===allJobs(p.state).find(j=>j.id===p.selection?.id)?.trade)??technicians[0];}
function position(p:Props,id:string){const t=p.state.technicians[id],progress=t.replay?.progress??t.progress;return t.driving?geoPosition(t.driving.coordinates,p.reduced?Math.floor(progress*15)/15:progress):{...realStops[t.node],heading:0};}
function tradeIcon(trade:Trade){return new URL(`/trade-${trade.toLowerCase()}.svg`,location.origin).href;}
export function GoogleDispatchMap(props:Props){
 const technicians=teamRecords(props.state),definitions=definitionsFor(props.state);
 const definitionKey=definitions.map(d=>d.id+'/'+d.node).join('|');
  const host2=useRef<HTMLDivElement>(null),host3=useRef<HTMLDivElement>(null),map2=useRef<google.maps.Map|null>(null),map3=useRef<google.maps.maps3d.Map3DElement|null>(null),overlay=useRef<google.maps.OverlayView|null>(null),current=useRef(props);current.current=props;
  const markers2=useRef(new Map<string,Marker2>()),markers3=useRef(new Map<string,Marker3>()),lines2=useRef<google.maps.Polyline[]>([]),lines3=useRef<google.maps.maps3d.Polyline3DElement[]>([]);
  const [epoch,setEpoch]=useState(0),[loaded2,setLoaded2]=useState(false),[loaded3,setLoaded3]=useState(false),[loading,setLoading]=useState('Loading Google Maps…');
  const selectedKey=useRef(''),routeKey=useRef(''),fittedKey=useRef(''),manual=useRef(false),threeReady=useRef(false),hovered=useRef<string|null>(null),fitRef=useRef<(all?:boolean)=>void>(()=>{});
  function choose(id:string,tech:boolean){if(id==='custom-destination'){const selected=current.current.selection;if(selected?.type==='job')current.current.onSelect(selected);return;}current.current.onSelect({type:tech||id==='depot'?'tech':'job',id:id==='depot'?technicians[0].id:id});}
  function build2(){
    const layer=document.createElement('div');layer.className='google-pin-layer';
    for(const d of definitions){
      const button=document.createElement('button');button.className=`google-pin ${d.tech?'vehicle-pin':'visit-pin'}`;button.title=`${d.name} · ${d.trade}`;button.setAttribute('aria-label',`Select ${d.name}, ${d.trade}`);button.dataset.mapMarker=d.id;button.style.setProperty('--pin-color',tradeColors[d.trade]);
      const icon=document.createElement('img');icon.src=tradeIcon(d.trade);icon.alt='';const direction=document.createElement('i');direction.textContent='➤';button.append(icon);if(d.tech)button.append(direction);
      const tooltip=document.createElement('div');tooltip.className='google-pin-details';tooltip.setAttribute('aria-hidden','true');button.addEventListener('click',()=>choose(d.id,d.tech));
      const hover=(show:boolean)=>{hovered.current=show?d.id:null;overlay.current?.draw();};button.addEventListener('mouseenter',()=>hover(true));button.addEventListener('mouseleave',()=>hover(false));button.addEventListener('focus',()=>hover(true));button.addEventListener('blur',()=>hover(false));
      google.maps.OverlayView.preventMapHitsAndGesturesFrom(button);layer.append(button,tooltip);markers2.current.set(d.id,{point:realStops[d.node],button,tooltip,visible:true,selected:false,heading:0,tech:d.tech});
    }
    class Pins extends google.maps.OverlayView{
      onAdd(){this.getPanes()!.overlayMouseTarget.append(layer);}
      onRemove(){layer.remove();}
      draw(){
        const projection=this.getProjection();if(!projection||!map2.current||!host2.current)return;
        const w=host2.current!.clientWidth,h=host2.current!.clientHeight,origin=new google.maps.LatLng(columbia),div=projection.fromLatLngToDivPixel(origin)!,container=projection.fromLatLngToContainerPixel(origin)!;
        layer.style.left=`${div.x-container.x}px`;layer.style.top=`${div.y-container.y}px`;layer.style.width=`${w}px`;layer.style.height=`${h}px`;
        if(!w||!h)return;
        const occupied:ScreenRect[]=[],details:{id:string;anchor:{x:number;y:number};width:number;height:number;priority:number;above:boolean}[]=[];
        [...markers2.current].sort((a,b)=>Number(b[1].selected)-Number(a[1].selected)).forEach(([id,m])=>{
          if(!validMapPoint(m.point)){m.button.style.display='none';m.tooltip.style.visibility='hidden';return;}const point=projection.fromLatLngToContainerPixel(new google.maps.LatLng(m.point))!,size=m.tech?38:32,rect={x:point.x-size/2,y:point.y-size/2,width:size,height:size};
          const visible=m.visible&&(m.selected||!occupied.some(r=>overlaps(r,rect,3)));
          m.button.style.display=visible?'grid':'none';m.tooltip.style.visibility='hidden';if(!visible)return;occupied.push(rect);
          m.button.style.left=`${point.x}px`;m.button.style.top=`${point.y}px`;m.button.style.zIndex=m.selected?'20':'10';
          if(id===hovered.current||current.current.selection?.id===id||id==='custom-destination'&&m.selected||m.selected&&m.tech&&!markers2.current.get(current.current.selection?.id??'')?.visible){m.tooltip.style.display='block';details.push({id,anchor:point,width:m.tooltip.offsetWidth,height:m.tooltip.offsetHeight,priority:m.selected?20:10,above:true});}
        });
        layoutLabels(details,w,h,[{x:w-62,y:h-250,width:62,height:225},{x:0,y:h-32,width:w,height:32}]).forEach(r=>{const el=markers2.current.get(r.id)!.tooltip;el.style.left=`${r.x}px`;el.style.top=`${r.y}px`;el.style.visibility='visible';});
      }
    }
    overlay.current=new Pins();overlay.current.setMap(map2.current);
  }
  async function build3(){
    const {Marker3DInteractiveElement}=await importLibrary('maps3d'),{PinElement}=await importLibrary('marker');if(!map3.current)return;
    for(const d of definitions){if(!validMapPoint(realStops[d.node]))continue;const marker=new Marker3DInteractiveElement({position:{...realStops[d.node],altitude:d.tech?7:2},altitudeMode:'RELATIVE_TO_GROUND',title:`Select ${d.name}, ${d.trade}`,drawsWhenOccluded:true,sizePreserved:true});
      const pin=new PinElement({background:tradeColors[d.trade],borderColor:'#fffdf5',glyphSrc:d.tech?vehicleGlyph:tradeIcon(d.trade),scale:1});marker.append(pin);marker.addEventListener('gmp-click',()=>choose(d.id,d.tech));
      marker.addEventListener('mouseenter',()=>{if(!current.current.selection)marker.label=`${d.name} · ${d.trade}`;});marker.addEventListener('mouseleave',()=>{if(current.current.selection?.id!==d.id)marker.label=null;});map3.current!.append(marker);markers3.current.set(d.id,{marker,pin});}
  }
  function pointsForFit(all=false):GeoPoint[]{const p={...current.current,state:current.current.motion.getState()},t=selectedTech(p),ts=p.state.technicians[t.id],job=allJobs(p.state).find(j=>j.id===(p.selection?.type==='job'?p.selection.id:ts.jobId));const points:GeoPoint[]=all||!p.selection?Object.values(realStops):[];if(ts.driving)points.push(...ts.driving.coordinates);else if(p.state.preview?.route)points.push(...p.state.preview.route.coordinates);points.push(position(p,t.id));if(ts.status==='Returning')points.push(realStops[depot]);else if(job&&realStops[job.node])points.push(realStops[job.node]);if(points.length===1)points.push(...Object.values(realStops));return points.filter(validMapPoint);}
  function fit(all=false){
    const p=current.current,points=pointsForFit(all);if(!points.length||!host2.current||!host3.current)return;const box=new google.maps.LatLngBounds();points.forEach(point=>box.extend(point));
    if(p.mode==='2D'||!map3.current){map2.current?.fitBounds(box,{top:62,left:50,right:85,bottom:65});return;}
    const center=box.getCenter().toJSON(),radius=Math.max(...points.map(point=>meters(center,point))),w=host3.current!.clientWidth,h=host3.current!.clientHeight,v=Math.atan(Math.tan(17.5*Math.PI/180)*Math.max(.25,(h-127)/h)),horizontal=Math.atan(Math.tan(17.5*Math.PI/180)*w/h*Math.max(.25,(w-135)/w));
    map3.current.stopCameraAnimation();map3.current.flyCameraTo({endCamera:{center:{...center,altitude:0},altitudeMode:'RELATIVE_TO_GROUND',range:Math.max(450,1.2*radius/Math.sin(Math.min(v,horizontal))),tilt:58,heading:0},durationMillis:p.reduced?0:450});
  }fitRef.current=fit;
  useEffect(()=>{
    setLoaded2(false);setLoaded3(false);let disposed=false;const original=(window as Window & {gm_authFailure?:()=>void}).gm_authFailure;
    (window as Window & {gm_authFailure?:()=>void}).gm_authFailure=()=>{if(!disposed)current.current.onMapError('Google Maps could not authorize this site. Check the browser key, referrer restrictions, API enablement, and billing.');};
    if(!configuredKey){setOptions({key:props.config.browserKey,v:'weekly',region:'US',language:'en',authReferrerPolicy:'origin'});configuredKey=props.config.browserKey;}
    const timeout=window.setTimeout(()=>{if(!disposed&&!map2.current)current.current.onMapError('Google Maps did not load. Check connectivity and browser-key configuration.');},20000);
    importLibrary('maps').then(({Map,RenderingType})=>{if(disposed)return;map2.current=new Map(host2.current!,{center:columbia,zoom:16,tilt:0,heading:0,...(props.config.mapId?{mapId:props.config.mapId,renderingType:RenderingType.VECTOR}:{renderingType:RenderingType.RASTER,styles:quietStreets}),disableDefaultUI:true,gestureHandling:'greedy',clickableIcons:false});build2();clearTimeout(timeout);setLoaded2(true);setLoading('');setEpoch(e=>e+1);fitRef.current();}).catch(()=>{if(!disposed)current.current.onMapError('Google Maps could not load. Check network access and the restricted browser key.');});
    return()=>{disposed=true;clearTimeout(timeout);(window as Window & {gm_authFailure?:()=>void}).gm_authFailure=original;overlay.current?.setMap(null);overlay.current=null;markers2.current.clear();lines2.current.forEach(l=>l.setMap(null));if(map2.current)google.maps.event.clearInstanceListeners(map2.current);map2.current=null;markers3.current.forEach(({marker})=>marker.remove());markers3.current.clear();lines3.current.forEach(l=>l.remove());map3.current?.stopCameraAnimation();map3.current?.remove();map3.current=null;host2.current?.replaceChildren();};
  },[definitionKey]);
  useEffect(()=>{
    if(props.mode!=='3D'||!loaded2||map3.current)return;
    let canceled=false,timer=0;setLoading('Loading photorealistic 3D…');
    const fallback=()=>{if(canceled)return;clearTimeout(timer);map3.current?.remove();map3.current=null;markers3.current.clear();threeReady.current=false;setLoaded3(false);setLoading('');current.current.on2DFallback('Photorealistic 3D is unavailable on this device, browser, or map area. Using Google 2D; dispatch progress is preserved.');};
    importLibrary('maps3d').then(async({Map3DElement})=>{
      if(canceled)return;const map=new Map3DElement({center:{...columbia,altitude:100},range:1800,tilt:58,heading:0,mode:'HYBRID',...(current.current.config.mapId?{mapId:current.current.config.mapId}:{}),defaultUIHidden:true,gestureHandling:'GREEDY'});map3.current=map;host3.current!.append(map);timer=window.setTimeout(fallback,20000);
      const rendered=()=>{if(canceled||map3.current!==map)return;clearTimeout(timer);threeReady.current=true;setLoaded3(true);setLoading('');};
      map.addEventListener('gmp-error',()=>{if(map3.current===map){clearTimeout(timer);map.stopCameraAnimation();map.remove();map3.current=null;markers3.current.clear();threeReady.current=false;setLoaded3(false);setLoading('');current.current.on2DFallback('Photorealistic 3D failed to render. Using Google 2D with the same dispatch progress.');}});
      map.addEventListener('gmp-animationend',rendered);map.addEventListener('gmp-steadychange',event=>{if(event.isSteady)rendered();});await build3();if(canceled)return;setEpoch(e=>e+1);if(!manual.current)fitRef.current();
    }).catch(fallback);
    return()=>{canceled=true;clearTimeout(timer);if(map3.current&&!threeReady.current){map3.current.remove();map3.current=null;markers3.current.clear();setLoaded3(false);}if(current.current.mode==='2D')setLoading('');};
  },[props.mode,loaded2]);
  useEffect(()=>{
    if(!loaded2)return;const p=props,active=selectedTech(p),activeState=p.state.technicians[active.id],job=allJobs(p.state).find(j=>j.id===(p.selection?.type==='job'?p.selection.id:activeState.jobId)),destination=activeState.status==='Returning'?'depot':job?.id;
    const destinationPoint=destination==='depot'?realStops[depot]:job?realStops[job.node]:undefined,colocated=!!destinationPoint&&meters(position(p,active.id),destinationPoint)<12;
    for(const base of definitions){const custom=base.id==='custom-destination',d=custom&&job&&!definitions.some(d=>d.id===job.id)?{...base,id:base.id,trade:job.trade,name:job.address,node:job.node}:base;const ts=d.tech?p.state.technicians[d.id]:undefined,selected=(custom&&!!job&&!definitions.some(d=>d.id===job.id))||(p.selection?.id===d.id&&activeState.status!=='Returning')||!!p.selection&&(d.id===active.id||d.id===destination);
      let visible=(!custom||!!job&&!definitions.some(d=>d.id===job.id))&&(p.preferences.trade==='All'||p.preferences.trade===d.trade)&&(!ts||!p.preferences.available||['Available','Completed'].includes(ts.status))&&(!jobs.some(j=>j.id===d.id)||p.preferences.jobStatus==='All'||p.state.jobs[d.id]===p.preferences.jobStatus)&&(d.id!=='willow'||p.state.jobs.oak==='Completed')||selected||p.follow===d.id||d.id==='depot';if(colocated&&(d.id===destination||custom))visible=false;
      const point=ts?position(p,d.id):realStops[d.node];if(!validMapPoint(point)){const two=markers2.current.get(d.id);if(two){two.visible=false;two.button.style.display='none';two.tooltip.style.visibility='hidden';}markers3.current.get(d.id)?.marker.remove();continue;}const label=d.id==='depot'?'Goob Depot':`${ts&&!p.preferences.names?`Truck ${technicians.find(t=>t.id===d.id)!.truck}`:d.name} · ${d.trade}${ts?` · ${ts.status}`:''}${d.id===active.id&&colocated?` · ${destination==='depot'?'Goob Depot':job?.address}`:''}`;
      const two=markers2.current.get(d.id);if(two){two.button.style.setProperty('--pin-color',tradeColors[d.trade]);two.button.querySelector('img')!.src=tradeIcon(d.trade);two.point=point;two.button.dataset.lat=String(point.lat);two.button.dataset.lng=String(point.lng);two.visible=visible;two.selected=selected;two.button.classList.toggle('selected',selected);two.button.setAttribute('aria-pressed',String(selected));two.tooltip.textContent=label;const direction=two.button.querySelector('i');if(direction)direction.style.display=ts?'block':'none';}
      const three=markers3.current.get(d.id);if(three){three.pin.background=tradeColors[d.trade];if(!ts)three.pin.glyphSrc=tradeIcon(d.trade);three.marker.position={...point,altitude:ts?7:2};three.marker.label=custom&&selected||p.selection?.id===d.id||colocated&&d.id===active.id?label:null;three.marker.zIndex=selected?100:ts?20:10;three.marker.collisionBehavior=selected?'REQUIRED_AND_HIDES_OPTIONAL':'OPTIONAL_AND_HIDES_LOWER_PRIORITY';three.pin.scale=selected?1.2:ts?1.05:.9;if(visible){if(!three.marker.parentNode)map3.current?.append(three.marker);}else three.marker.remove();}
    }overlay.current?.draw();
    const routes=technicians.flatMap(t=>{const ts=p.state.technicians[t.id];return ts.driving&&['Assigned','En route','Arrived','Working','Returning'].includes(ts.status)?[{id:t.id,route:ts.driving,color:t.color,selected:!!p.selection&&t.id===active.id}]:[];});if(p.preferences.routes&&p.state.preview?.route)routes.push({id:'preview',route:p.state.preview.route,color:active.color,selected:true});
    const key=`${epoch}/${JSON.stringify(routes.map(r=>[r.id,r.route.coordinates,r.selected]))}`;
    if(routeKey.current!==key){routeKey.current=key;lines2.current.forEach(l=>l.setMap(null));lines2.current=[];lines3.current.forEach(l=>l.remove());lines3.current=[];
      routes.forEach(r=>{const color=r.selected?r.color:'#9b939f';lines2.current.push(new google.maps.Polyline({map:map2.current,path:r.route.coordinates,strokeColor:r.selected?'#fffdf6':'#ddd8dd',strokeOpacity:r.selected ? .98 : .65,strokeWeight:r.selected?10:6,zIndex:r.selected?8:4}),new google.maps.Polyline({map:map2.current,path:r.route.coordinates,strokeColor:color,strokeOpacity:r.selected?1:.65,strokeWeight:r.selected?6:3,zIndex:r.selected?9:5}));if(map3.current){const line=new google.maps.maps3d.Polyline3DElement({path:r.route.coordinates,altitudeMode:'CLAMP_TO_GROUND',strokeColor:color,strokeWidth:r.selected?8:4,outerColor:r.selected?'#fffdf6':'#ddd8dd',outerWidth:.4,drawsOccludedSegments:true});map3.current.append(line);lines3.current.push(line);}});
    }
    const selectionKey=`${p.selection?.type}/${p.selection?.id}`;if(selectedKey.current!==selectionKey){selectedKey.current=selectionKey;manual.current=false;}const focusKey=`${epoch}/${p.mode}/${p.selection?.type}/${p.selection?.id}/${p.state.preview?.key}/${p.state.preview?.route?.distanceMeters}/${destination}/${activeState.driving?.distanceMeters}`;if(fittedKey.current!==focusKey){fittedKey.current=focusKey;if(!p.follow&&!manual.current)fitRef.current();}
  },[props.state,props.selection,props.preferences,props.mode,props.follow,epoch,loaded2]);
  useEffect(()=>{manual.current=false;if(props.follow&&props.follow!==selectedTech(props).id)props.onFollow(selectedTech(props).id);},[props.selection?.id]);
  useEffect(()=>{
    const hosts=[host2.current!,host3.current!];let pointer:{x:number;y:number}|null=null;
    const cancel=()=>{manual.current=true;map3.current?.stopCameraAnimation();if(current.current.follow)current.current.onFollow(null);};
    const down=(event:PointerEvent)=>{pointer={x:event.clientX,y:event.clientY};},move=(event:PointerEvent)=>{if(pointer&&Math.hypot(pointer.x-event.clientX,pointer.y-event.clientY)>4)cancel();},up=()=>{pointer=null;},key=(event:KeyboardEvent)=>{if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','+','-','PageUp','PageDown'].includes(event.key))cancel();};
    hosts.forEach(host=>{host.addEventListener('pointerdown',down,true);host.addEventListener('pointermove',move,true);host.addEventListener('pointerup',up,true);host.addEventListener('wheel',cancel,{capture:true,passive:true});host.addEventListener('keydown',key,true);});return()=>hosts.forEach(host=>{host.removeEventListener('pointerdown',down,true);host.removeEventListener('pointermove',move,true);host.removeEventListener('pointerup',up,true);host.removeEventListener('wheel',cancel,true);host.removeEventListener('keydown',key,true);});
  },[]);
  useEffect(()=>{const observer=new ResizeObserver(()=>{if(!current.current.follow&&!manual.current&&map2.current)fitRef.current();});observer.observe(host2.current!);return()=>observer.disconnect();},[]);
  useEffect(()=>{
    if(!loaded2)return;return props.motion.subscribe((state,dt)=>{
      const p={...current.current,state},factor=p.reduced?1:1-Math.exp(-dt*9);
      if(!p.follow&&!Object.values(state.technicians).some(t=>t.running||t.replay?.running))return;
      for(const t of technicians){const point=position(p,t.id);if(!validMapPoint(point))continue;const two=markers2.current.get(t.id);if(two){two.point=point;two.button.dataset.lat=String(point.lat);two.button.dataset.lng=String(point.lng);two.heading+=(((point.heading-two.heading)%360+540)%360-180)*factor;two.button.querySelector('i')!.style.transform=`rotate(${two.heading-90}deg)`;}const three=markers3.current.get(t.id);if(three)three.marker.position={...point,altitude:7};}if(p.mode==='2D')overlay.current?.draw();
      if(!p.follow||manual.current)return;const target=position(p,p.follow);if(!validMapPoint(target))return;const ease=p.reduced?1:1-Math.exp(-dt*5);
      if(p.mode==='3D'&&map3.current){const c=map3.current.center??{...target,altitude:100};map3.current.center={lat:c.lat+(target.lat-c.lat)*ease,lng:c.lng+(target.lng-c.lng)*ease,altitude:c.altitude};}else{const c=map2.current?.getCenter();if(c)map2.current?.moveCamera({center:{lat:c.lat()+(target.lat-c.lat())*ease,lng:c.lng()+(target.lng-c.lng())*ease},tilt:0,heading:0});}
    });
  },[props.motion,loaded2]);
  useEffect(()=>{if(props.follow){manual.current=false;map3.current?.stopCameraAnimation();}},[props.follow]);
  function zoom(factor:number){manual.current=true;props.onFollow(null);if(props.mode==='3D'&&map3.current){map3.current.stopCameraAnimation();map3.current.range=Math.max(150,Math.min(5000,(map3.current.range??1800)*factor));}else if(map2.current)map2.current.setZoom((map2.current.getZoom()??16)+(factor<1?1:-1));}
  return <div className="map-card google-map-card"><div ref={host2} className={`google-map-host ${props.mode==='3D'&&loaded3?'map-hidden':''}`} aria-label="Google 2D map of Columbia"/><div ref={host3} className={`google-map-host ${props.mode==='2D'?'map-hidden':''}`} aria-label="Photorealistic Google 3D map of Columbia"/>{loading&&<div className="google-map-loading" role="status">{loading}</div>}
    <div className="map-controls"><button aria-label="Zoom in" title="Zoom in" onClick={()=>zoom(.8)}><Plus size={19}/></button><button aria-label="Zoom out" title="Zoom out" onClick={()=>zoom(1.25)}><Minus size={19}/></button><button aria-label="Fit route" title="Fit selected route" onClick={()=>{manual.current=false;props.onFollow(null);fitRef.current();}}><Route size={18}/></button><button aria-label="Reset map view" title="Reset map view" onClick={()=>{manual.current=false;props.onFollow(null);fitRef.current(true);}}><LocateFixed size={19}/></button><button className={props.follow?'following':''} aria-label={props.follow?'Stop following technician':'Follow technician'} aria-pressed={!!props.follow} title={props.follow?'Stop following technician':'Follow technician'} onClick={()=>{manual.current=false;props.onFollow(props.follow?null:selectedTech(props).id);}}><Navigation size={18}/></button></div>
  </div>;
}
