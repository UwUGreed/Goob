# Operations vertical slice

## Before implementation: existing system and stack
Latest origin/main f86662f contains the React/TypeScript dispatch simulation. The other local folders were empty scaffolding. The initial operations commit preserved dispatch unchanged. At the user's subsequent request, the existing React frontend now includes a Work review dialog backed by the Python standard-library HTTP/PostgreSQL API. Dispatch simulation, map, routing and job records remain intact. The API serves the built React workspace; Vite proxies API calls during development. The original plain browser UI remains at /operations as a fallback. The server now requires private Tiger Cloud credentials; it has no SQLite fallback.

## Module/dependency map
The explicit registry declares dependencies, permissions, navigation, settings, optional integrations and event names. CRM owns customer/equipment access. Agreements depends on CRM and owns eligibility/benefit ledger. Inventory owns stock and movements. Billing owns calculations and invoice snapshots. Workflow depends on CRM, agreements, inventory and billing, and orchestrates their interfaces transactionally; it owns jobs, proposals and approval history. Readiness consumes inventory. No domain module writes another module's tables. No async event delivery occurs; work.approved.v1 is a reserved future event contract, not a published integration.

## Model and invariants
Tenant-scoped customers have branch identifiers, properties and equipment. Frozen agreement terms scope coverage to exact property/equipment/trade/date. Signed benefit entries track opening grant and consumption. Stock movements distinguish issued stock, installation disposition and unused returns. Proposals carry job revisions; approved drafts preserve calculated invoice snapshots. Audit records actor, time, source, reason and before/after evidence.

Approval uses BEGIN IMMEDIATE, rechecks coverage, revision, issued stock and benefit balance, and commits work, stock, benefits, invoice and history atomically. Proposal IDs make approval retries idempotent. Stale concurrent proposals cannot consume twice. Money is integer cents, with half-up percentage rounding. Issued invoice mutation is unsupported. Module configuration preserves data, checks dependency closure and is enforced on server commands and reads.

## Explicit assumptions
One fictional tenant and branch. Role selection simulates identity; this is not production authentication. Owner/billing reviewer approve; technician proposes; dispatcher reads. HVAC labor has a 10% discount, materials none, tax zero pending jurisdiction rules. Maintenance consumes one visit. Two capacitors were already issued: one installed and one usable spare returned. Stock cost is fixed seed cost ($18), selling price $45, not FIFO accounting. Missing/expired/overlapping coverage blocks approval. Plan mutations and damaged returns are unsupported. Pricing is an unvalidated configurable $1,000/month hypothesis separate from invoice calculations.

## Phased delivery
1. Customer → equipment/coverage → proposed work/materials → billing review → employee approval/history, with deterministic simulated AI.
2. Read-only readiness blocker and uncertain migration preview; implement real reservations, technician qualification checks, approved imports and reversal commands next. Dispatch and operations share the frontend navigation; their fictional datasets remain explicitly separate with no synchronization.
3. Agreement lifecycle, inventory receiving/transfers/reservations, communication drafts, outbox and adapter contracts.
4. Real authentication, complete branch/trade authorization, isolated files/jobs/caches, provider integrations and production hardening.

Current limitations: properties are labels on equipment rather than full contact/address entities. No production AI, messaging, Ply, payments, accounting, migration writes, dispatch integration, or comprehensive readiness engine. No real customers or messages. Purchasing, full offline operation, advanced automation and construction management remain roadmap items. Export is a tenant-scoped JSON snapshot; future schema changes require backed-up, versioned database migrations. This demo initializes only schema v1 and never silently upgrades an existing schema.
