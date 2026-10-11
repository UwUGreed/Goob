export type Trade = 'Plumbing' | 'HVAC' | 'Electrical';
export type Status = 'Available' | 'Assigned' | 'En route' | 'Arrived' | 'Working' | 'Completed' | 'Returning';
export type JobStatus = 'Unassigned' | 'Assigned' | 'En route' | 'Arrived' | 'Working' | 'Completed';
export type Point = { x: number; z: number };
export type Technician = { id: string; name: string; trade: Trade; truck: string; initials: string; color: string; start: string };
export type Job = { id: string; customerId?:string; title: string; address: string; trade: Trade; customer: string; description: string; part: string; node: string; urgent?: boolean; time: string };
export type TechState = { status: Status; node: string; jobId?: string; route: Point[]; progress: number; running: boolean; duration: number; driving?:import('./integrations/geography').DrivingRoute; replay?:{progress:number;running:boolean} };
export type ScheduleSlot={date:string;start:number;end:number;travelStart:number};
export type Simulation = { customers?:Customer[];stock?:StockItem[];customJobs?:Job[];bookings?:Record<string,ScheduleSlot&{techId:string}>; technicians: Record<string, TechState>; jobs: Record<string, JobStatus>; speed: number; preview?:{route:import('./integrations/geography').DrivingRoute|null;loading:boolean;error:string;key:string} };
export type Preferences = { trade: Trade | 'All'; available: boolean; jobStatus: JobStatus | 'All'; names: boolean; routes: boolean; density: 'comfortable' | 'compact' };
export type Selection = { type: 'job' | 'tech'; id: string } | null;

export type Customer={id:string;name:string;email:string;phone:string;address:string};
export type StockItem={id:string;part:string;sku:string;trade:Trade;truck:string;quantity:number;threshold:number};
