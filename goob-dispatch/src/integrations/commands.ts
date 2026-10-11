import { jobs, technicians, teamRecords } from '../data';
import type { Job, Simulation, Trade, Technician } from '../types';
export type Command={type:'availability';trade:Trade}|{type:'filter';trade:Trade;available:boolean}|{type:'open-job';jobId:string}|{type:'parts'}|{type:'recommend';jobId?:string;techId?:string}|{type:'preview';techId:string}|{type:'mode';mode:'2D'|'3D'}|{type:'follow';techId:string};
export function availabilityReply(state:Simulation,trade:Trade){
  const team=teamRecords(state).filter(t=>t.trade===trade),available=team.filter(t=>['Available','Completed'].includes(state.technicians[t.id].status));
  if(available.length)return `${available.map(t=>t.name).join(' and ')} ${available.length===1?'is':'are'} available for ${trade==='HVAC'?'HVAC':trade.toLowerCase()}.`;
  const busy=team.map(t=>`${t.name} is ${state.technicians[t.id].status==='Working'?'on a job':state.technicians[t.id].status.toLowerCase()}.`).join(' ');
  return `No ${trade==='Electrical'?'electrician':trade==='Plumbing'?'plumber':'HVAC technician'} is available right now. ${busy}`;
}
export type ParsedCommand={ok:true;commands:Command[]}|{ok:false;message:string;choices?:{label:string;text:string}[]};
export function interpretCommand(input:string,catalog:Job[]=jobs,technicians:Technician[]=teamRecords({} as Simulation)):ParsedCommand{
  const text=input.toLowerCase().replace(/\bavaliable\b/g,'available').replace(/[’']s\b/g,'').replace(/[’']/g,'').replace(/[.,!?]/g,'').trim();if(!text||text.length>500)return{ok:false,message:'Enter a short dispatch command.'};
  const jobMatches=catalog.filter(j=>text.includes(j.address.split(' ').slice(1).join(' ').toLowerCase())||text.includes(j.id));
  const techMatches=technicians.filter(t=>text.includes(t.name.toLowerCase())||new RegExp(`\\b${t.name.split(' ')[0].toLowerCase()}\\b`).test(text));
  if(jobMatches.length>1)return{ok:false,message:'Which visit do you mean?',choices:jobMatches.map(j=>({label:j.address,text:`Open the ${j.id} job`}))};
  if(techMatches.length>1)return{ok:false,message:'Which technician do you mean?',choices:techMatches.map(t=>({label:t.name,text:`Follow ${t.name}`}))};
  const job=jobMatches[0],tech=techMatches[0],commands:Command[]=[];
  if(/^(switch|show|open) (to )?(the )?[23]d( (map|view))?$/.test(text))return{ok:true,commands:[{type:'mode',mode:text.includes('3d')?'3D':'2D'}]};
  if(/^follow\b/.test(text)){if(!tech)return{ok:false,message:'Choose a technician to follow.',choices:technicians.map(t=>({label:t.name,text:`Follow ${t.name}`}))};return{ok:true,commands:[{type:'follow',techId:tech.id}]};}
  if(/^preview\b/.test(text)&&/route/.test(text)){if(!tech)return{ok:false,message:'Whose route should I preview?',choices:technicians.map(t=>({label:t.name,text:`Preview ${t.name}s route`}))};return{ok:true,commands:[{type:'preview',techId:tech.id}]};}
  if(/\b(open|select)\b/.test(text)&&/\b(job|visit|lane|avenue|street|way)\b/.test(text)){if(!job)return{ok:false,message:'Choose an existing demo visit.',choices:catalog.slice(0,3).map(j=>({label:j.address,text:`Open the ${j.id} job`}))};commands.push({type:'open-job',jobId:job.id});}
  const trade:Trade|undefined=/\b(plumber|plumbers|plumbing)\b/.test(text)?'Plumbing':/\b(hvac|mechanical)\b/.test(text)?'HVAC':/\b(electrician|electricians|electrical)\b/.test(text)?'Electrical':undefined;
  if(/^(who|which|is|are|any)\b/.test(text)&&/\bavailable\b/.test(text)){
    const trades=([['Plumbing',/\b(plumber|plumbers|plumbing)\b/],['HVAC',/\b(hvac|mechanical)\b/],['Electrical',/\b(electrician|electricians|electrical)\b/]] as const).filter(([,pattern])=>pattern.test(text));
    if(trades.length!==1)return{ok:false,message:'Which trade should I check?',choices:['Plumbing','HVAC','Electrical'].map(t=>({label:t,text:`Who is available for ${t}?`}))};
    return{ok:true,commands:[{type:'availability',trade:trades[0][0]}]};
  }
  if(/^show\b/.test(text)&&trade)commands.push({type:'filter',trade,available:/\bavailable\b/.test(text)});
  if(/\b(find|recommend|propose|assign)\b/.test(text)&&(/\b(technician|plumber|plumbers|plumbing|hvac|electrician|electrical|maya|chris|jordan)\b/.test(text))){if(job&&!commands.some(c=>c.type==='open-job'))commands.push({type:'open-job',jobId:job.id});commands.push({type:'recommend',jobId:job?.id,techId:tech?.id});}
  if(/\b(check|inspect|show)\b/.test(text)&&/\bparts?\b/.test(text)){if(job&&!commands.some(c=>c.type==='open-job'))commands.push({type:'open-job',jobId:job.id});commands.push({type:'parts'});}
  if(commands.length)return{ok:true,commands};
  return{ok:false,message:'I could not match that to a supported command. Try “Open the Oak Lane job” or “Show available plumbers.” Assignment changes always require the Confirm assignment button.'};
}
