import { useResource } from './api';
import { Coverage } from './Coverage';
import { StockLedger } from './StockLedger';
import { JobReview } from './JobReview';
import { Migrations } from './Migrations';
import { Growth } from './Growth';
import type { Simulation } from '../types';
import type { Action } from '../simulation';
import './expansion.css';

export function Expansion({page,go,state,dispatch}:{page:string;go:(path:string)=>void;state:Simulation;dispatch:(action:Action)=>Promise<boolean>}){
  const me=useResource<{branches:string[];role:string}>('/me');
  if(me.loading&&!me.data)return <section className="expansion-page" role="status">Loading workspace access…</section>;
  if(me.error||!me.data?.branches.length)return <section className="expansion-page" role="alert">{me.error||'No branch is available for this account.'}</section>;
  const branchId=me.data.branches[0];
  if(page==='growth')return <Growth branchId={branchId} go={go} state={state}/>;
  if(page==='memberships')return <Coverage branchId={branchId} initialId={window.location.pathname.split('/')[2]||''} state={state} dispatch={dispatch}/>;
  if(page==='stock-ledger')return <StockLedger branchId={branchId} go={go} state={state}/>;
  if(page==='work-review')return <JobReview go={go} state={state}/>;
  if(page==='migration')return <Migrations branchId={branchId}/>;
  return <section className="expansion-page">Page not found.</section>;
}
