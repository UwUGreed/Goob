import type { Point } from './types';
export const streetX = [120,360,600,840];
export const streetZ = [130,340,550,760];
export const nodes: Record<string,Point> = {};
streetX.forEach((x,i)=>streetZ.forEach((z,j)=>{nodes[`${i}-${j}`]={x,z};}));
export const edges: [string,string][] = [];
for(let i=0;i<4;i++) for(let j=0;j<4;j++) {
  if(i<3) edges.push([`${i}-${j}`,`${i+1}-${j}`]);
  if(j<3) edges.push([`${i}-${j}`,`${i}-${j+1}`]);
}
export const distance = (a:Point,b:Point) => Math.hypot(a.x-b.x,a.z-b.z);
export function findRoute(from:string,to:string):Point[] {
  if(!nodes[from]||!nodes[to]) throw new Error('Unknown street location');
  const queue=[from], previous:Record<string,string|undefined>={[from]:undefined};
  while(queue.length) {
    const current=queue.shift()!; if(current===to) break;
    for(const [a,b] of edges) {
      const next=a===current?b:b===current?a:null;
      if(next && !(next in previous)) {previous[next]=current;queue.push(next);}
    }
  }
  const path:Point[]=[]; let current:string|undefined=to;
  while(current) {path.unshift(nodes[current]);current=previous[current];}
  return path;
}
export const routeLength=(route:Point[])=>route.slice(1).reduce((sum,p,i)=>sum+distance(route[i],p),0);
export function pointOnRoute(route:Point[],progress:number):Point & {angle:number} {
  if(route.length<2) return {...(route[0]??nodes['0-3']),angle:0};
  let remaining=routeLength(route)*Math.max(0,Math.min(1,progress));
  for(let i=1;i<route.length;i++) {
    const a=route[i-1],b=route[i],length=distance(a,b);
    if(remaining<=length || i===route.length-1) {const f=length?remaining/length:0;return {x:a.x+(b.x-a.x)*f,z:a.z+(b.z-a.z)*f,angle:Math.atan2(b.x-a.x,b.z-a.z)};}
    remaining-=length;
  }
  return {...route.at(-1)!,angle:0};
}
