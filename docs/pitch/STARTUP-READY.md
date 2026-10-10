# Goob: startup-ready pitch and validation packet

## Pitch

Goob helps independent home-service contractors expand from one trade into HVAC,
electrical, and plumbing while keeping customer promises, material use, and work records
connected. AI turns technician notes into reviewable entries. Explicit rules reconcile
membership benefits, stock, and draft billing before an employee approves the changes.
Our first market is South Carolina contractors we can work with directly.

The entry product is one verifiable customer → work → materials → membership → billing
workflow. Cross-trade follow-ups reuse the customer's property history. The broader growth
platform is a roadmap; advertising and outbound lead acquisition are not implemented here.

## Buyer, problem, and competitive hypothesis

Buyer: an owner or GM. Daily users: office staff and technicians. Initial prospect: an
independent contractor with several technicians, memberships, warehouse/truck stock,
and operational handoffs that become harder when adding a trade.

User-reported discovery includes Iesha's requests for customer tracking, memberships,
multiple trades, and materials linked to jobs. This is a discovery lead, not measured
market demand, a signed pilot, or a paying customer. Obtain permission before naming or
quoting a contact in the public pitch.

Existing platforms already provide substantial overlap. FieldPulse advertises linked
assets and service history; Jobber documents recurring jobs. Our hypothesis is that a
specific contractor can complete and reconcile this workflow with less manual effort,
with a verified transition of remaining benefits. Compare against the customer's actual
configured tools rather than claiming that competitors have no AI, memberships, or inventory.
[FieldPulse](https://www.fieldpulse.com/features/asset-management),
[Jobber](https://help.getjobber.com/en/articles/create-a-recurring-job/).

## Business model and route to first customers

- Core company subscription; **price and included usage remain undecided**. Adding a
  trade should not force a trade-unlock purchase under the current positioning hypothesis.
- Test willingness to pay after demonstrating the workflow. Separate optional service
  work and advertising budgets from the platform subscription.
- Model hosting, database, AI, support, payment-provider fees if adopted, and onboarding
  labor. Subscription revenue is not profit. A free standard migration still has delivery cost.
- Recruit three design partners through existing contractor relationships, then seek
  referrals from pilots with measured outcomes. Three is a recruitment target, not traction.
- Start with supported exports, a small parts catalog, defined membership rules, named
  users, and a bounded set of jobs. Existing accounting remains the financial system of record.
- Agree who writes each record during the pilot and a reconciliation/cutover procedure.
  Avoid concurrent edits in two systems that both claim to own the same balance.

## Interview and evidence worksheet

| Evidence | Question/task | Current status |
|---|---|---|
| Pain example | Show the last membership, material, or follow-up discrepancy. | Needs customer example |
| Frequency/cost | How often does it happen; how much time or correction does it require? | Not measured |
| Existing alternative | Demonstrate the same task in the current configured system. | Needs observed comparison |
| Desired outcome | Which record/result would have prevented the problem? | Validate in workflow session |
| Pilot commitment | Who will test which jobs, with what success criteria? | No commitment established here |
| Purchase intent | If those criteria are met, would you continue at a tested price? | Price research pending |

Record the date, participant role, permission to quote, actual example, timing method,
and limitations of each observation. Do not replace missing evidence with fictional metrics.

## Proposed pilot and measures

Run a bounded 30-day pilot when the customer authorizes it. Suggested targets, not
achieved results: accurate equipment/coverage lookup, no unexplained stock/benefit
differences, lower median administrative time, useful AI suggestions after review, and
a clear paid-continuation decision. Capture wrong suggestions, missed discrepancies,
reviewer time, onboarding hours, and per-company delivery cost.

```text
Recurring contribution = subscription collected
                       − database/hosting/AI allocation
                       − direct support and integration costs

Onboarding payback months = onboarding delivery cost / monthly contribution
```

Use these formulas only after choosing assumptions and show sensitivity to support time
and AI volume. Do not present an unvalidated dollar price or margin as an established fact.

## Three-minute demonstration outline

1. Explain one contractor handoff problem with evidence or clearly label the example fictional.
2. Show an existing customer, covered equipment, and remaining service.
3. Submit a technician note; Gemini proposes structured work and materials for employee review.
4. Confirm the work; trace benefit usage, an unused part return, and the corrected draft invoice.
5. Show a plumbing follow-up preserving the original customer/property context.
6. Explain Tiger Data persistence and Vultr deployment only after those live connections are verified.
7. Hand off to the separately owned ElevenLabs demonstration and label hardware as a proposed integration.
8. Close with the pilot ask, business model, and measured evidence or explicit unanswered hypotheses.

## Award evidence checklist

| Category | Evidence ready in this branch | Still required |
|---|---|---|
| Hardware | Concept, diagram, budget assumptions, integration boundary | Pitch delivery; any organizer-specific submission requirements |
| Startup Ready | Target/customer/problem/model/GTM/pilot packet | Customer validation, accurately described commitment, final pitch |
| Gemini | Real provider adapter, test fixtures, review rules | Live call and measured evaluation with credentials |
| Tiger Data | PostgreSQL schema, migration, ledger, reports | Hosted service connection and evidence |
| Vultr | Backend deployment files and recovery runbook | Build, deploy, HTTPS, runtime verification |
| ElevenLabs | Ownership recorded; code untouched | Existing team's spoken briefing demonstration |

Technical tests are evidence of tested behavior, not proof of customer demand or award eligibility.
