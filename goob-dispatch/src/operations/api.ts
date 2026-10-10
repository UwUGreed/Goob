export type Role = 'owner' | 'billing_reviewer' | 'technician' | 'dispatcher';
export type Billing = { currency: string; labor_cents: number; installed_part_cents: number; discount_cents: number; tax_cents: number; original_cents: number; approved_cents: number; flags: {rule: string; evidence: string; potential_cents: number}[] };
export type Proposal = { id: string; state: string; payload: string };
export type OperationsState = {
  simulation: boolean;
  job: {id: string; status: string; revision: number};
  crm: {customers: {id: string; name: string; branch: string}[]; equipment: {id: string; name: string; property: string; trade: string}[]} | null;
  agreements: {agreements: {id: string; equipment: string; terms: string; start: string; end: string; remaining: number}[]; ledger: {id: string; source: string; amount: number}[]} | null;
  inventory: {id: string; name: string; available: number; cost: number; price: number}[] | null;
  proposals: Proposal[];
  invoices: {id: string; state: string; snapshot: string}[];
  audit: {id: string; actor: string; at: string; reason: string; before_value: string; after_value: string}[];
};
export type ChangeSet = {provider: string; completed_work: string; installed: number; unused_return: number; agreement: string; billing: Billing};
export async function operationsApi<T>(path: string, role: Role, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/${path}`, {method: body === undefined ? 'GET' : 'POST', headers: {'Content-Type':'application/json','X-Demo-Role':role}, ...(body === undefined ? {} : {body:JSON.stringify(body)}), signal});
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Operations service is unavailable. Start the API with python3 -m operations.server.');
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Operations command failed.');
  return data as T;
}
