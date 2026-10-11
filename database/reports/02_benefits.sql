-- Eligibility is separate from quantity: date and interpretation gates shown explicitly.
SELECT a.agreement_number,a.status,a.interpretation_state,
 (a.status='active' AND a.interpretation_state='approved' AND o.created_at::date BETWEEN a.starts_on AND a.ends_on) AS agreement_eligible_as_of,
 b.balance_state,b.remaining,b.reserved,b.available
FROM goob_foundation.agree_balances b
JOIN goob_foundation.agree_agreements a ON (a.organization_id,a.id)=(b.organization_id,b.agreement_id)
JOIN goob_foundation.org_organizations o ON o.id=a.organization_id
WHERE o.slug='goob-demo-services' AND o.is_demo
ORDER BY a.agreement_number;
