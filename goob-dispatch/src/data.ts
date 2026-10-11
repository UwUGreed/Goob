import type { Job, Technician, Trade, Preferences } from './types';
export const tradeColors: Record<Trade,string> = { Plumbing: '#3485db', HVAC: '#319b72', Electrical: '#e1a43d' };
export const technicians: Technician[] = [
  { id:'maya', name:'Maya Chen', trade:'Plumbing', truck:'P-02', initials:'MC', color:tradeColors.Plumbing, start:'0-3' },
  { id:'chris', name:'Chris Davis', trade:'HVAC', truck:'H-01', initials:'CD', color:tradeColors.HVAC, start:'1-1' },
  { id:'jordan', name:'Jordan Lee', trade:'Electrical', truck:'E-03', initials:'JL', color:tradeColors.Electrical, start:'3-1' },
];
export const jobs: Job[] = [
  {id:'oak', title:'Urgent plumbing visit', address:'124 Oak Lane', trade:'Plumbing', customer:'Alex Morgan', description:'Steady leak under the kitchen sink. Check the supply line and replace the failed shutoff valve. Same-day visit requested.', part:'½-inch angle stop valve', node:'3-2', urgent:true, time:'As soon as possible'},
  {id:'maple', title:'HVAC repair', address:'82 Maple Avenue', trade:'HVAC', customer:'Sam Rivera', description:'Air conditioner is running but not cooling. Inspect the unit and replace the start capacitor.', part:'Dual-run capacitor', node:'1-0', time:'10:00–12:00'},
  {id:'cedar', title:'Electrical service visit', address:'210 Cedar Street', trade:'Electrical', customer:'Taylor Brooks', description:'Inspect and replace a faulty kitchen GFCI outlet. Jordan is already working on this visit.', part:'GFCI outlet', node:'3-1', time:'09:00–11:00'},
  {id:'willow', title:'Plumbing follow-up', address:'46 Willow Way', trade:'Plumbing', customer:'Jamie Ellis', description:'Replace the worn washer in a dripping bathroom faucet. A quick follow-up visit for Maya.', part:'Faucet washer kit', node:'1-1', time:'After Oak Lane'},
];
export const inventory = [
  {part:'½-inch angle stop valve', truck:'P-02', quantity:3, reserved:'124 Oak Lane'},
  {part:'Faucet washer kit', truck:'P-02', quantity:5, reserved:'46 Willow Way'},
  {part:'Dual-run capacitor', truck:'H-01', quantity:2, reserved:'82 Maple Avenue'},
  {part:'GFCI outlet', truck:'E-03', quantity:4, reserved:'210 Cedar Street'},
];
export const defaults: Preferences = {trade:'All',available:false,jobStatus:'All',names:true,routes:true,density:'comfortable'};
export const depot = '0-3';

export const customerFixtures=jobs.map(j=>({id:j.id,name:j.customer,email:'',phone:'',address:j.address}));
export const stockFixtures=inventory.map((i,n)=>({...i,id:'part-'+n,sku:'GOOB-'+(100+n),trade:technicians.find(t=>t.truck===i.truck)!.trade,threshold:2}));

export const teamRecords=(state:import('./types').Simulation)=>state.roster??technicians;
