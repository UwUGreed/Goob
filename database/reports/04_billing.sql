SELECT i.invoice_number,i.currency,r.recorded_total,r.calculated_total,r.discrepancy,
 (SELECT count(*) FROM goob_foundation.bill_review_flags f WHERE f.organization_id=i.organization_id AND f.invoice_id=i.id AND f.status='open') AS open_flags
FROM goob_foundation.bill_invoice_reconciliation r
JOIN goob_foundation.bill_invoices i ON (i.organization_id,i.id)=(r.organization_id,r.invoice_id)
JOIN goob_foundation.org_organizations o ON o.id=r.organization_id
WHERE o.slug='goob-demo-services' AND o.is_demo ORDER BY i.invoice_number;
