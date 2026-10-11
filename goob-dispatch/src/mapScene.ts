import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { streetX, streetZ } from './routing';
import type { Point, Trade } from './types';
export type MapMode = '2D' | '3D';
export type Insets = { left:number; right:number; top:number; bottom:number };
type Route = { points:Point[]; color:string; preview:boolean };

export function createDistrict(host:HTMLDivElement) {
  const scene=new THREE.Scene();scene.background=new THREE.Color('#e9e6dc');
  const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1;
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;host.appendChild(renderer.domElement);
  // All resources are scene-owned. Route changes never dispose shared scenery.
  const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>(),textures=new Set<THREE.Texture>();
  function geometry<T extends THREE.BufferGeometry>(g:T):T{geometries.add(g);return g;}
  const cube=geometry(new THREE.BoxGeometry(1,1,1)),plane=geometry(new THREE.PlaneGeometry(1,1)),crown=geometry(new THREE.IcosahedronGeometry(1,1)),wheelGeo=geometry(new THREE.CylinderGeometry(1,1,1,10)),ring=geometry(new THREE.RingGeometry(.84,1,48));
  const matCache=new Map<string,THREE.Material>();
  function mat(color:string,basic=false,opacity=1):THREE.Material {
    const key=`${color}/${basic}/${opacity}`;
    if(!matCache.has(key)){const options={color,transparent:opacity<1,opacity,depthWrite:opacity===1};const value=basic?new THREE.MeshBasicMaterial({...options,toneMapped:false}):new THREE.MeshStandardMaterial({...options,roughness:.92});matCache.set(key,value);materials.add(value);}return matCache.get(key)!;
  }
  const camera=new THREE.OrthographicCamera(-610,610,500,-500,1,3200);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableRotate=false;controls.enableDamping=false;controls.screenSpacePanning=true;
  controls.minZoom=.45;controls.maxZoom=3;controls.mouseButtons.LEFT=THREE.MOUSE.PAN;controls.touches.ONE=THREE.TOUCH.PAN;controls.listenToKeyEvents(renderer.domElement);
  scene.add(new THREE.HemisphereLight('#fff9eb','#a5afa2',1.55));
  const sun=new THREE.DirectionalLight('#fff5e8',1.75);sun.position.set(-350,900,250);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.radius=4;sun.shadow.normalBias=.6;sun.shadow.bias=-.00015;
  Object.assign(sun.shadow.camera,{left:-760,right:760,top:760,bottom:-760,near:1,far:2300});sun.target.position.set(480,0,430);scene.add(sun,sun.target);
  const fill=new THREE.DirectionalLight('#d9e4ed',.4);fill.position.set(700,450,-300);scene.add(fill);
  const terrain=new THREE.Group(),architecture=new THREE.Group(),landscaping=new THREE.Group();scene.add(terrain,architecture,landscaping);architecture.position.y=2;
  function mesh(g:THREE.BufferGeometry,m:THREE.Material,scale:[number,number,number],position:[number,number,number],parent:THREE.Object3D,shadows=true){const o=new THREE.Mesh(g,m);o.scale.set(...scale);o.position.set(...position);o.castShadow=shadows;o.receiveShadow=true;parent.add(o);return o;}
  function box(w:number,h:number,d:number,color:string,x:number,y:number,z:number,parent:THREE.Object3D=terrain,shadows=false){return mesh(cube,mat(color),[w,h,d],[x,y+h/2,z],parent,shadows);}
  function groundText(text:string,x:number,z:number,w:number){
    const canvas=document.createElement('canvas');canvas.width=512;canvas.height=100;const ctx=canvas.getContext('2d')!;ctx.font='600 45px Arial';ctx.fillStyle='#657268';ctx.textAlign='center';ctx.fillText(text,256,65);
    const texture=new THREE.CanvasTexture(canvas);textures.add(texture);const m=new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,toneMapped:false});materials.add(m);
    const o=mesh(plane,m,[w,25,1],[x,3.8,z],terrain,false);o.rotation.x=-Math.PI/2;
  }
  // A single shared gradient provides soft contact depth without postprocessing.
  const contactCanvas=document.createElement('canvas');contactCanvas.width=contactCanvas.height=64;const ctx=contactCanvas.getContext('2d')!;
  const gradient=ctx.createRadialGradient(32,32,5,32,32,32);gradient.addColorStop(0,'rgba(61,64,50,.22)');gradient.addColorStop(.55,'rgba(61,64,50,.12)');gradient.addColorStop(1,'rgba(61,64,50,0)');ctx.fillStyle=gradient;ctx.fillRect(0,0,64,64);
  const contactTexture=new THREE.CanvasTexture(contactCanvas);textures.add(contactTexture);const contactMat=new THREE.MeshBasicMaterial({map:contactTexture,transparent:true,depthWrite:false,toneMapped:false});materials.add(contactMat);
  function contact(x:number,z:number,w:number,d:number,parent:THREE.Object3D=terrain){const o=mesh(plane,contactMat,[w,d,1],[x,2.3,z],parent,false);o.rotation.x=-Math.PI/2;}
  box(1250,8,1110,'#e3e0d3',535,-8,440);box(160,1,1110,'#9ec3cc',1020,.2,440);box(14,2,1110,'#bfceb3',933,.3,440);
  for(const x of streetX){box(50,.7,990,'#f8f5eb',x,.7,440);box(35,.7,990,'#edece2',x,1.5,440);for(let z=-25;z<940;z+=36)box(1.3,.2,13,'#fffdf6',x,2.25,z);}
  for(const [i,z]of streetZ.entries()){box(940,.7,50,'#f8f5eb',490,.7,z);box(940,.7,35,'#edece2',490,1.5,z);for(let x=40;x<950;x+=36)box(13,.2,1.3,'#fffdf6',x,2.25,z);groundText(['MAPLE AVENUE','CEDAR STREET','OAK LANE','WILLOW WAY'][i],472,z,176);}
  for(const x of streetX)for(const z of streetZ)for(let n=-12;n<=12;n+=6){box(3,.3,10,'#fffdf6',x+n,2.4,z-25);box(10,.3,3,'#fffdf6',x-25,2.4,z+n);}
  // Reusable roofs stay centered over their actual footprints in both modes.
  const roofShape=new THREE.Shape();roofShape.moveTo(-.5,0);roofShape.lineTo(0,1);roofShape.lineTo(.5,0);roofShape.closePath();
  const gable=geometry(new THREE.ExtrudeGeometry(roofShape,{depth:1,bevelEnabled:false}));gable.translate(0,0,-.5);
  const hip=geometry(new THREE.BufferGeometry());const corners=[[-.5,0,-.5],[.5,0,-.5],[.5,0,.5],[-.5,0,.5]],vertices:number[]=[];
  corners.forEach((p,i)=>vertices.push(...p,0,1,0,...corners[(i+1)%4]));hip.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));hip.computeVertexNormals();
  const walls=['#d5c7b5','#d9d4c6','#bbc7c0','#d8c3b8','#c4c7b9','#d4d2c9'],roofs=['#9d9f95','#a79786','#919d99','#b6aa95'],greens=['#a3b78c','#91a883','#b3c19c'];
  function tree(x:number,z:number,r=9){box(2.5,13,2.5,'#9f9278',x,2,z,landscaping);mesh(crown,mat(greens[Math.floor(x+z)%3]),[r,r*.86,r],[x,21,z],landscaping);}
  function building(x:number,z:number,w:number,d:number,h:number,type:'cottage'|'townhouse'|'shop'|'office',seed:number){
    const group=new THREE.Group();group.position.set(x,0,z);architecture.add(group);const style=type==='shop'||type==='office'?'flat':seed%3===0?'hip':'gable';
    box(w+12,.8,d+12,'#c7c5b8',x,.7,z);contact(x,z,w+24,d+24);box(w,h,d,walls[seed%walls.length],0,0,0,group,true);
    if(style==='flat'){box(w+2,2,d+2,roofs[seed%4],0,h,0,group,true);box(10,5,12,'#8d9c98',w*.18,h+2,-d*.2,group,true);box(w-3,1,2,'#d9d7cc',0,h+2,d/2,group);}
    else{mesh(style==='hip'?hip:gable,mat(roofs[seed%4]),[w+4,11+seed%8,d+5],[0,h,0],group);box(4,10,5,'#a59385',-w*.24,h+4,-d*.2,group,true);}
    const floors=type==='office'?3:type==='townhouse'?2:1,count=type==='office'?3:2;
    for(let f=0;f<floors;f++)for(let n=0;n<count;n++){const wx=-w/2+(n+1)*w/(count+1),wy=8+f*12;box(type==='shop'?12:6,type==='shop'?10:6,.6,'#809796',wx,wy,d/2+.4,group);box(.6,6,7,'#879c99',w/2+.4,wy,0,group);}
    box(5,9,.8,'#86766a',0,0,d/2+.5,group);
    if(type==='cottage'){box(14,2,9,'#d9d3c2',0,0,d/2+4,group);box(20,1.5,11,roofs[seed%4],0,11,d/2+4,group);for(const dx of[-8,8])box(1.2,10,1.2,'#d1c8b8',dx,1,d/2+8,group);}
    if(type==='shop'){box(w-5,2,8,['#9eae98','#bd9380','#929eac'][seed%3],0,15,d/2+4,group,true);box(w-6,3,.8,'#e6e1d3',0,21,d/2+.6,group);}
    if(seed%4===0)box(10,3,5,'#aab791',x-w/2-8,1,z+d/3);
  }
  let buildingCount=0;
  for(let i=0;i<3;i++)for(let j=0;j<3;j++){
    const x=streetX[i]+120,z=streetZ[j]+105;box(185,.4,155,'#d6dbc8',x,.5,z);
    if(i===1&&j===0){box(179,.4,150,'#c5d2b4',x,1,z);box(8,.3,145,'#eee8d9',x,1.6,z);box(175,.3,8,'#eee8d9',x,1.6,z);[[-65,-48],[65,-48],[-65,48],[65,48]].forEach(([dx,dz])=>tree(x+dx,z+dz,12));box(13,3,4,'#9e8e77',x-28,2,z+20);box(13,3,4,'#9e8e77',x+28,2,z+20);groundText('COMMONS PARK',x,z+49,143);continue;}
    for(let row=0;row<2;row++)for(let col=0;col<3;col++){
      const seed=i*23+j*17+row*7+col*11;
      const type=(i===1&&j===2&&col!==2)||(i===2&&j===0&&row===0)?'shop':seed%9===0?'office':seed%4===0?'townhouse':'cottage';
      const w=type==='shop'?49:type==='office'?41:30+seed%10,d=type==='shop'?43:32+seed%9,h=type==='office'?45:type==='townhouse'?29:type==='shop'?23:17+seed%6;
      const bx=x-64+col*64+(seed%7-3),bz=z-39+row*78+(seed%9-4);building(bx,bz,w,d,h,type,seed);buildingCount++;
      if(seed%5===1)tree(bx-24,bz-24,7);
    }
  }
  box(67,.4,665,'#cbd6bb',891,1,450);for(let z=200;z<750;z+=115)tree(903,z,10);
  // Sawtooth workshop, three loading bays, and a lower office wing.
  box(132,1,91,'#c6c6b9',210,.8,823);contact(210,822,130,94);
  const depotGroup=new THREE.Group();depotGroup.position.set(218,0,819);architecture.add(depotGroup);box(93,34,55,'#92a799',0,0,0,depotGroup,true);
  for(let bay=-1;bay<=1;bay++){mesh(gable,mat('#6f8379'),[31,12,60],[bay*31,34,0],depotGroup);box(22,23,.8,'#657c70',bay*29,0,28,depotGroup);for(let slat=0;slat<5;slat++)box(20,.5,1,'#a5b3a8',bay*29,4+slat*4,28.6,depotGroup);}
  box(35,23,43,'#c0c5b4',-60,0,4,depotGroup,true);box(38,2,46,'#e1ddcd',-60,23,4,depotGroup,true);box(19,8,.8,'#75928b',-60,10,26,depotGroup);box(91,5,1.5,'#ece4ce',0,27,28.8,depotGroup);
  const sign=document.createElement('canvas');sign.width=256;sign.height=48;const signCtx=sign.getContext('2d')!;signCtx.fillStyle='#ece4ce';signCtx.fillRect(0,0,256,48);signCtx.font='bold 29px Georgia';signCtx.fillStyle='#465f50';signCtx.textAlign='center';signCtx.fillText('goob depot',128,34);
  const signTexture=new THREE.CanvasTexture(sign);textures.add(signTexture);const signMat=new THREE.MeshBasicMaterial({map:signTexture,toneMapped:false});materials.add(signMat);mesh(plane,signMat,[80,8,1],[0,29,29.7],depotGroup,false);
  for(let n=0;n<4;n++)box(1,.3,15,'#f3f0e3',175+n*24,2,862);groundText('GOOB DEPOT',205,882,130);
  // Batch static meshes. Windows, roof shapes, streets and shadows share buffers.
  function batch(group:THREE.Group){
    group.updateMatrixWorld(true);const inverse=group.matrixWorld.clone().invert();
    const buckets=new Map<string,{g:THREE.BufferGeometry;m:THREE.Material;matrices:THREE.Matrix4[];cast:boolean;receive:boolean}>();
    group.traverse(o=>{if(!(o instanceof THREE.Mesh)||Array.isArray(o.material))return;const key=`${o.geometry.uuid}/${o.material.uuid}/${o.castShadow}/${o.receiveShadow}`;if(!buckets.has(key))buckets.set(key,{g:o.geometry,m:o.material,matrices:[],cast:o.castShadow,receive:o.receiveShadow});buckets.get(key)!.matrices.push(inverse.clone().multiply(o.matrixWorld));});group.clear();
    buckets.forEach(b=>{const instances=new THREE.InstancedMesh(b.g,b.m,b.matrices.length);b.matrices.forEach((matrix,i)=>instances.setMatrixAt(i,matrix));instances.castShadow=b.cast;instances.receiveShadow=b.receive;instances.computeBoundingSphere();group.add(instances);});
  }
  batch(terrain);batch(architecture);batch(landscaping);
  const vehicles=new Map<string,THREE.Group>(),halos=new Map<string,THREE.Mesh>();
  function vehicle(id:string,color:string,trade?:Trade){
    const group=new THREE.Group();contact(0,0,28,47,group);box(18,11,34,color,0,5,0,group,true);box(17,8,14,'#f6f5e9',0,9,9,group,true);box(15,5,.8,'#455e66',0,12,16.2,group);box(12,1,11,'#f5f3e7',0,17,8,group);
    for(const x of[-9,9])for(const z of[-11,11]){const wheel=mesh(wheelGeo,mat('#3e4846'),[3.8,2.5,3.8],[x,5,z],group,false);wheel.rotation.z=Math.PI/2;}
    for(const x of[-6,6])box(2.5,2,1,'#d87765',x,9,-17.4,group);
    if(trade==='Plumbing')for(const x of[-5,-2])box(1.7,1.7,18,'#c9d9dc',x,17,-4,group);
    if(trade==='HVAC')box(10,4,10,'#c6d5c4',0,16,-7,group);
    if(trade==='Electrical'){for(const x of[-5,5])box(1,1,23,'#e6d3a6',x,17,-3,group);for(let z=-12;z<8;z+=5)box(10,1,1,'#e6d3a6',0,17,z,group);}
    // Moving trucks use their contact shadows; the district's sun shadows are
    // cached so travel never redraws the static neighborhood shadow map.
    group.traverse(object=>{object.castShadow=false;});
    const halo=mesh(ring,mat(color,true,.75),[29,29,1],[0,3.2,0],group,false);halo.rotation.x=-Math.PI/2;halo.visible=false;halos.set(id,halo);group.scale.setScalar(1.08);scene.add(group);vehicles.set(id,group);return group;
  }
  const destination=mesh(ring,mat('#3485db',true),[23,23,1],[0,3.5,0],scene,false);destination.rotation.x=-Math.PI/2;destination.visible=false;
  function highlight(id:string|null,point:Point|null,color:string){vehicles.forEach((g,key)=>{g.scale.setScalar(key===id?1.16:1.08);halos.get(key)!.visible=key===id;});destination.visible=!!point;if(point){destination.position.set(point.x,3.8,point.z);destination.material=mat(color,true,.9);}}
  const routeGroup=new THREE.Group();scene.add(routeGroup);
  function setRoutes(routes:Route[]){routeGroup.clear();routes.forEach(route=>{for(let i=1;i<route.points.length;i++){const a=route.points[i-1],b=route.points[i],length=Math.hypot(b.x-a.x,b.z-a.z);if(!length)continue;const outline=mesh(cube,mat('#fffefa',true,.96),[10,.5,length+5],[(a.x+b.x)/2,3.4,(a.z+b.z)/2],routeGroup,false);outline.rotation.y=Math.atan2(b.x-a.x,b.z-a.z);const line=mesh(cube,mat(route.color,true,route.preview?.8:1),[5.8,.6,length+4],[(a.x+b.x)/2,4,(a.z+b.z)/2],routeGroup,false);line.rotation.y=outline.rotation.y;}});}
  let goal:{target:THREE.Vector3;zoom:number}|null=null;
  function setMode(next:MapMode){goal=null;camera.up.set(0,1,0);camera.position.copy(controls.target).add(new THREE.Vector3(next==='2D'?0:570,next==='2D'?1350:1040,next==='2D'?.1:820));camera.lookAt(controls.target);controls.update();architecture.scale.y=next==='2D'?.025:1;landscaping.scale.y=next==='2D'?.23:1;sun.castShadow=next==='3D';renderer.shadowMap.enabled=next==='3D';renderer.shadowMap.needsUpdate=next==='3D';}
  function framePoints(points:Point[],padding:Insets,immediate=false){
    if(!points.length)return;camera.updateMatrixWorld();const right=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,0),up=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,1);
    const center=new THREE.Vector3((Math.min(...points.map(p=>p.x))+Math.max(...points.map(p=>p.x)))/2,0,(Math.min(...points.map(p=>p.z))+Math.max(...points.map(p=>p.z)))/2);
    const xs=points.map(p=>new THREE.Vector3(p.x,15,p.z).sub(center).dot(right)),ys=points.map(p=>new THREE.Vector3(p.x,15,p.z).sub(center).dot(up));
    const spanX=Math.max(490,Math.max(...xs)-Math.min(...xs)+100),spanY=Math.max(350,Math.max(...ys)-Math.min(...ys)+80),w=host.clientWidth,h=host.clientHeight;
    const zoom=Math.max(.45,Math.min(2.25,(camera.right-camera.left)/spanX*Math.max(.2,(w-padding.left-padding.right)/w),(camera.top-camera.bottom)/spanY*Math.max(.2,(h-padding.top-padding.bottom)/h)));
    const shiftX=(padding.left-padding.right)/2*(camera.right-camera.left)/w/zoom,shiftY=(padding.bottom-padding.top)/2*(camera.top-camera.bottom)/h/zoom;
    center.addScaledVector(right,-shiftX);const groundUp=new THREE.Vector3(up.x,0,up.z);if(groundUp.lengthSq()>.001)center.addScaledVector(groundUp,-shiftY/groundUp.lengthSq());
    goal={target:center,zoom};if(immediate)stepCamera(1,true);
  }
  function stepCamera(dt:number,reduced=false){if(!goal)return;const f=reduced?1:1-Math.exp(-dt*8),delta=goal.target.clone().sub(controls.target).multiplyScalar(f);controls.target.add(delta);camera.position.add(delta);camera.zoom+=(goal.zoom-camera.zoom)*f;camera.updateProjectionMatrix();controls.update();if(delta.length()<.015&&Math.abs(camera.zoom-goal.zoom)<.0001)goal=null;}
  function followPoint(point:Point,dt:number,reduced=false){goal=null;const delta=new THREE.Vector3(point.x,0,point.z).sub(controls.target).multiplyScalar(reduced?1:1-Math.exp(-dt*7));controls.target.add(delta);camera.position.add(delta);controls.update();}
  function cancelCamera(){goal=null;}
  function reset(next:MapMode){controls.target.set(480,0,440);camera.zoom=1;setMode(next);framePoints([{x:90,z:95},{x:890,z:820}],{left:55,right:70,top:85,bottom:100},true);}
  function resize(){const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight);renderer.setSize(w,h);camera.left=-610;camera.right=610;camera.top=610*h/w;camera.bottom=-610*h/w;camera.updateProjectionMatrix();}
  const observer=new ResizeObserver(resize);observer.observe(host);resize();reset('3D');host.dataset.buildingCount=String(buildingCount+1);host.dataset.batches=String(terrain.children.length+architecture.children.length+landscaping.children.length);
  return{scene,renderer,camera,controls,vehicles,vehicle,highlight,setRoutes,setMode,framePoints,stepCamera,followPoint,cancelCamera,reset,
    dispose(){observer.disconnect();controls.dispose();geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());scene.traverse(o=>{if(o instanceof THREE.InstancedMesh)o.dispose();});renderer.dispose();renderer.domElement.remove();},
  };
}
