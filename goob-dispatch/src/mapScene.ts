import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { streetX, streetZ } from './routing';
export function createDistrict(host:HTMLDivElement) {
  const scene=new THREE.Scene();scene.background=new THREE.Color('#e9e8dc');
  const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputColorSpace=THREE.SRGBColorSpace;host.appendChild(renderer.domElement);
  const camera=new THREE.OrthographicCamera(-620,620,500,-500,1,3000);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableRotate=false;controls.enableDamping=false;controls.screenSpacePanning=true;controls.minZoom=.65;controls.maxZoom=3;controls.mouseButtons.LEFT=THREE.MOUSE.PAN;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;
  scene.add(new THREE.HemisphereLight('#fffdf0','#a6ada0',1.5));
  const sun=new THREE.DirectionalLight('#fff4e4',1.3);sun.position.set(-200,800,250);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-1000,right:1000,top:1000,bottom:-1000,near:1,far:2000});sun.shadow.normalBias=2;scene.add(sun);
  const buildings:THREE.Mesh[]=[];const foliage:THREE.Group[]=[];
  function box(w:number,h:number,d:number,color:string,x:number,y:number,z:number,parent:THREE.Object3D=scene) {
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),new THREE.MeshStandardMaterial({color,roughness:1}));mesh.position.set(x,y+h/2,z);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;
  }
  box(1500,8,1250,'#e8e7da',520,-8,440);
  box(190,2,1250,'#a7c9d4',1040,0,440);
  box(18,3,1250,'#c7d2b3',936,0,440);
  for(const x of streetX) {box(46,1,1050,'#fbfaf3',x,1,440);box(31,1.2,1050,'#d8d8d0',x,1.2,440);for(let z=-70;z<990;z+=30) box(1,1,12,'#fffdf0',x,2.5,z);}
  const streetNames=['Maple Avenue','Cedar Street','Oak Lane','Willow Way'];
  for(const [i,z] of streetZ.entries()) {box(970,1,46,'#fbfaf3',480,1,z);box(970,1.2,31,'#d8d8d0',480,1.2,z);for(let x=0;x<920;x+=30)box(12,1,1,'#fffdf0',x,2.5,z);label(streetNames[i],500,z+2,128,17);}
  // Crosswalks make the grid easy to read in both projections.
  for(const x of streetX)for(const z of streetZ)for(let n=-11;n<=11;n+=5) {box(3,1,12,'#fafaf2',x+n,3,z-25);box(12,1,3,'#fafaf2',x-25,3,z+n);}
  function label(text:string,x:number,z:number,w:number,h:number) {
    const canvas=document.createElement('canvas');canvas.width=512;canvas.height=80;const ctx=canvas.getContext('2d')!;ctx.fillStyle='#777d78';ctx.font='500 34px Arial';ctx.textAlign='center';ctx.fillText(text,256,52);
    const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(canvas),transparent:true,depthWrite:false}));mesh.rotation.x=-Math.PI/2;mesh.position.set(x,4,z);scene.add(mesh);
  }
  function tree(x:number,z:number,r:number=10) {
    const group=new THREE.Group();group.position.set(x,0,z);box(3,15,3,'#a29276',0,0,0,group);
    const crown=new THREE.Mesh(new THREE.IcosahedronGeometry(r,1),new THREE.MeshStandardMaterial({color:['#9bb588','#adc491','#8daa7c'][Math.floor((x+z)%3)],roughness:1}));crown.position.y=21;crown.castShadow=true;group.add(crown);scene.add(group);foliage.push(group);
  }
  const roofColors=['#ddd6c4','#e5dfd1','#c8cfd0','#dbc9b9','#dedacb','#c5c7bb'];
  for(let i=0;i<3;i++)for(let j=0;j<3;j++) {
    const x=streetX[i]+120,z=streetZ[j]+105;
    box(191,1,162,'#dce2cd',x,0,z);
    if(i===1&&j===0) {
      box(177,1,148,'#c9d8b3',x,1,z);box(170,1,8,'#eeeadb',x,2,z);box(8,1,140,'#eeeadb',x,2,z);
      for(let n=0;n<12;n++)tree(x-72+(n%4)*48,z-51+Math.floor(n/4)*48,11);
      label('COMMONS PARK',x,z+42,155,15);continue;
    }
    for(let a=0;a<3;a++)for(let b=0;b<2;b++) {
      const bx=x-66+a*66,bz=z-40+b*80,seed=i*13+j*17+a*5+b*7;
      const w=34+seed%16,d=35+seed%12,h=20+seed%45;
      box(w+9,1,d+9,'#f1eee1',bx,1,bz);
      const building=box(w,h,d,roofColors[seed%roofColors.length],bx,2,bz);buildings.push(building);
      const roof=box(w+2,2,d+2,'#f3efe5',bx,h+2,bz);buildings.push(roof);
      // Raised trim and a small roof unit give the 3D buildings a service-district feel.
      const unit=box(8,4,10,'#b5bab4',bx+5,h+4,bz);buildings.push(unit);
      for(let floor=0;floor<Math.floor(h/12);floor++)for(let col=-1;col<=1;col++) {
        const win=box(5,5,1,'#b3bcb9',bx+col*10,8+floor*11,bz+d/2+.5);buildings.push(win);
      }
      tree(bx+25,bz-24,7+seed%4);
    }
  }
  // Riverbank pocket park and depot, away from the street centerlines.
  box(64,1,655,'#d2dfc0',893,1,450);for(let z=180;z<770;z+=58)tree(901,z,11);
  box(104,2,62,'#d4d0c4',207,1,822);buildings.push(box(82,31,43,'#b5c2b2',207,3,822));buildings.push(box(86,3,47,'#efece0',207,34,822));label('GOOB DEPOT',206,867,110,15);
  const vehicles=new Map<string,THREE.Group>();
  function vehicle(id:string,color:string) {
    const group=new THREE.Group();box(14,9,27,color,0,5,0,group);box(13,8,12,'#fafaf4',0,7,6,group);box(12,5,1,'#566c76',0,11,12.4,group);box(9,1,11,'#fafaf4',0,16,5,group);
    for(const x of [-7,7])for(const z of [-8,8]) {const wheel=new THREE.Mesh(new THREE.CylinderGeometry(3,3,2,10),new THREE.MeshStandardMaterial({color:'#41484a'}));wheel.rotation.z=Math.PI/2;wheel.position.set(x,5,z);group.add(wheel);}
    scene.add(group);vehicles.set(id,group);return group;
  }
  const routeGroup=new THREE.Group();scene.add(routeGroup);
  function setRoutes(routes:{points:{x:number;z:number}[];color:string;preview:boolean}[]) {
    while(routeGroup.children.length){const child=routeGroup.children[0] as THREE.Mesh;child.geometry.dispose();(child.material as THREE.Material).dispose();routeGroup.remove(child);}
    routes.forEach(route=>{
      for(let i=1;i<route.points.length;i++) {
        const a=route.points[i-1],b=route.points[i],length=Math.hypot(a.x-b.x,a.z-b.z);
        if(!length)continue;
        const mesh=box(5,1.8,length,route.color,(a.x+b.x)/2,4,(a.z+b.z)/2,routeGroup);mesh.rotation.y=Math.atan2(b.x-a.x,b.z-a.z);(mesh.material as THREE.MeshStandardMaterial).transparent=true;(mesh.material as THREE.MeshStandardMaterial).opacity=route.preview?.65:1;
      }
    });
  }
  function reset(mode:'2D'|'3D') {
    controls.target.set(495,0,430);camera.up.set(0,1,0);camera.position.set(mode==='2D'?495:850,mode==='2D'?1300:900,mode==='2D'?430.1:1100);camera.zoom=1;camera.lookAt(controls.target);controls.update();
    buildings.forEach(mesh=>{const original=mesh.userData.baseY??mesh.position.y;mesh.userData.baseY=original;mesh.scale.y=mode==='2D'?.03:1;mesh.position.y=mode==='2D'?3.5:original;});
    foliage.forEach(group=>{group.scale.y=mode==='2D'?.28:1;});renderer.shadowMap.enabled=mode==='3D';
  }
  function resize() {const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h);camera.left=-610;camera.right=610;camera.top=610*h/w;camera.bottom=-610*h/w;camera.updateProjectionMatrix();}
  const observer=new ResizeObserver(resize);observer.observe(host);resize();reset('3D');
  return {scene,renderer,camera,controls,vehicles,vehicle,setRoutes,reset,dispose(){observer.disconnect();controls.dispose();scene.traverse(o=>{if(o instanceof THREE.Mesh){o.geometry.dispose();const mats=Array.isArray(o.material)?o.material:[o.material];mats.forEach(m=>{if(m.map)m.map.dispose();m.dispose();});}});renderer.dispose();renderer.domElement.remove();}};
}
