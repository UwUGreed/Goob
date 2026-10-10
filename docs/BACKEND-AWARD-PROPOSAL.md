# Goob backend proposal for the selected hackathon categories

Prepared October 10, 2026. Proposal only; these capabilities are not implemented by this document.

Branch: `codex/backend-award-plan`. Base: `c96ae88`.

## Scope and ownership

Build the operational backend that supports Goob's expansion from one trade into multiple trades, with Tiger Data storage, Gemini text extraction, and a Vultr deployment. Preserve the existing approval model: AI proposes; explicit rules and authorized people control records, inventory, benefits, and billing.

The frontend and voice dispatch are being developed separately. They are outside this work's ownership, including code, configuration, dependencies, prompts, tests, voice integrations, audio storage, playback, routing, technician assignment, scheduling behavior, and dispatch state transitions. This proposal does not implement or redesign those systems.

- Protected: all of `goob-dispatch/`, `operations/static/`, and any current or newly added frontend/voice/dispatch files regardless of their folder.
- Preserve the existing local demo server and `/api/state`, `/api/propose`, `/api/approve`, `/api/export`, and `/api/modules` contracts while other teams use them.
- Add a separately launched, versioned backend service. Do not expose the existing demo role-header server publicly.
- New backend API contracts are proposals for coordination, not instructions to change the frontend or voice implementation. Identity, job identifiers, and shared field ownership must be agreed before clients switch.
- Persistent dispatch scheduling is deferred to its owner. General operational job records can be implemented without assigning technicians, changing routes, or modifying a dispatch state machine.
- ElevenLabs is already owned by the voice team. Track its award dependency in documentation; add no competing implementation or voice-specific endpoint.
- Pricing remains undecided. Do not carry the seeded $1,000/month value into a new tenant, migration, pitch, or subscription contract. Job invoice amounts are separate from platform pricing.

This branch adds only this proposal. Implementation, account provisioning, deployment, and production data imports have not occurred.

## Award coverage

| Selected category | Proposed deliverable | Evidence for the presentation | Ownership |
|---|---|---|---|
| Best Use of Hardware | Proposed scanner/phone inventory workflow, explanatory mockup, equipment assumptions, cost estimate, and pilot plan. | Show how an identified SKU becomes a reviewed warehouse/truck/job movement. State clearly that hardware is proposed. | Pitch documentation here; no physical build or frontend work. |
| Most Startup Ready — Boyd Innovation Center | Customer problem evidence, narrow initial market, competitive comparison, subscription hypothesis, acquisition plan, pilot criteria, and operating cost model. | An authorized real example, accurately described customer commitment, and a credible path to testing willingness to pay. | Product/business documentation. |
| Best Use of ElevenLabs | Working spoken job briefings. | Live provider-backed speech demonstrated by the voice team. A placeholder is not completion. | Existing voice team only. |
| Best Use of Gemini API | Actual technician text-note extraction into reviewable work, material, and follow-up suggestions. | New text inputs produce different validated proposals, with source evidence and explicit unknowns. | Backend integration here. |
| Best Use of Tiger Data | Hosted PostgreSQL operational records plus useful time-based operational analysis. | Persistence across restarts; trace a job through its ledger and audit events; report blocker duration or material movement totals. | Backend persistence here. |
| Best Use of Vultr | Deployed authenticated backend with repeatable deployment and recovery instructions. | HTTPS API exercised by a scripted workflow, with records persisting in Tiger Data. | Backend deployment here. |

The user's selected-category screenshot defines these six targets. Hardware can be a proposed integration according to the user's clarification. This plan does not invent judging weights, guarantee qualification, or assume awards stack. The official MLH page confirms the four selected sponsor technology categories; local hardware/startup criteria come from the user's materials.

## Current baseline

The repository has a React dispatch simulation and a Python/SQLite operations example. The backend has one fixed job, fixed material quantities, fixed invoice calculations, a simulated identity header, and a deterministic AI placeholder. Approval has useful atomicity, retry protection, staleness checks, and audit history. Nine existing backend tests passed during the earlier inspection.

Keep those invariants while replacing demo assumptions. In particular:

- Remove `job-1`, fixed agreement IDs, fixed prices, and fixed part IDs from the new operational services.
- Coverage must use the job's service date and the applicable agreement version, rather than always using today's date.
- An uncovered job must be distinguishable from a covered job with an exhausted benefit and from unknown coverage. A legitimate nonmember job should be able to proceed through an explicitly approved billable path.
- Material installation is disposition of issued stock; it must not deduct warehouse stock a second time.
- The current registry's readiness entry is not a readiness implementation. Migration preview and static dispatch inventory also do not constitute imports or reservations.

## Proposed code boundaries

The new service initially lives alongside the local demo so it does not force frontend or voice changes. Once owners adopt it, schedule a separate cutover and retirement of the demo path. Do not build synchronization between two writable sources of operational truth.

```text
operations/
  api_v1/                  New backend entrypoint, routes, schemas, errors
  persistence/             PostgreSQL sessions, repositories, transaction scope
  migrations/              Ordered, versioned database migrations
  domain/                  Generalized business modules for the new service
    identity.py            User membership, tenant/branch access policies
    crm.py                 Customers, contacts, properties, equipment
    jobs.py                Operational job records, notes, revision history
    agreements.py          Versioned terms and benefit ledger
    inventory.py           Locations, movements, reservations, adjustments
    billing.py             Draft lines, rule findings, approved snapshots
    workflow.py            Proposal review and atomic confirmation
    readiness.py           Read-only prerequisites and evidence
    imports.py             Staging, matching, reconciliation, commit
    opportunities.py       Reviewed follow-up needs and conversion to jobs
    analytics.py           Tenant-scoped event and ledger reporting
  integrations/
    gemini.py              Text-only provider adapter
  workers/                 Bounded AI tasks and later outbox processing
scripts/
  backend_demo.py          API-only demonstration using fictional records
  reconcile_demo_export.py Validated one-way import of the local demo snapshot
tests/backend_v1/          Domain, API, PostgreSQL, and integration tests
deploy/backend/           Container, deployment settings, health/recovery runbook
docs/backend/             API examples, ownership, setup, award evidence
docs/pitch/               Hardware concept and startup evidence materials
```

Proposed implementation choice: FastAPI/Pydantic for the new API, SQLAlchemy with psycopg for PostgreSQL access, and Alembic for migrations. Pin versions during implementation. Keep business rules independent of HTTP/provider clients. This is a small modular service, not a separate deployed microservice for each module.

Existing `operations/modules/`, `db.py`, and `server.py` remain the local demo during transition. Reuse and generalize their tested rules in the new service rather than expanding its hardcoded SQL in place. New dependencies must not affect the frontend package or lockfile.

## Work packages and acceptance criteria

### P0-A. Tiger Data persistence and migration foundation

Create relational records for tenants, branches, user memberships, customers, contacts, properties, equipment, operational jobs, source notes, proposals, agreements and term versions, benefits, SKUs, locations, movements, reservations, invoice drafts, audit events, and import batches. Implement additional tables alongside their owning work package rather than creating unused schemas up front.

- Use tenant-scoped foreign keys so references cannot cross company boundaries. Represent property/equipment links explicitly instead of using address labels as identity.
- Use a restricted application database role, TLS, connection pooling, and explicit transaction boundaries. Put credentials in deployment secrets, never the repository.
- Preserve integer minor-unit money with currency, deliberate quantity units, UTC timestamps, service dates, and user timezone context.
- Scope idempotency keys by tenant and operation; store request fingerprints so the same key with a different payload is rejected.
- Use PostgreSQL locks or guarded updates and uniqueness constraints for concurrent benefit consumption, approvals, and reservations. SQLite's `BEGIN IMMEDIATE` is not a PostgreSQL concurrency design.
- Add versioned migrations, seed commands for fictional tenants, a restore check, and a one-way importer for the current JSON snapshot. Preserve the source backup and reconcile balances/counts before adopting the imported records.
- Reject silent fallback to SQLite in cloud mode. Keep the old demo explicitly separate until cutover.

Acceptance: two tenants with multiple jobs persist across service restarts; concurrent approvals cannot double-consume; a deliberately failed transaction leaves no partial ledger or invoice changes; demo export reconciliation reports match or explain all differences.

### P0-B. Authentication and tenant/branch authorization

Use a managed OIDC identity provider, chosen to match the frontend team's existing decision if one exists. Validate issuer, audience, signature, and token expiry on the backend. Do not build a custom password system or login screen in this work.

- Maintain authorized user-to-tenant memberships and branch grants server-side. A requested tenant ID alone never grants access.
- Add owner, office/reviewer, technician, and read-only permissions at resource/action level; avoid treating a global `read` permission as complete authorization.
- Add owner-authorized invitations/membership administration, role changes, and revocation. Identity-provider account operations must follow that provider's supported lifecycle.
- Check authorization on list/search/detail/mutations, exports, import files, background tasks, and analytics. Tenant-wide resources need explicit access rules; stock locations belong to defined branches.
- Reject `X-Demo-Role` as an authorization mechanism in the deployed service. Record actor identity, not just a role label.
- Keep provider keys and database access server-side. Log request IDs and errors without tokens or unnecessary customer text.

Acceptance: unauthenticated and revoked users cannot access records; users cannot enumerate another tenant's data or mutate a branch they do not own; technicians cannot approve invoices or grant roles. Backend tests use signed test tokens. Frontend login integration remains external work.

### P0-C. Customer and operational job CRUD

- Create/read/update/archive customers, contacts, properties, equipment, and jobs; add scoped search and pagination. Use archive/cancel semantics where deleting would destroy history. Restrict hard deletion to unreferenced drafts.
- Keep contact roles, residential/commercial type, service trade, property, equipment, and external IDs explicit.
- Store job notes with author, source, timestamp, and revision. Support multiple equipment/work entries where needed.
- Separate operational review/completion state from dispatch/travel/scheduling state. Do not claim that a backend confirmation completes a dispatch visit until the owning team adopts the contract.
- Protect edits with revision checks; associate follow-up jobs with their source job and customer.

Acceptance: create two customers with similar addresses and multiple jobs; independently edit/archive permitted records; record work on the correct equipment; reject stale edits and cross-tenant links. No seeded identity is required for the new endpoints.

Persistent appointments, availability, technician assignment, routing, and dispatch status are a coordination dependency, not part of this implementation scope.

### P0-D. Gemini text extraction and review

Accept typed technician notes plus permitted job context and a bounded catalog. Call Gemini with a structured output schema. Persist the original note, provider/model identifier, prompt/schema version, output, and source references. Model selection stays configurable rather than hardcoding a model from an example.

Proposed output: equipment candidates, completed work, material candidates with quantities/units/disposition, unresolved needs, and suggested follow-ups. References to original note spans must be checked against the stored source. Unsupported or ambiguous matches remain unresolved.

- Validate schema, IDs, tenant ownership, quantities, and disposition before presenting a proposal. Valid JSON is not proof of correct interpretation.
- Keep notes as untrusted data: a note cannot grant permissions, choose another tenant, run code, or authorize mutations.
- AI must not determine membership balances, stock totals, invoice totals, or permission decisions.
- Add approve, reject, and revise commands. Human revision produces a versioned proposal; approval rechecks source job, agreement version, and relevant material state.
- Bound note size, context, provider timeouts, retry count, usage, and duplicate submissions. Provider errors produce an actionable state; never silently substitute the fixed demo and label it live AI.
- Call the model outside inventory/billing transactions. Manual structured entry remains possible during provider failure.

Acceptance: a labeled set of about 12–20 notes covers normal work, returns, quantities, wrong/ambiguous equipment, unknown parts, irrelevant instructions, and incomplete work. Report actual field-level accuracy, unresolved rate, latency, and reviewer edits. Include a separate live call in award evidence; mocked tests alone do not prove Gemini usage. No speech, transcription, microphone, or ElevenLabs changes.

### P0-E. Atomic work confirmation and billing review

Generalize the existing orchestrator so an approved proposal updates equipment history, job work records, relevant benefit entries, material disposition, draft billing, and audit evidence in one transaction.

- Membership discounts apply to eligible lines under the terms effective on the service date. Billable, included, warranty, and fixed-price lines have explicit treatment.
- Reconcile issued, installed, unused-return, and damaged/lost material by SKU and job. Do not aggregate different parts into a single quantity check.
- Findings identify the rule, supporting records, affected draft lines, and proposed action. Permit dismissal with a reason as well as correction.
- Preserve immutable approved snapshots. Corrections require an explicit reversal or replacement record; reopening a job must not automatically restock installed material.
- Distinguish job draft invoicing from payment collection, accounting posting, and platform subscription pricing.

Acceptance: concurrent approvals yield one effect; the original $240-to-$180 scenario still reconciles; other quantities and line prices work; a missing membership can follow a reviewed nonmember billing path; reversals preserve history and do not invent returns.

### P0-F. Vultr backend deployment

Package only the new backend and its worker, if needed, in containers. Start with a single Vultr compute deployment and Tiger Data as the external managed database; Kubernetes is not required for this scope.

- Provide an example environment file containing names/placeholders only, dependency lock, HTTPS reverse proxy, explicit allowed origins, and separate liveness/readiness checks.
- Run migrations as an explicit release step. Start without migrations being executed by every request or worker.
- Configure database TLS, secret injection, restart behavior, request limits, bounded logs, monitoring, and a documented backup/restore procedure.
- Provide a release manifest with image/commit and schema version. Roll back application releases only to a schema-compatible version; otherwise use the documented recovery procedure.
- Exercise the backend using an API script and separate authorized identities. Frontend builds, deployment, domain changes, and voice services remain untouched.

Acceptance: the authenticated HTTPS API works on Vultr; a service restart preserves data; an unready database yields a failing readiness check; secrets do not appear in responses/logs; a fresh deployment and a restore can be reproduced from the runbook.

Required external setup at implementation time: authorized Vultr account/project and budget, Tiger Data service/credentials, Gemini key/quota, identity provider configuration, and agreed client origin. No resources or spend are created by this proposal.

### P1-A. Inventory receiving, transfers, reservations, replenishment

- Add warehouse/truck locations, SKU/barcode aliases, units, opening balances, receiving, transfers, job issue, consumption/disposition, usable return, damaged return, and reasoned adjustment.
- Reservations reduce available-to-promise stock, not physical on-hand stock. Issue releases/converts the associated reservation atomically; installation records disposition without double deduction.
- Enforce location/SKU stock constraints and concurrency protection. Transfer either commits both sides together or models an explicit in-transit state.
- Add configurable minimum/target stock and reviewed replenishment suggestions. Supplier purchasing/payment is later work; do not automatically order from a low-stock event.
- Provide lookup by a barcode string for ordinary API consumers. No scanner driver, camera recognition, device integration, or UI implementation is needed for the hardware pitch.

Acceptance: receive → transfer → reserve → issue → install/return reconciles by location and SKU. Competing reservations cannot oversell. Duplicate requests have one effect; damaged returns never become available stock without inspection.

### P1-B. Agreement lifecycle and obligations

- Add draft/active/expired/canceled states, effective-dated renewals and upgrades, equipment/trade coverage, and separate allowances per covered service.
- Preserve historical terms. Preview future impact of a change; apply staff-approved amendments without rewriting past work or invoices.
- Record grants, consumption, adjustments, and reversals as signed ledger entries with source and reason. Review disputed balances rather than guessing them.
- Generate due-service and renewal records from an explicit schedule. Unused allowance alone does not establish that a service is overdue.
- Track recorded payment status separately from entitlement rules. Automatic charging, refunds, and prorations are not implied by cancellation or upgrade support.

Acceptance: HVAC completion does not spend a plumbing benefit; changing future terms preserves the old invoice; scheduling never consumes a visit; cancellation/adjustment/reversal cases reconcile as specified.

### P1-C. Real imports and migration reconciliation

Start with documented CSV formats and the existing JSON export, not an unrestricted promise to import any CRM or historical attachment.

- Stage rows with source IDs, batch checksums, tenant, mapping version, and validation results.
- Preview customer/property/equipment matches, duplicates, agreement versions, completed service, and proposed opening balances.
- Flag ambiguity and conflicting evidence for review. Do not merge records or import benefits by inference alone.
- Commit an approved batch with idempotent row handling and an audit report. Re-running a batch cannot create duplicate grants or customers.
- Rollback of untouched imported records may be allowed; subsequent operational activity requires reviewed compensating corrections rather than deletion.

Acceptance: a clean import succeeds; an ambiguous equipment match blocks the affected row; inconsistent visit counts remain unresolved; repeat import creates no duplicate benefit; exported balances match approved imports plus later transactions.

### P1-D. Readiness evaluation

Add an actual read-only evaluator for required materials/reservations, coverage or approved billable scope, customer approval, and prerequisite work. Qualification/availability evidence can only come from an agreed source owned by the dispatch team.

- Return a verdict of ready, blocked, or unknown, with check IDs, explanations, evidence, and evaluation time/revision.
- Missing data is unknown, not success. Changing an input invalidates cached results.
- Expose evaluation through the operations API; do not schedule, assign, route, or modify dispatch state. Scheduling-time enforcement belongs to its owner after integration.

Acceptance: missing part blocks; confirmed receipt plus reservation clears that blocker; absent qualification evidence stays unknown; an incomplete prerequisite remains blocked even when materials are ready.

### P1-E. Cross-trade opportunities and Tiger Data analytics

Record an employee-approved follow-up need linked to its source note, customer, property, equipment, and trade. Give it reviewed/open/converted/dismissed states and a reason. Convert it once into an operational job. Contacting the customer and scheduling remain separate actions.

Add useful time-based reports from actual operational events: time spent blocked for materials, draft billing corrections approved, and material usage/returns by trade/location. Clearly distinguish prevented overcharges from revenue recovered; sample/demo results are not customer savings.

Keep current-state records, financial evidence, and inventory ledgers in ordinary transactional PostgreSQL tables. If useful for the dataset, add an append-only operational event hypertable and a continuous aggregate after verifying Tiger Data service support. Emit events transactionally or through an idempotent outbox; analytics must not become the authority for balances. Benchmark and explain any time-series feature instead of adding it solely as a logo.

Acceptance: a plumbing follow-up from an HVAC note keeps the same customer/property context without spending an HVAC benefit; conversion retries create one job; report values reconcile to the underlying events; other tenants' events never appear.

### P2. Messaging, payments, and accounting integrations

These are compatible future backend extensions but not required for the selected awards. Choose providers and concrete pilot needs before building them.

| Extension | Bounded proposal | Prerequisites and limits |
|---|---|---|
| Messaging | Stored employee-reviewed email/SMS drafts; later provider delivery with an outbox, delivery receipts, retry protection, and contact preferences. | No voice dispatch changes. No real customer messages are sent as part of this proposal. |
| Payments | Provider sandbox checkout/payment-reference records and verified, idempotent webhooks. | Merchant account, currency/tax/refund policy, authorization model, and reconciliation must be defined. Store provider references, not card data. |
| Accounting | Approved invoice export with external IDs; later one chosen provider's sandbox sync and reconciliation. | Define ownership of invoice numbers, edits, taxes, credits, and failures. Never silently create duplicate invoices. |

An adapter interface by itself is not a working integration. Keep all three marked planned until exercised end-to-end with the chosen provider.

## Proposed API contract for coordination

All paths below are new `/api/v1` proposals. Publish an OpenAPI description and sample fixtures before consumers adopt them. Authenticate every business endpoint. Derive allowed tenant/branch scope from verified identity. Return structured errors and request IDs; support pagination, revisions, and idempotency on financial/ledger commands.

| Resource | Suggested operations |
|---|---|
| Customers, properties, equipment | List/search, create, read, patch with expected revision, archive |
| Jobs | Create/read/patch operational details, add source note, read evidence/history, archive unused draft |
| Proposals | Prepare from text or manual entry, inspect, revise, reject, confirm with idempotency key |
| Agreements | Read coverage, create, preview/apply amendment, renew, cancel, adjust benefit with reason |
| Inventory | Read balances, receive, transfer, reserve/release, issue, record disposition/return/adjustment |
| Imports | Upload/stage, validate/preview, resolve row, approve/commit, export reconciliation |
| Readiness | Read current evidence-based evaluation for a job |
| Opportunities | Create/review need, dismiss, convert into an operational job |
| Analytics | Read authorized movement/exception/blocker reports |
| Administration | Manage user memberships/branch grants, supported module configuration, export |

There is no new voice, audio, assignment, scheduling, navigation, or route endpoint in this proposal. Generic authorized job and coverage reads may eventually be consumed by existing teams, without this work changing those clients.

## Hardware concept and startup pitch work

### Hardware: proposed workflow, not implemented UI

Document a USB/Bluetooth barcode scanner attached to an existing workstation, or an existing phone camera used to read a barcode. Ordinary barcode lookup is the first scope; recognizing arbitrary loose parts from photos is a different, unvalidated capability.

Illustrative pitch mockup (documentation only):

```text
IDENTIFY PART       CONFIRM MOVEMENT             REVIEW RESULT
Barcode/SKU   ->    Source: warehouse            Job: selected work order
Matched item       Destination: truck/job  ->    On hand / reserved
Unknown? Review    Quantity + purpose            Actor + time + evidence
                   [Employee confirmation]
```

The pitch should include who scans, when, handling unknown/damaged items, duplicate scan behavior, network failure behavior, physical rollout/training, and expected benefit. Do not claim automatic stock accuracy just because a scan occurred.

Cost worksheet: list an existing-phone option with $0 incremental device purchase only if the company already owns it, plus a researched scanner option with supplier/date/price. Include labels, setup time, training, replacements, and hosting/usage allocations. Obtain current quotes before putting a scanner total on the pitch; no product price is asserted here. Compare the estimate against measured manual-entry time and error corrections, not invented savings.

### Startup: evidence and business model

Prepare a concise evidence packet containing:

1. Target buyer: owner/GM of an independent South Carolina home-service contractor; office manager as daily user; adding a trade or struggling with membership/material handoffs as the trigger.
2. One permissioned customer workflow example and its current cost/time/error, clearly separating reported observations from measurements. Iesha's reported interest is a discovery lead, not a signed pilot or paid customer.
3. A competitor comparison of the exact workflow; avoid claiming that multi-trade, memberships, inventory, or AI are unique features.
4. A core subscription model with price and included usage still to be validated. Keep any separate services or advertising assumptions explicit. Explain costs of AI, hosting, support, and migration without fixing a subscription amount.
5. A go-to-market plan using existing contractor relationships, direct demonstrations, and referrals. Define a bounded onboarding offer rather than promising every historical record or unlimited customization.
6. A proposed pilot: a small catalog, defined jobs, two trades, named users, agreed record ownership, reconciliation, and feedback sessions. Target 3 design partners; label that as a target until committed.
7. Success measures: coverage lookup time, reviewer effort, reconciled stock/benefits, useful AI suggestions, onboarding hours, and willingness to continue at a tested price. Record baselines and failures as well as improvements.
8. A stage-accurate roadmap separating working backend, separately owned frontend/voice, hardware concept, and later integrations.

## Delivery sequence and stopping points

| Stage | Work | Exit evidence |
|---|---|---|
| 0 | Share contracts and ownership boundary; confirm identity decision with existing owners. | No protected paths changed; proposed IDs/auth expectations documented. |
| 1 | P0-A/B/C: Tiger Data foundation, authorization, general customer/job records. | PostgreSQL tests pass with multiple tenants/jobs; authorized API CRUD works. |
| 2 | P0-D/E: Gemini text proposals, review, atomic confirmation/billing. | Live extraction plus manual review; retries/concurrency reconcile. |
| 3 | P0-F: Vultr backend deployment and repeatable API demo. | Authenticated deployed service and persisted records; logs and recovery checked. |
| 4 | P1-A/B/D: one real inventory flow, cross-trade benefits, evidence-based readiness. | Missing-part scenario clears correctly; benefits stay scoped by trade. |
| 5 | P1-C/E: migration reconciliation, follow-up conversion, useful analytics. | Import resolves actual ambiguity; opportunity converts once; reports reconcile. |
| Alongside | Hardware concept and startup evidence packet. | Claims, costs, assumptions, validation, and pilot ask are reviewable. |
| Later | Full P1 breadth and P2 external integrations. | Customer-validated need and explicit provider acceptance tests. |

P0 is the proposed minimum backend delivery. The integrated presentation still depends on the independently owned frontend and ElevenLabs work. Backend completion alone must not be described as a finished six-category submission. No delivery date is assumed without the event deadline and team capacity.

## Backend-only demonstration and checks

Use API scripts or API documentation, not frontend edits, to prove the work independently:

1. Create a fictional customer/property with HVAC and plumbing equipment and scoped benefits.
2. Create an operational job and record material issue from an actual inventory transaction when P1 inventory is available.
3. Submit a new typed note; inspect Gemini's proposed work, return, and plumbing follow-up with evidence.
4. Revise/confirm as an authorized reviewer. Show the correct benefit, stock disposition, draft invoice, equipment history, and audit entry.
5. Retry confirmation, attempt a stale update, and attempt cross-tenant access; show safe rejection or one-effect replay.
6. Read the same authorized records in a separate API session after restarting the Vultr service.
7. If P1 is complete, convert the plumbing opportunity, resolve a missing-part readiness blocker, and review an import conflict and time-based report.

Test real PostgreSQL transactions rather than relying only on SQLite tests. Add invariant, authorization, concurrency, migration/reconciliation, provider-failure, and API contract tests. Keep mocked provider tests separate from a small live Gemini smoke test. No frontend/voice tests are edited here. For the proposal itself, check Markdown and the Git diff; runtime tests are unnecessary because application code is unchanged.

## References

- Selected categories: user's screenshot and explicit hardware-pitch clarification in this conversation.
- [Official Palmetto Hacks sponsor prizes](https://www.mlh.com/events/palmetto-hacks/prizes): confirms the selected MLH integrations; does not establish local category scoring weights.
- [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output): JSON-schema-constrained output; domain validation remains our responsibility.
- [Connect to Tiger Data](https://www.tigerdata.com/docs/integrate/find-connection-details): hosted PostgreSQL connection setup.
- [PostgreSQL TLS verification](https://www.postgresql.org/docs/18/libpq-ssl.html): connection certificate/hostname verification.
- [Vultr Docker deployment guide](https://docs.vultr.com/how-to-use-vultrs-docker-marketplace-application): deployment reference, not a requirement to use every example configuration.

Sources checked October 10, 2026. Implementation choices and acceptance criteria above are proposals, not claims that the repo already implements them.
