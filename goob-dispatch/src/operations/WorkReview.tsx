import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, ClipboardCheck, Download, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';
import { operationsApi, type Billing, type ChangeSet, type OperationsState, type Role } from './api';
import './work-review.css';
const money = (cents: number) => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(cents/100);
export function WorkReview() {
  const [role,setRole] = useState<Role>('owner');
  const [state,setState] = useState<OperationsState|null>(null);
  const [busy,setBusy] = useState(false), [loading,setLoading] = useState(true), [error,setError] = useState(''), [notice,setNotice] = useState('');
  const mounted = useRef(true);
  const load = useCallback(async (signal?: AbortSignal) => {
    const next = await operationsApi<OperationsState>('state',role,undefined,signal);
    if(mounted.current) setState(next);
  },[role]);
  useEffect(()=>{mounted.current=true; const controller=new AbortController();setLoading(true);setError('');setNotice('');setState(null);load(controller.signal).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>{mounted.current=false;controller.abort();};},[load]);
  async function command(path: string, body: unknown) {
    setBusy(true);setError('');setNotice('');
    try {await operationsApi(path,role,body);await load();if(mounted.current)setNotice(path==='approve'?'Approved: confirmed work, returned stock, covered visit and draft billing saved together.':'Proposal ready. Review the evidence before confirming.');}
    catch(e){if(mounted.current)setError(e instanceof Error?e.message:'Command failed.');}
    finally{if(mounted.current)setBusy(false);}
  }
  async function download() {
    setBusy(true);setError('');
    try {const data=await operationsApi<OperationsState>('export',role);const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='goob-operations-export.json';link.click();URL.revokeObjectURL(url);}
    catch(e){setError(e instanceof Error?e.message:'Export failed.');}finally{setBusy(false);}
  }
  const proposal=state?.proposals.filter(p=>p.state==='pending').at(-1);
  const changes:ChangeSet|undefined=proposal?JSON.parse(proposal.payload):undefined;
  const approved=state?.job.status==='Confirmed';
  const bill:Billing|undefined=state?.invoices[0]?JSON.parse(state.invoices[0].snapshot):changes?.billing;
  const canPropose=role!=='dispatcher', canApprove=role==='owner'||role==='billing_reviewer';
  return <div className="work-review">
    <div className="work-review-intro"><div><span className="small-label">CUSTOMER → WORK → BILLING → HISTORY</span><p>Confirm the work. Explain the bill.</p></div><label>Demo role<select aria-label="Operations demo role" value={role} disabled={busy} onChange={e=>setRole(e.target.value as Role)}><option value="owner">Owner</option><option value="billing_reviewer">Billing reviewer</option><option value="technician">Technician</option><option value="dispatcher">Dispatcher</option></select></label></div>
    <div className="work-review-disclosure"><Sparkles size={16}/><span>Fictional operations scenario · Fixed AI proposal and simulated identity. Dispatch visits run separately; this review does not complete a map visit.</span></div>
    {error&&<div className="work-review-error" role="alert">{error}<button className="secondary-button" disabled={busy||loading} onClick={()=>{setError('');setLoading(true);load().catch(e=>setError(e.message)).finally(()=>setLoading(false));}}><RefreshCw size={14}/> Retry connection</button></div>}
    {notice&&<p className="work-review-success" role="status"><Check size={16}/>{notice}</p>}
    {loading&&<p role="status">Loading operations records…</p>}
    {state&&<div className="work-review-grid"><div>
      <section className="work-review-card"><h3>Customer & equipment</h3><strong>{state.crm?.customers[0]?.name||'Customer module unavailable'}</strong><p className="muted">Two properties · shared HVAC and electrical customer record</p>{state.crm?.equipment.map(e=><div className="work-review-equipment" key={e.id}><strong>{e.name}</strong><p>{e.property} · {e.trade}</p><span className={`badge ${e.id==='hvac-1'?'ready':'neutral'}`}>{e.id==='hvac-1'?'Named equipment on Care v1':'Excluded from Care v1'}</span></div>)}</section>
      <section className="work-review-card"><div className="work-review-card-heading"><h3>Work confirmation</h3><span className={`badge ${approved?'ready':'neutral'}`}>{state.job.status}</span></div><p>“Finished maintenance on the upstairs unit. Installed one capacitor and returned the spare.”</p><p className="muted">This fixed example produces a reviewable proposal. Preparing it changes no stock, benefits or invoices.</p>{changes&&!approved&&<><div className="work-review-row"><span>Completed work</span><strong>HVAC maintenance</strong></div><div className="work-review-row"><span>Installed / unused return</span><strong>{changes.installed} / {changes.unused_return}</strong></div><div className="work-review-row"><span>Covered benefit consumption</span><strong>1 visit</strong></div></>}
      {!approved&&<div className="work-review-actions"><button className="secondary-button" disabled={busy||!canPropose} onClick={()=>command('propose',{})}><Sparkles size={15}/> Prepare demo proposal</button>{proposal&&<button className="primary-button" disabled={busy||!canApprove} onClick={()=>command('approve',{id:proposal.id})}><ShieldCheck size={15}/> Confirm work & approve draft</button>}</div>}{!canApprove&&!approved&&<p className="muted">Owner or billing reviewer permission is required to approve.</p>}{approved&&<p className="work-review-success"><ClipboardCheck size={16}/> Work confirmed. The approved draft is preserved below.</p>}</section>
      <section className="work-review-card"><h3>Approval history</h3>{state.audit.length===0?<p className="muted">No employee-approved changes yet.</p>:state.audit.map(a=><div key={a.id}><p><span className="badge ready">Employee approved</span> {a.actor} · {new Date(a.at).toLocaleString()}</p><p>{a.reason}</p><details><summary>Before / after evidence</summary><pre>{JSON.stringify({before:JSON.parse(a.before_value),after:JSON.parse(a.after_value)},null,2)}</pre></details></div>)}<button className="secondary-button" disabled={busy} onClick={download}><Download size={14}/> Export operations records</button></section>
    </div><div>
      <section className="work-review-card"><h3>{approved?'Approved draft':'Billing review'}</h3><div className="work-review-total">{money(bill?.approved_cents??24000)}</div><p className="muted">{bill?'Original draft: $240.00 · reviewed amount above':'Original draft · prepare a proposal to inspect corrections'}</p>{bill&&<><div className="work-review-row"><span>Labor</span><strong>{money(bill.labor_cents)}</strong></div><div className="work-review-row"><span>Installed capacitor</span><strong>{money(bill.installed_part_cents)}</strong></div><div className="work-review-row"><span>Eligible labor discount</span><strong>−{money(bill.discount_cents)}</strong></div>{bill.flags.map(f=><div className="work-review-flag" key={f.rule}><strong>{f.rule==='AGREEMENT_LABOR_DISCOUNT'?'Eligible discount missing':'Unused return charged'}</strong><span className="badge neutral">{approved?'Approved correction':'Potential discrepancy'}</span><p>{f.evidence}</p></div>)}</>}<p className="muted">Zero demo tax · no payment collected or invoice issued.</p></section>
      <section className="work-review-card"><h3>Coverage & benefit ledger</h3>{state.agreements?.agreements.map(a=><div key={a.id}><p>{a.terms}</p><span className="badge ready">{a.remaining} remaining {a.remaining===1?'visit':'visits'}</span><p className="muted">{a.start} → {a.end}</p></div>)}{state.agreements?.ledger.map(l=><div className="work-review-row" key={l.id}><span>{l.source}</span><strong>{l.amount>0?'+':''}{l.amount}</strong></div>)}</section>
      <section className="work-review-card"><h3>Return visit <span className="badge urgent">Blocked preview</span></h3><p>Replacement control board is unavailable and unreserved.</p>{state.inventory?.map(i=><div className="work-review-row" key={i.id}><span>{i.name}</span><strong>{i.available} in stock</strong></div>)}<p className="muted">Read-only scenario. Qualification and complete prerequisite checks remain planned.</p></section>
      <section className="work-review-card"><h3>Migration review <span className="badge neutral">Uncertain preview</span></h3><p>Legacy record MIG-017 says “2 visits”; supporting service history is missing.</p><p className="muted">No balance imported. Staff must reconcile source evidence before approving an opening balance.</p></section>
    </div></div>}
  </div>;
}
