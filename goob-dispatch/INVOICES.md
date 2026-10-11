# Invoice workspace

Open **Invoices** in the sidebar or `/invoices`. Choose a customer and property; optionally link a job and its covered equipment. Describe the requested charges, generate a proposal or enter lines manually, review quantities/prices/categories, and save a draft. Saved drafts reopen at `/invoices/{id}`. Customer and job details include invoice creation links and invoice history. Typed or voice Ask Goob invoice requests open the same editor/generator; without a selected job, choose the billing records first.

Generation never completes work, consumes inventory or spends a maintenance allowance. Explicit credits/refunds use separate Credit lines with negative amounts; ordinary charges cannot be negative, credits receive no membership discount, and credits exceeding charges block finalization. For example, `Sink repair 150$ credit 20$` produces $150 and ?$20 lines for $130 before tax. General repairs remain unclassified; only explicitly evidenced labor can be generated as labor. Prices without explicit dollar evidence remain unresolved. The server uses exact decimal arithmetic, confirmed SKU pricebook records when explicitly selected, and existing equipment/property/trade/date membership eligibility. Eligible discounts are proposed individually and require review. A pricebook choice confirms that catalog price; choosing a catalog item does not issue stock.

## Server configuration

Set these in the root `.env` locally, or the service's environment on deployment. Never use `VITE_` for these variables.

```dotenv
GEMINI_API_KEY=your-server-key
GEMINI_MODEL=gemini-3.8-flash
GOOB_INVOICE_COMPANY_NAME=Your legal business name
GOOB_INVOICE_COMPANY_ADDRESS=Your billing address
GOOB_INVOICE_COMPANY_CONTACT=Your billing email or phone
GOOB_INVOICE_TAX_BPS=0
```

The tax example means **confirmed no tax**, not an assumed exemption. Configure the actual rate in basis points (725 = 7.25%) on net charges for this deployment. The existing work-review accounting flow has no finalized tax configuration; leaving this blank preserves draft entry and blocks finalization. This flat deployment configuration must be reviewed for your business's tax requirements before use. Customer name, address and email or phone, company details, positive quantities, resolved pricing and human review are required for finalization. Resolve model review questions in the review note. Finalization compares a server-generated preview fingerprint against current configuration/coverage/prices, and finalized snapshots are immutable.

Install `requirements.txt` and run `npm ci --prefix goob-dispatch` on the server. Python invokes a bounded Node process using Google's official `@google/genai` package with `responseMimeType: 'application/json'` and `responseJsonSchema`. Node must be on the service PATH, or set `GOOB_NODE_BINARY` to its absolute path. [Official structured-output configuration](https://googleapis.github.io/js-genai/release_docs/interfaces/types.GenerateContentConfig.html#responseJsonSchema). Provider failures do not log keys or descriptions; the UI offers manual entry, with separate messages for configuration, rate limits, timeout and invalid output. Generation is limited by `GEMINI_HOURLY_REQUEST_LIMIT` (default 30 shared attempts per tenant/hour).

Apply `python -m alembic -c alembic-backend.ini upgrade head` with the intended server environment before restarting. Migration `20261013_invoice_editor` adds optional independent links, status/revision/number to the existing `invoices_v1` ledger and a database numbering sequence. No existing invoices are removed. With a separate runtime database role, rerun `deploy/backend/grants.sql` as the schema owner after migration to grant invoice draft updates and sequence usage. The backend Dockerfile includes Node and the SDK bridge. Numbers are unique `INV-year-sequence` values; aborted transactions may leave harmless numbering gaps. Mutation commands reuse the existing transactional idempotency ledger; clients retain request IDs across retries and stale revisions cannot create duplicates.

Print and PDF export use saved snapshots with company, customer, dates, itemized charges, discounts, tax and total. Save edits before export. Draft PDFs remain labeled draft and list review blockers. The existing proposal accounting export is preserved; independent finalized invoices expose the same `/api/v1/invoices/{id}/accounting-export` path with schema version 2 and `sync_status: not_posted`. No external accounting posting occurs.

## Verification

`npm run build --prefix goob-dispatch` and `npm test --prefix goob-dispatch` check types/build and exact decimal preview rounding. With an explicit `TEST_DATABASE_URL`, run:

```text
python -m pytest tests/backend_v1/test_invoice_editor.py -q
```

These are mocked Gemini checks with real authentication, disposable PostgreSQL schema/migrations, pricing/coverage, ledger side effects, persistence, duplicate retries, finalization and real PDF parsing. Install `deploy/backend/requirements-dev.txt` for PDF parsing and backend tests. The browser QA uses the same isolated database and mocked provider, and tests desktop/mobile, sign-in return routes, both example charges, edits, refresh, finalization, PDF download, record links/history and Ask Goob:

```text
GOOB_BROWSER_CHECK=1 python -m pytest tests/backend_v1/test_invoice_browser.py -q
```

PowerShell: `$env:GOOB_BROWSER_CHECK='1'`. It starts a temporary server on port 8092; Windows uses installed Edge, other platforms need Playwright Chromium installed. Screenshots and a sample export are in ignored `goob-dispatch/test-results/`. Live Gemini verification is separate from these mocked checks and requires both server variables; both plain-price examples have since been verified against the live authenticated Gemini endpoint after the server key was configured.

Generation allows a 90-second overall SDK deadline with up to three attempts and exponential backoff for transient HTTP failures. The Python bridge allows 100 seconds so it does not kill SDK retries prematurely. Persistent Google 429 responses require available model quota; increasing timeouts cannot remove provider quota limits.
