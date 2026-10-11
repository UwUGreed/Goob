-- Derived quantities in each material's base unit; includes zero-stock accounts.
SELECT l.code AS location,m.sku,u.code AS unit,b.on_hand,b.reserved,b.available
FROM goob_foundation.inv_balances b
JOIN goob_foundation.org_organizations o ON o.id=b.organization_id
JOIN goob_foundation.inv_locations l ON (l.organization_id,l.id)=(b.organization_id,b.location_id)
JOIN goob_foundation.cat_materials m ON (m.organization_id,m.id)=(b.organization_id,b.material_id)
JOIN goob_foundation.cat_units u ON (u.organization_id,u.id)=(m.organization_id,m.unit_id)
WHERE o.slug='goob-demo-services' AND o.is_demo
ORDER BY l.code,m.sku;
