import type { Preferences } from '../types';
export type Page = 'overview' | 'dispatch';
export type Breakpoint = 'lg' | 'md' | 'sm';
export type Tile = { i: string; x: number; y: number; w: number; h: number };
export type Column = 'customer' | 'trade' | 'status' | 'technician' | 'time';
export type Configuration = { version: 1; layouts: Record<Breakpoint, Tile[]>; hidden: string[]; columns: Column[]; preferences: Preferences; mode: '2D' | '3D' };
export type Account = { identifier: string; workspace: string; role: string; tenant: string; userId: string; demo: boolean };
export type View = { id: string; name: string; page: Page; scope: 'personal' | 'team'; revision: number; configuration: Configuration };
export type ViewList = { views: View[]; teamDefault: View | null; activeViewId: string | null };
export const widgets: Record<Page, { id: string; label: string }[]> = {
 overview: [{id:'metrics',label:'Summary metrics'},{id:'urgent',label:'Urgent work'},{id:'maintenance',label:'Maintenance due'},{id:'renewals',label:'Renewals'},{id:'reviews',label:'Unresolved reviews'},{id:'schedule',label:'Today’s schedule'},{id:'availability',label:'Technician availability'},{id:'stock',label:'Stock attention'}],
 dispatch: [{id:'queue',label:'Job queue'},{id:'schedule',label:'Team schedule'},{id:'map',label:'Dispatch map'}],
};
export const columnLabels: Record<Column, string> = { customer:'Customer / property',trade:'Trade',status:'Status',technician:'Technician',time:'Service time' };
export const defaultPreferences: Preferences = {trade:'All',jobStatus:'All',available:false,names:true,routes:true,density:'comfortable'};
export function minimumWidth(page: Page, id: string, bp: Breakpoint) { return bp === 'sm' ? 1 : page === 'dispatch' && id === 'schedule' ? 6 : 3; }
export function breakpoint(width: number): Breakpoint { return width >= 1000 ? 'lg' : width >= 640 ? 'md' : 'sm'; }
export const gridColumns = {lg:12,md:6,sm:1};
export function preset(page: Page, kind: 'balanced' | 'dispatch' | 'owner' = 'balanced'): Configuration {
 const order = page === 'overview' ? (kind === 'dispatch' ? ['metrics','schedule','urgent','availability','stock','maintenance','reviews','renewals'] : kind === 'owner' ? ['metrics','reviews','renewals','stock','maintenance','urgent','schedule','availability'] : widgets.overview.map(w=>w.id)) : kind === 'dispatch' ? ['schedule','queue','map'] : kind === 'owner' ? ['queue','schedule','map'] : ['queue','schedule','map'];
 const lg: Tile[] = page === 'dispatch'
  ? kind === 'dispatch' ? [{i:'schedule',x:0,y:0,w:12,h:10},{i:'queue',x:0,y:10,w:7,h:8},{i:'map',x:7,y:10,w:5,h:8}]
    : kind === 'owner' ? [{i:'queue',x:0,y:0,w:12,h:8},{i:'schedule',x:0,y:8,w:8,h:10},{i:'map',x:8,y:8,w:4,h:10}] : [{i:'queue',x:0,y:0,w:8,h:6},{i:'schedule',x:0,y:6,w:8,h:10},{i:'map',x:8,y:0,w:4,h:16}]
  : kind === 'balanced' ? [{i:'metrics',x:0,y:0,w:12,h:2},...['urgent','maintenance','renewals','reviews'].map((i,n)=>({i,x:0,y:2+n*6,w:8,h:6})),...['schedule','availability','stock'].map((i,n)=>({i,x:8,y:2+n*6,w:4,h:6}))] : order.map((i,n)=>({i,x:n===0?0:n%2===1?0:8,y:n===0?0:2+Math.floor((n-1)/2)*6,w:n===0?12:n%2===1?8:4,h:n===0?2:6}));
 const stacked = (bp: 'md' | 'sm') => order.reduce<Tile[]>((rows,i)=>{const h=i==='metrics'?2:i==='schedule'&&page==='dispatch'?10:bp==='sm'&&page==='overview'&&i!=='availability'?5:7; rows.push({i,x:0,y:rows.reduce((sum,t)=>sum+t.h,0),w:gridColumns[bp],h});return rows;},[]);
 return {version:1,layouts:{lg,md:stacked('md'),sm:stacked('sm')},hidden:[],columns:Object.keys(columnLabels) as Column[],preferences:{...defaultPreferences},mode:'2D'};
}
export function validConfiguration(value: unknown, page: Page): value is Configuration {
 if (!value || typeof value !== 'object') return false;
 const c=value as Configuration,allowed=new Set(widgets[page].map(w=>w.id));
 if(c.version!==1||!c.layouts||!Array.isArray(c.hidden)||!Array.isArray(c.columns)||!c.preferences||!['2D','3D'].includes(c.mode))return false;
 if(c.hidden.some(id=>!allowed.has(id))||new Set(c.hidden).size!==c.hidden.length||c.hidden.length>=allowed.size)return false;
 if(c.columns.some(id=>!Object.hasOwn(columnLabels,id))||new Set(c.columns).size!==c.columns.length)return false;
 const p=c.preferences;
 if(!['All','Plumbing','HVAC','Electrical'].includes(p.trade)||!['All','Unassigned','Assigned','En route','Arrived','Working','Completed'].includes(p.jobStatus)||!['comfortable','compact'].includes(p.density)||[p.available,p.names,p.routes].some(v=>typeof v!=='boolean'))return false;
 return (['lg','md','sm'] as const).every(bp=>Array.isArray(c.layouts[bp])&&c.layouts[bp].length===allowed.size&&new Set(c.layouts[bp].map(t=>t.i)).size===allowed.size&&c.layouts[bp].every(t=>allowed.has(t.i)&&[t.x,t.y,t.w,t.h].every(Number.isInteger)&&t.x>=0&&t.y>=0&&t.y<=256&&t.h>=2&&t.h<=24&&t.w>=minimumWidth(page,t.i,bp)&&t.x+t.w<=gridColumns[bp]));
}
export function resolveView(data: ViewList, page: Page): Configuration { return data.views.find(v=>v.id===data.activeViewId)?.configuration ?? data.teamDefault?.configuration ?? preset(page); }
export function moveTile(c: Configuration, bp: Breakpoint, id: string, delta: number): Configuration {
 const ordered=[...c.layouts[bp]].sort((a,b)=>a.y-b.y||a.x-b.x),at=ordered.findIndex(t=>t.i===id),to=at+delta;
 if(at<0||to<0||to>=ordered.length)return c;
 [ordered[at],ordered[to]]=[ordered[to],ordered[at]];
 let y=0;
 return {...c,layouts:{...c.layouts,[bp]:ordered.map(t=>{const tile={...t,x:0,y};y+=t.h;return tile;})}};
}
export function devicePreferences(): Preferences | null {
 try {const p=JSON.parse(localStorage.getItem('goob-dispatch-view-v1')||'null');const c={...preset('dispatch'),preferences:p};return validConfiguration(c,'dispatch')?p:null;}catch{return null;}
}
