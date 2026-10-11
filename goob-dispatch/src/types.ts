export type Trade = 'Plumbing' | 'HVAC' | 'Electrical';
export type Status = 'Available' | 'Assigned' | 'En route' | 'Arrived' | 'Working' | 'Completed' | 'Returning';
export type JobStatus = 'Unassigned' | 'Assigned' | 'En route' | 'Arrived' | 'Working' | 'Completed';
export type Point = { x: number; z: number };
export type Technician = { branchId?:string;locationId?:string; id: string; name: string; trade: Trade; truck: string; initials: string; color: string; start: string };
export type Job = { displayNumber?:string;verification?:boolean;propertyId?:string;equipmentId?:string;service?:string;serviceDate?:string;lines?:ChargeLine[];coverage?:Coverage;chargeProposal?:ChargeProposal;appliedCharge?:ChargeProposal;notes?:string;reviewed?:boolean;history?:{kind:string;date:string;actor:string}[]; branchId?:string; id: string; customerId?:string;requirements?:{part:string;quantity:number;skuId:string}[]; title: string; address: string; trade: Trade; customer: string; description: string; part: string; node: string; urgent?: boolean; time: string };
export type TechState = { status: Status; node: string; jobId?: string; route: Point[]; progress: number; running: boolean; duration: number; driving?:import('./integrations/geography').DrivingRoute; replay?:{progress:number;running:boolean} };
export type ScheduleSlot={date:string;start:number;end:number;travelStart:number};
export type Simulation = { properties?:Property[];equipment?:Equipment[];plans?:ServicePlan[];memberships?:ServiceMembership[];movements?:StockMovement[];locations?:{id:string;name:string;type:string}[]; customers?:Customer[];stock?:StockItem[];databaseBacked?:boolean;records?:Job[];roster?:Technician[];reservations?:{jobId:string;part:string;truck:string;quantity:number}[];customJobs?:Job[];bookings?:Record<string,ScheduleSlot&{techId:string}>; technicians: Record<string, TechState>; jobs: Record<string, JobStatus>; speed: number; preview?:{route:import('./integrations/geography').DrivingRoute|null;loading:boolean;error:string;key:string} };
export type Preferences = { trade: Trade | 'All'; available: boolean; jobStatus: JobStatus | 'All'; names: boolean; routes: boolean; density: 'comfortable' | 'compact' };
export type Selection = { type: 'job' | 'tech'; id: string } | null;

export type Customer={verification?:boolean;accountType?:"residential"|"commercial";contacts?:{name:string;email:string;phone:string;contact_role:string}[];addresses?:string[];branchId?:string;id:string;name:string;email:string;phone:string;address:string};
export type StockItem={reservedQuantity?:number;branchId?:string;skuId?:string;locationId?:string;id:string;part:string;sku:string;trade:Trade;truck:string;quantity:number;threshold:number};

export type Property={id:string;customerId:string;name:string;address:string;revision:number};
export type Equipment={id:string;propertyId:string;name:string;trade:Trade;model:string;serial:string};
export type DiscountRule={kind:'labor'|'material'|'other';service:'repair'|'maintenance';percent:number};
export type PlanConfiguration={trades:Trade[];termDays:number;visits:number;discountRules:DiscountRule[]};
export type ServicePlan=PlanConfiguration&{id:string;name:string;revision:number};
export type ServiceMembership={id:string;revision:number;customerId:string;customer:string;propertyId:string;property:string;equipmentId:string;equipment:string;trade:Trade;planId:string;plan:string;status:string;paymentStatus:string;starts:string;ends:string;remaining:number;due:string[];renewalSoon:boolean;configuration:Partial<PlanConfiguration>;history:{id:string;jobId?:string;amount:number;reason:string;date:string}[]};
export type Coverage={eligible:boolean;reason:string;remaining:number;membershipId?:string;maintenanceEligible?:boolean;discountRules:DiscountRule[]};
export type ChargeLine={description:string;kind:'labor'|'material'|'other';quantity:number;unit_cents:number;discount_eligible?:boolean;treatment?:string;sku_id?:string};
export type ChargeProposal={totalCents:number;lines:{description:string;kind:string;grossCents:number;discountPercent:number;discountCents:number;totalCents:number}[]};
export type StockMovement={id:string;part:string;location:string;locationId:string;jobId?:string;kind:string;quantity:number;delta:number;reason:string;date:string};
