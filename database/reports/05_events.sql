-- Ordinary relational projection; no automatic retention, aggregation jobs or producers.
SELECT date_trunc('day',e.occurred_at AT TIME ZONE 'UTC') AS utc_day,e.event_type,count(*) AS event_count
FROM goob_foundation.report_events e JOIN goob_foundation.org_organizations o ON o.id=e.organization_id
WHERE o.slug='goob-demo-services' AND o.is_demo AND e.is_fictional
GROUP BY 1,2 ORDER BY 1,2;
