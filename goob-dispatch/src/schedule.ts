import { jobs, technicians, customerFixtures } from './data';
import type { Simulation, ScheduleSlot } from './types';
export const demoDate='2026-10-10';
export const stamp=(day:string,h:number,m=0)=>Date.parse(`${day}T${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:00Z`);
export const demoNow=stamp(demoDate,10,30);
export const jobDetails:Record<string,{number:string;issue:string;minutes:number}>={oak:{number:'1042',issue:'Kitchen sink leak',minutes:60},maple:{number:'1043',issue:'AC not cooling',minutes:60},cedar:{number:'1041',issue:'Electrical service',minutes:120},willow:{number:'1044',issue:'Faucet follow-up',minutes:45}};
export const allJobs=(state:Simulation)=>[...jobs.filter(j=>!state.customJobs?.some(c=>c.id===j.id)),...state.customJobs??[]].map(j=>{const customerId=j.customerId??customerFixtures.find(c=>c.name===j.customer)?.id;return {...j,customerId,customer:state.customers?.find(c=>c.id===customerId)?.name??j.customer};});
export const jobLabel=(id:string,state:Simulation)=>jobDetails[id]?{...jobDetails[id],issue:state.customJobs?.find(j=>j.id===id)?.title??jobDetails[id].issue}:{number:String(2000+(state.customJobs??[]).findIndex(j=>j.id===id)),issue:allJobs(state).find(j=>j.id===id)?.title??'Visit',minutes:60};
export type Booking=ScheduleSlot&{techId:string;jobId?:string;title:string;completed?:boolean};
export const scheduleFixtures:Booking[]=[
 {techId:'maya',title:'Shower repair',completed:true,date:demoDate,start:stamp(demoDate,9),end:stamp(demoDate,10),travelStart:stamp(demoDate,9)},
 {techId:'chris',title:'Filter replacement',date:demoDate,start:stamp(demoDate,13),end:stamp(demoDate,14),travelStart:stamp(demoDate,12,45)},
 {techId:'jordan',jobId:'cedar',title:'Electrical service',date:demoDate,start:stamp(demoDate,9),end:stamp(demoDate,11),travelStart:stamp(demoDate,9)},
];
export function bookingsFor(state:Simulation,techId:string,day:string):Booking[]{return [...scheduleFixtures,...Object.entries(state.bookings??{}).map(([jobId,slot])=>({...slot,jobId,title:jobLabel(jobId,state).issue}))].filter(b=>b.techId===techId&&b.date===day).sort((a,b)=>a.travelStart-b.travelStart);}
export function slotAllowed(state:Simulation,techId:string,slot:ScheduleSlot){return /^\d{4}-\d{2}-\d{2}$/.test(slot.date)&&Number.isFinite(slot.start)&&Number.isFinite(slot.end)&&Number.isFinite(slot.travelStart)&&slot.travelStart>=stamp(slot.date,9)&&slot.end<=stamp(slot.date,18)&&slot.start>=slot.travelStart&&slot.end>slot.start&&slot.end-slot.start<=4*3600000&&!bookingsFor(state,techId,slot.date).some(b=>slot.travelStart<b.end&&slot.end>b.travelStart);}
export function proposedSlot(state:Simulation,techId:string,jobId:string,day=demoDate,travelMinutes=10):ScheduleSlot|null{
 const travel=Math.max(1,Math.ceil(travelMinutes))*60000,work=jobLabel(jobId,state).minutes*60000;
 let start=day===demoDate?Math.max(stamp(day,10,45),demoNow+travel):stamp(day,9)+travel;
 start=Math.ceil(start/900000)*900000;
 for(const b of bookingsFor(state,techId,day))if(start-travel<b.end&&start+work>b.travelStart)start=Math.ceil((b.end+travel)/900000)*900000;
 const slot={date:day,start,end:start+work,travelStart:start-travel};return slotAllowed(state,techId,slot)?slot:null;
}
export const timeLabel=(value:number)=>new Intl.DateTimeFormat('en-US',{hour:'numeric',minute:'2-digit',hour12:false,timeZone:'UTC'}).format(value);
export const dateLabel=(day:string)=>new Intl.DateTimeFormat('en-US',{weekday:'short',month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(day+'T12:00:00Z'));
export const shiftDay=(day:string,delta:number)=>new Date(Date.parse(day+'T12:00:00Z')+delta*86400000).toISOString().slice(0,10);
export const matchesSearch=(text:string,q:string)=>text.toLowerCase().includes(q.trim().toLowerCase());
export const tradeTemplate=(trade:string)=>jobs.find(j=>j.trade===trade)!;
export const team=technicians;
