# Database contracts and limits

## Tenant and identity integrity

All business FKs are tenant-qualified. An organization cannot reference another organization's customer, work, inventory, agreement, identity membership, or invoice. IDs, tenant IDs and creation timestamps cannot be changed after insertion. This prevents cross-organization links; it does **not** prevent an overprivileged connection from selecting or directly inserting another organization's otherwise valid records.

No RLS policies are enabled because the current application uses an administrative-style connection and has no trusted authenticated tenant context. RLS under that model would either be bypassed by ownership privileges or break existing access. Before application integration, introduce a non-owner runtime role, separate migration credentials, trusted transaction-local tenant context, `USING` and `WITH CHECK` policies, and tests proving the context cannot come from an untrusted header. Keep migration/fixture tooling out of the runtime role. No role, policy, or grant on existing application objects changed here.

All deletion FKs are RESTRICT, not destructive cascades. Tooling's demo history deletion exception requires a matching known tenant, isolated development database name/comment and transaction-local reset setting. It is an operator guard, not protection against the object owner or a superuser. The standalone reset adds a complete fixture manifest comparison and explicit confirmation.

## Agreements

Plans have immutable published versions and benefit definitions. Definitions cannot be appended to a version once an agreement references it. Agreements freeze the version, billing customer and text terms snapshot; renewals/changes are separate history records. The mutable lifecycle/date/renewal settings still require audited employee commands during integration.

Every coverage row names a property and exactly one scope:

- `property`: property-wide; equipment and trade IDs must both be absent.
- `equipment`: one explicit equipment unit at that property; trade ID absent. A trigger validates current equipment/property alignment when coverage is inserted/changed.
- `trade`: one explicit trade at that property; equipment ID absent.

`service_scope=all` explicitly covers all services within the selected scope; `specific` requires a service ID. Benefit definitions use the same explicit all/specific service scope. Service/trade compatibility is checked for equipment/trade scopes. Equipment relocation does not rewrite past terms. Reassessment of coverage after relocation/replacement is a future employee-reviewed command.

Eligibility, remaining balance, reserved balance and available balance are distinct. The `benefit_job_eligible` SQL function tests an explicit account/job/date against approved active agreement dates, benefit period, task service and coverage scope. Insert triggers apply this gate to active reservations and consumption, using the service property's timezone. It does not choose among overlapping agreements or implement every plan-specific business condition. The caller must resolve ambiguity and enforce qualification/approval conditions before authoritative use.

Known remaining balance is the signed ledger sum; active reservations are summed separately; available = remaining − reserved. Unknown migrated balance returns NULL remaining/available. Reserving or consuming an unknown balance is rejected. An expired agreement can still retain a known historical balance but fails eligibility. Grants, consumption, expiration, exact reversals and approved adjustments are append-only; idempotency and reversal references are unique. Negative quantities are allowed only in appropriate entry kinds. Consumption references confirmed work and matching job. A reservation resolves explicitly to released or consumed; it cannot be erased, resized, reparented, reopened or changed after resolution. Consumption references must match account, job and quantity and cannot be reused by another reservation.

## Stock and costing

Materials have an explicit base unit. Every stock account identifies one material/location; identity cannot mutate. On-hand is a signed sum of movements, not an editable stock column. Reserved sums only active reservations, and available subtracts reserved from on-hand. Fractional quantities use numeric(18,4); conversions between units require a later explicit conversion policy.

A transfer is **one row containing both source and destination accounts** and one quantity/cost, so its legs always balance. Accounts must hold the same material; endpoints cannot be identical. Opening/receipt/usable-return movements enter a destination; consumption leaves a source and links confirmed work. Damaged returns must enter a quarantine location. Opening movements require a source staging-record reference. Staff approval is represented by a required member FK; role authorization and source approval semantics remain application responsibilities.

Initial costing is an explicitly supplied **standard unit-cost snapshot per posted movement**, numeric(19,4) with ISO currency. Transfers and their reversals retain the same unit cost. This is not FIFO, weighted-average, landed-cost valuation, or supplier invoice reconciliation. Choosing/approving the correct source cost and comparing currencies is future integration work. There is no accounting valuation report that sums mixed currencies.

Movements cannot be edited or deleted. Exact reversals swap endpoints and preserve material, quantity, cost and currency. A movement can be reversed once; corrections beyond that require explicit adjustments with a reason and approver. Usable/damaged return reconciliation against the originating issued/consumed quantity requires a future operational command; a standalone fixture return is not proof of that rule. All posted movements require idempotency keys.

## Concurrency contract

Use ordinary READ COMMITTED transactions for write commands. BEFORE triggers lock benefit or stock account rows. Multi-account transfers lock source/destination in UUID order. Deferred constraint triggers validate the final committed on-hand/remaining and available balances, allowing reservation resolution and consumption in the same transaction in either order. Simultaneous reservations of the same balance serialize; the later one sees the first committed reservation and cannot overdraw. A balance-read followed by an unchecked application write is not sufficient.

A command touching several accounts should acquire **all** needed account locks in sorted UUID order before its first movement/reservation. Multi-row batches that ignore that order can deadlock; retry the entire transaction on `40P01`/`40001` with the same idempotency keys. This foundation does not include application retries, command dispatch, or a stored-procedure workflow engine. Higher isolation levels need corresponding retry tests before adoption. Eligibility reads across mutable agreement/scope/job rows also need a coordinated command locking policy before integrating concurrent term changes.

Unique keys block duplicate posted movements and consumed reservation links. Tooling uses its own transaction advisory lock, table locks for seed/reset, bounded connection/statement/lock timeouts, and migration checksums. These do not replace runtime authorization.

## Exact billing

Quantities: numeric(18,4). Unit prices/costs/rates: numeric(19,4). Posted money/totals: numeric(19,2). Currency: explicit three-letter uppercase code. Every numeric field rejects NaN. Currency validity/minor-unit support must be checked during integration; this baseline's **two-decimal, nonnegative charge convention** is USD-style and must not be applied unchanged to zero-/three-decimal currencies.

Per line, use PostgreSQL numeric `round(...,2)` (ties away from zero; half-up for these nonnegative charges):

1. Base = round(quantity × unit_price, 2).
2. Subtract explicit line discount_amount.
3. Tax = round((base − discount_amount) × tax_rate, 2).
4. Line total = base − discount_amount + tax_amount.

Constraints enforce line arithmetic and nonnegative results. Draft headers may intentionally disagree with line totals; `bill_invoice_reconciliation` exposes this. Issuance requires at least one line, matching header subtotal/discount/tax/total, no open review flags, and an immutable issued snapshot with exactly the stored ordered lines, currency and total. Issued header/lines cannot mutate. Corrections/credits are separate append-only records with matching currency, reason and approver; cumulative credit limits remain an application rule. Quote acceptance retains an immutable accepted scope and quote snapshot. Verifying customer consent, snapshot completeness and accepted quote content is a future employee command.

Catalog edits do not rewrite the copied prices, rates, discount/tax snapshots or issued/accepted snapshots. Review flag resolution requires a reviewer, resolution text and time. Tax jurisdiction/rate values are input snapshots, not tax-engine outputs. No payments or card data exist. Membership billing schedules are separate from job invoices.

## AI, imports, audit and reporting

AI runs, extracted terms/evidence, immutable proposed actions, staff decisions and execution outcomes are separate from authoritative ledgers. A successful outcome must reference an approved decision for the same change set. An import outcome requires an accept/merge decision on the same staging record. These constraints do not execute a proposal, import, or external command. Future commands must validate target/version/permission and write audit in the same transaction.

Staging stores original values verbatim as JSON with source identifiers/files, mappings, issues, duplicate candidates and staff decisions. Opening ledger provenance points to staging rows; no real source records are imported. Unknown balances stay explicitly unknown. Polymorphic outcome/evidence pointers are informational and do not create generic executable relationships.

Operational events are ordinary append-only PostgreSQL rows with unique tenant idempotency keys and timestamptz, plus concrete optional job/movement/invoice FKs. Example reports aggregate fictional events. There is no producer, scheduler, retention, rollup, hypertable, integration connector, message sender or payment side effect.
