import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CustomerMembership, JobMembership } from './CustomerMembership';
import type { Job, ServiceMembership, Simulation } from '../types';

const membership = {id:'care',customerId:'customer-1',plan:'HVAC Care',status:'active',property:'Home',equipment:'Heat pump',remaining:2,paymentStatus:'paid'} as ServiceMembership;
const state = {memberships:[membership],jobs:{},technicians:{},speed:1} as Simulation;
const job: Job = {id:'repair',title:'Repair',address:'Rental',trade:'HVAC',customer:'Alex',customerId:'customer-1',description:'Repair',part:'No parts required',node:'0-0',time:'Today',coverage:{eligible:false,reason:'Different property',remaining:0,discountRules:[]}};

describe('customer membership across views', () => {
  it('keeps account membership visible without marking an uncovered visit covered', () => {
    const html = renderToStaticMarkup(<JobMembership state={state} job={job}/>);
    expect(html).toContain('1 active membership');
    expect(html).toContain('Visit not covered');
    expect(html).toContain('Different property');
    expect(html).not.toContain('covers this visit');
  });
  it('never borrows another customer’s membership', () => {
    expect(renderToStaticMarkup(<CustomerMembership state={state} customerId="other"/>)).toContain('No membership');
  });
  it('reflects cancellation and updated remaining visits from the next snapshot', () => {
    const changed = {...state,memberships:[{...membership,status:'canceled',remaining:0}]};
    const html = renderToStaticMarkup(<CustomerMembership state={changed} customerId="customer-1"/>);
    expect(html).toContain('Membership canceled');
    expect(html).toContain('0 visits remaining');
    expect(html).not.toContain('active membership');
  });
  it('names the actual covered plan rather than a different enrollment', () => {
    const covered = {...job,coverage:{eligible:true,membershipId:'care',reason:'Covered equipment',remaining:2,discountRules:[]}};
    expect(renderToStaticMarkup(<JobMembership state={state} job={covered}/>)).toContain('HVAC Care covers this visit');
  });
});
