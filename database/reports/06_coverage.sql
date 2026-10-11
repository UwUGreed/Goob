-- Scope matching produces candidates, not an application authorization decision.
-- A job/task can match several agreements; callers must resolve ambiguity, never silently pick one.
SELECT j.job_number,t.description AS task,
 count(DISTINCT a.id) FILTER (WHERE a.status='active' AND a.interpretation_state='approved'
 AND c.review_state='approved' AND o.created_at::date BETWEEN a.starts_on AND a.ends_on
 AND o.created_at::date BETWEEN c.valid_from AND c.valid_until) AS approved_agreement_candidates
FROM goob_foundation.job_tasks t
JOIN goob_foundation.job_jobs j ON (j.organization_id,j.id)=(t.organization_id,t.job_id)
JOIN goob_foundation.cat_services s ON (s.organization_id,s.id)=(t.organization_id,t.service_id)
JOIN goob_foundation.org_organizations o ON o.id=j.organization_id
LEFT JOIN goob_foundation.agree_coverage c ON c.organization_id=j.organization_id AND c.property_id=j.property_id
 AND (c.service_scope='all' OR (c.service_scope='specific' AND c.service_id=t.service_id))
 AND (c.scope_kind='property' OR (c.scope_kind='trade' AND c.trade_id=s.trade_id)
 OR (c.scope_kind='equipment' AND EXISTS(SELECT 1 FROM goob_foundation.job_equipment e
 JOIN goob_foundation.crm_equipment q ON (q.organization_id,q.id)=(e.organization_id,e.equipment_id)
 JOIN goob_foundation.crm_equipment_types et ON (et.organization_id,et.id)=(q.organization_id,q.type_id)
 WHERE e.organization_id=j.organization_id AND e.job_id=j.id AND e.equipment_id=c.equipment_id AND et.trade_id=s.trade_id)))
LEFT JOIN goob_foundation.agree_agreements a ON (a.organization_id,a.id)=(c.organization_id,c.agreement_id) AND a.customer_id=j.billing_customer_id
WHERE o.slug='goob-demo-services' AND o.is_demo
GROUP BY j.job_number,t.description ORDER BY j.job_number;
