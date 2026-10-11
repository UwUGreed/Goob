import { useResource } from './api';
import { Coverage } from './Coverage';
import { StockLedger } from './StockLedger';
import { JobReview } from './JobReview';
import { Migrations } from './Migrations';
import { Growth } from './Growth';
import './expansion.css';

export function Expansion({page,go}:{page:string;go:(path:string)=>void}){
  const me=useResource<{branches:string[];role:string}>('/me');
  if(me.loading)return <section className="expansion-page" role="status">Loading workspace access…</section>;
  if(me.error||!me.data?.branches.length)return <section className="expansion-page" role="alert">{me.error||'No branch is available for this account.'}</section>;
  const branchId=me.data.branches[0];
  if(page==='growth')return <Growth branchId={branchId} go={go}/>;
  if(page==='memberships')return <Coverage branchId={branchId}/>;
  if(page==='stock-ledger')return <StockLedger branchId={branchId} go={go}/>;
  if(page==='work-review')return <JobReview go={go}/>;
  if(page==='migration')return <Migrations branchId={branchId}/>;
  return <section className="expansion-page">Page not found.</section>;
}
