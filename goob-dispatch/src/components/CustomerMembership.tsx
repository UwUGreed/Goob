import type { Job, ServiceMembership, Simulation } from '../types';

export function customerMemberships(state: Simulation, customerId?: string): ServiceMembership[] {
  return customerId ? (state.memberships ?? []).filter(m => m.customerId === customerId) : [];
}

export function CustomerMembership({state, customerId}: {state: Simulation; customerId?: string}) {
  const memberships = customerMemberships(state, customerId);
  const active = memberships.filter(m => m.status === 'active');
  const label = active.length ? `${active.length} active membership${active.length === 1 ? '' : 's'}`
    : memberships.length ? `Membership ${[...new Set(memberships.map(m => m.status))].join(' / ')}`
    : 'No membership';
  const detail = memberships.map(m => `${m.plan}: ${m.status} · ${m.property} · ${m.equipment} · ${m.remaining} visits remaining · Payment: ${m.paymentStatus}`).join('\n');
  return <span className={`customer-membership ${active.length ? 'active' : 'inactive'}`} title={detail || 'No customer membership recorded.'} aria-label={detail ? `${label}. ${detail}` : label}>{label}</span>;
}

export function JobMembership({state, job}: {state: Simulation; job: Job}) {
  const membership = state.memberships?.find(m => m.id === job.coverage?.membershipId);
  return <span className="job-membership"><CustomerMembership state={state} customerId={job.customerId}/><span className={`job-coverage ${job.coverage?.eligible ? 'covered' : 'uncovered'}`} title={job.coverage?.reason}>{job.coverage?.eligible ? `${membership?.plan ?? 'Membership'} covers this visit` : 'Visit not covered'}</span></span>;
}
