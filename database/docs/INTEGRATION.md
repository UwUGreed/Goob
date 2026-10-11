# Future application integration — not performed

The website uses the existing cloud `goob` schema. SQLite fallback and startup initialization/seeding have been removed. The separately integrated v1 backend uses `public.*_v1`. React dispatch remains local simulation. These new records are not wired into any API/UI/AI tool. The repository already contained uncommitted changes from the earlier connection work; this task preserves them.

## Resolve the legacy/new-schema boundary

Legacy tables use text tenant `demo` and text IDs, loose text properties, unstructured snapshots and no comprehensive FKs. The foundation uses UUID organizations and structured entities. Do not point existing SQL at the new schema or rename/drop legacy tables. A later, separately authorized project needs:

1. A source inventory and backed-up snapshot with immutable source identifiers.
2. Explicit legacy tenant/customer/property/equipment/role mappings to new UUIDs.
3. Staging records preserving original values, unknown balances, validation issues and staff decisions.
4. A dry-run reconciliation of row counts, stock/benefit balances and immutable invoice/audit history.
5. Approved backfill with idempotency keys and source provenance; no implicit zero for unknown stock/benefits.
6. Application adapters and a controlled cutover, followed by read/write verification and a backup-based recovery plan.

No customer data from the earlier SQLite-to-cloud demo was imported into this new foundation. No existing tables, records, secrets or deployment configuration were changed.

## Identity, permissions and tenant access

Replace simulated role headers with verified external identity. Map provider + opaque subject into org_members; resolve roles/permissions and tenant context server-side. Use a limited runtime role and a separately managed migration role. Design and test RLS before granting the new schema to application traffic, including pooled connection cleanup and tenant switching. The administrative development account is not a production access model.

## Commands and transactional boundaries

Implement explicit business commands, not a universal workflow engine. Each command must authorize actor/tenant, check expected version/state, acquire account locks in deterministic order, revalidate eligibility, and write operational changes plus audit within one transaction. Resolve reservations and post matching consumption together. Retry deadlocks/serialization failures with stable idempotency keys. Reserve/consume on the property-local date; do not convert a due date to UTC midnight and silently shift the business day.

Required command-level rules include:

- Module dependency closure, qualification validity, appointment/time-entry overlap and technician availability.
- Equipment relocation/replacement and reapproval of impacted coverage; agreement overlap selection and supplemental plan-specific conditions.
- Effective price selection/overlap, unit conversion, supported currencies/minor units, selected cost policy and legitimate stock-return reconciliation.
- Actual employee approval authority, source document interpretation and opening-balance reconciliation.
- Invoice semantic review against confirmed work, required material/benefit links, acceptance/consent snapshots, official invoice numbering, cumulative credit limits and jurisdiction-valid tax snapshots.
- Valid state transitions for jobs, schedules, import batches, proposals and integration attempts; corresponding status/audit events.
- Validated polymorphic target pointers in AI/import/audit/integration records; never execute raw proposed JSON or table names.
- No secret material in metadata, error_detail, message drafts, source excerpts or audit changes; secure object storage and file access.

Database guards cover the documented relational, arithmetic, immutability and capacity invariants. They do not prove these application policies work.

## Intentionally deferred infrastructure/features

No authentication provider, application endpoints, dashboard, dispatch algorithm, AI model call, message delivery, background task, tax engine, payment processor, accounting sync, supplier invoice flow, purchase order flow, Ply integration, external secrets manager or upload service was implemented. The schemas contain references/records for future integration where requested.

No Timescale hypertable, retention policy, continuous aggregation, vector index, search extension, production RLS or paid service was provisioned. Introduce these only for a measured need and an authorized deployment plan. Real inventory costing (FIFO/weighted average) and multi-minor-unit currency rules require new versioned design/migrations before claiming support.
