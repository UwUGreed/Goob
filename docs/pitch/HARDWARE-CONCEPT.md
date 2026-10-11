# Goob hardware concept: identify, confirm, reconcile

**Proposed integration. No hardware device, camera client, or product UI was built in this branch.**
The user's selected hardware category permits a pitch describing how it would be used.

## Thirty-second pitch

Contractors move parts between shelves, trucks, and jobs. Goob's proposed scanner
workflow captures a part's barcode, lets an employee confirm the quantity and destination,
and records the movement against the job. The same record supports parts readiness and
later review of what was installed or returned. Scanning helps identify the item; employee
confirmation and the inventory ledger establish what actually happened.

## Proposed equipment and rollout

- First option: an existing company phone camera reading printed item/bin codes. The
  phone must already be owned for the incremental hardware-purchase cost to be $0.
- Warehouse option: a USB HID barcode scanner at an existing workstation. HID devices
  can enter decoded characters like a keyboard; a future client captures the code and
  calls the existing SKU lookup API. [Adafruit's interface explanation](https://learn.adafruit.com/barcode-scanner/usb-interfacing).
- Use existing readable manufacturer barcodes or apply internal labels to a bounded
  pilot catalog. Initially support integer item quantities, one warehouse, and a few trucks.
- Test barcode format support, scan reliability, workstation/phone compatibility, label
  durability, and staff workflow before selecting a device. No purchase has been made.

## Documentation mockup

```text
┌──────────────────────────────┐     ┌────────────────────────────────┐
│ 1. IDENTIFY                  │     │ 2. CONFIRM MOVEMENT            │
│ Scan code / enter SKU        │ ──► │ Item: Run capacitor            │
│ Result: Run capacitor        │     │ From: Warehouse                │
│ Unit: each                   │     │ To: Truck H-01                 │
│ Unknown code? Staff review   │     │ Quantity: 2                    │
└──────────────────────────────┘     │ Purpose: selected service job  │
                                    │ [Review] [Confirm]             │
                                    └──────────────┬─────────────────┘
                                                   ▼
                                    ┌────────────────────────────────┐
                                    │ 3. RECONCILE                   │
                                    │ Warehouse −2; truck +2         │
                                    │ Reserve for job when approved  │
                                    │ Actor, time, reason, command ID│
                                    │ Later: installed 1 / return 1  │
                                    └────────────────────────────────┘
```

This is a pitch diagram, not an implemented screen. Backend building blocks exist:
`GET /api/v1/inventory/barcodes/{barcode}` and reviewed inventory commands for receiving,
transfer, reservation, issue, return, and adjustment. The future frontend/device owner
would supply code capture and confirmation UI without changing the accounting rules.

## Illustrative pilot budget

These are planning allowances, not vendor quotes or finalized product prices.

| Item | Existing-phone route | Scanner-station route |
|---|---:|---:|
| Existing phone/workstation | $0 incremental if already owned | $0 incremental if already owned |
| Scanner purchase allowance | $0 | $100 assumption; replace with current quote |
| Labels and consumables | $25 assumption | $25 assumption |
| Setup/training labor | 2 hours × $30 = $60 assumption | 2 hours × $30 = $60 assumption |
| Illustrative initial total | $85 | $185 |

Shipping, tax, replacement equipment, hosting/AI allocation, support, and future client
development are excluded and must be estimated separately. An Adafruit USB scanner
listing shows $69.95 but is **no longer stocked**; it is not an available procurement
recommendation or the basis of a purchase commitment. [Listing checked October 10, 2026](https://www.adafruit.com/product/1203).

## Exceptions and practical value

- Unknown/ambiguous item: no stock mutation; staff resolves the catalog match.
- Duplicate scan: scanning alone does not move stock; confirmation uses a unique command
  key so network retries do not duplicate a transfer.
- Missing network: show pending/unconfirmed entry in the future client; never report a
  successful movement before server acknowledgment. Offline sync is not implemented.
- Damaged return: record disposition; do not make damaged stock available for another job.
- Expected benefit: less repeated item entry and clearer material history. Test this on
  20 authorized sample movements: compare entry/reconciliation time and errors with the
  current process. Report actual results and reviewer effort, not projected savings as facts.
