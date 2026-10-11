-- A derived shortage, not a seeded dashboard status. Quantity uses material base units.
SELECT j.job_number,m.sku,r.quantity AS required,
 COALESCE((SELECT sum(v.quantity) FROM goob_foundation.inv_reservations v
 JOIN goob_foundation.inv_stock_accounts s ON (s.organization_id,s.id)=(v.organization_id,v.account_id)
 WHERE v.organization_id=r.organization_id AND v.job_id=r.job_id AND s.material_id=r.material_id AND v.status='active'),0) AS reserved,
 r.quantity-COALESCE((SELECT sum(v.quantity) FROM goob_foundation.inv_reservations v
 JOIN goob_foundation.inv_stock_accounts s ON (s.organization_id,s.id)=(v.organization_id,v.account_id)
 WHERE v.organization_id=r.organization_id AND v.job_id=r.job_id AND s.material_id=r.material_id AND v.status='active'),0) AS shortage
FROM goob_foundation.job_required_materials r
JOIN goob_foundation.job_jobs j ON (j.organization_id,j.id)=(r.organization_id,r.job_id)
JOIN goob_foundation.cat_materials m ON (m.organization_id,m.id)=(r.organization_id,r.material_id)
JOIN goob_foundation.org_organizations o ON o.id=r.organization_id
WHERE o.slug='goob-demo-services' AND o.is_demo ORDER BY j.job_number;
