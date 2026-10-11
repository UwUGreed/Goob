# Table dictionary

All business tables live in `goob_foundation`. Prefix = owning module. UUIDs identify records. Unless stated otherwise, `(organization_id,id)` is the primary key; `organization_id` references `org_organizations(id)`. Every FK uses `ON DELETE RESTRICT`; there are no cascading deletes. Every reference includes organization_id to reject cross-tenant links. NOT NULL denotes required columns; other columns are nullable. Every FK has an index. Non-history rows retain created_at; archive or use an explicit lifecycle status where provided. Changes to mutable business rows require application audit events in future integration. Append-only rows require a new version, reversal, or compensating record. The guarded demo reset is the only tooling path that deletes fixture history.

## org_organizations

Owner: **org**. PK: `id`. Mutable operational record; FK-restricted deletion. Tenant root; archive instead of deleting operational history.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL CHECK (length(trim(name)) > 0)` |  |
| slug | `text NOT NULL UNIQUE` |  |
| is_demo | `boolean NOT NULL DEFAULT false` |  |
| archived_at | `timestamptz` |  |

Unique constraints: primary key only.

Checks: column checks above.

## org_branches

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |
| timezone | `text NOT NULL` |  |
| archived_at | `timestamptz` |  |

Unique constraints: `organization_id,name`.

Checks: column checks above.

## org_roles

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |

Unique constraints: `organization_id,name`.

Checks: column checks above.

## org_permissions

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## org_trades

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| name | `text NOT NULL` |  |
| enabled | `boolean NOT NULL DEFAULT true` |  |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## org_modules

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| enabled | `boolean NOT NULL DEFAULT false` |  |
| settings | `jsonb NOT NULL DEFAULT '{}'::jsonb` |  |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## crm_customers

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| kind | `text NOT NULL CHECK (kind IN ('residential','commercial'))` |  |
| display_name | `text NOT NULL` |  |
| archived_at | `timestamptz` |  |

Unique constraints: primary key only.

Checks: column checks above.

## crm_contacts

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| given_name | `text NOT NULL` |  |
| family_name | `text NOT NULL` |  |
| email | `text` |  |
| phone | `text` |  |
| archived_at | `timestamptz` |  |

Unique constraints: primary key only.

Checks: column checks above.

## crm_addresses

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| line1 | `text NOT NULL` |  |
| line2 | `text` |  |
| city | `text NOT NULL` |  |
| region | `text NOT NULL` |  |
| postal_code | `text NOT NULL` |  |
| country_code | `text NOT NULL CHECK (country_code ~ '^[A-Z]{2}$')` |  |

Unique constraints: primary key only.

Checks: column checks above.

## crm_files

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Metadata only. Storage reference contains an object key, never credentials or file bytes.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| storage_reference | `text NOT NULL` |  |
| filename | `text NOT NULL` |  |
| content_type | `text NOT NULL` |  |
| byte_size | `bigint NOT NULL CHECK (byte_size >= 0)` |  |
| sha256 | `text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$')` |  |

Unique constraints: primary key only.

Checks: column checks above.

## cat_units

Owner: **cat**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| dimension | `text NOT NULL` |  |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## cat_job_types

Owner: **cat**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| name | `text NOT NULL` |  |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## cat_pricebooks

Owner: **cat**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |

Unique constraints: primary key only.

Checks: column checks above.

## agree_plans

Owner: **agree**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| name | `text NOT NULL` |  |
| active | `boolean NOT NULL DEFAULT true` |  |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## inv_suppliers

Owner: **inv**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |
| external_reference | `text` |  |

Unique constraints: primary key only.

Checks: column checks above.

## integrate_connections

Owner: **integrate**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Secret-manager reference only; no access tokens or plaintext credentials.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| provider | `text NOT NULL` |  |
| secret_reference | `text NOT NULL` |  |
| enabled | `boolean NOT NULL DEFAULT false` |  |

Unique constraints: `organization_id,provider`.

Checks: column checks above.

## org_members

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Opaque references to an external identity provider; no passwords or auth accounts.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| auth_provider | `text NOT NULL` |  |
| auth_subject | `text NOT NULL` |  |
| display_name | `text NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('active','invited','inactive'))` |  |
| branch_id | `uuid` | org_branches |

Unique constraints: `organization_id,auth_provider,auth_subject`.

Checks: column checks above.

## org_role_permissions

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| role_id | `uuid NOT NULL` | org_roles |
| permission_id | `uuid NOT NULL` | org_permissions |

Unique constraints: `organization_id,role_id,permission_id`.

Checks: column checks above.

## org_qualifications

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| name | `text NOT NULL` |  |
| trade_id | `uuid NOT NULL` | org_trades |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## crm_customer_contacts

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| relationship | `text NOT NULL` |  |
| is_primary | `boolean NOT NULL DEFAULT false` |  |
| customer_id | `uuid NOT NULL` | crm_customers |
| contact_id | `uuid NOT NULL` | crm_contacts |

Unique constraints: `organization_id,customer_id,contact_id,relationship`.

Checks: column checks above.

## crm_properties

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |
| timezone | `text NOT NULL` |  |
| archived_at | `timestamptz` |  |
| address_id | `uuid NOT NULL` | crm_addresses |

Unique constraints: primary key only.

Checks: column checks above.

## crm_equipment_types

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |
| trade_id | `uuid NOT NULL` | org_trades |

Unique constraints: `organization_id,trade_id,name`.

Checks: column checks above.

## crm_communication_preferences

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| channel | `text NOT NULL CHECK (channel IN ('email','sms','phone','postal'))` |  |
| purpose | `text NOT NULL` |  |
| allowed | `boolean NOT NULL` |  |
| recorded_at | `timestamptz NOT NULL` |  |
| source | `text NOT NULL` |  |
| contact_id | `uuid NOT NULL` | crm_contacts |

Unique constraints: `organization_id,contact_id,channel,purpose`.

Checks: column checks above.

## cat_materials

Owner: **cat**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| sku | `text NOT NULL` |  |
| name | `text NOT NULL` |  |
| active | `boolean NOT NULL DEFAULT true` |  |
| unit_id | `uuid NOT NULL` | cat_units |

Unique constraints: `organization_id,sku`.

Checks: column checks above.

## cat_services

Owner: **cat**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| name | `text NOT NULL` |  |
| active | `boolean NOT NULL DEFAULT true` |  |
| trade_id | `uuid NOT NULL` | org_trades |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## cat_labor_rates

Owner: **cat**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |
| valid_from | `date NOT NULL` |  |
| valid_until | `date` |  |
| hourly_rate | `numeric(19,4) NOT NULL CHECK (hourly_rate >= 0)` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |
| trade_id | `uuid NOT NULL` | org_trades |

Unique constraints: primary key only.

Checks: `valid_until IS NULL OR valid_until >= valid_from`.

## agree_plan_versions

Owner: **agree**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| version | `integer NOT NULL CHECK (version > 0)` |  |
| terms | `text NOT NULL` |  |
| published_at | `timestamptz NOT NULL` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |
| period_price | `numeric(19,2) NOT NULL CHECK (period_price >= 0)` |  |
| plan_id | `uuid NOT NULL` | agree_plans |
| source_file_id | `uuid` | crm_files |

Unique constraints: `organization_id,plan_id,version`.

Checks: column checks above.

## integrate_record_mappings

Owner: **integrate**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| entity_type | `text NOT NULL` |  |
| local_record_id | `uuid NOT NULL` |  |
| external_id | `text NOT NULL` |  |
| connection_id | `uuid NOT NULL` | integrate_connections |

Unique constraints: `organization_id,connection_id,entity_type,external_id`; `organization_id,connection_id,entity_type,local_record_id`.

Checks: column checks above.

## integrate_sync_attempts

Owner: **integrate**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| started_at | `timestamptz NOT NULL` |  |
| finished_at | `timestamptz` |  |
| status | `text NOT NULL CHECK (status IN ('pending','succeeded','failed'))` |  |
| error_code | `text` |  |
| error_detail | `text` |  |
| retry_after | `timestamptz` |  |
| idempotency_key | `text NOT NULL` |  |
| connection_id | `uuid NOT NULL` | integrate_connections |

Unique constraints: `organization_id,idempotency_key`.

Checks: column checks above.

## integrate_checkpoints

Owner: **integrate**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| stream | `text NOT NULL` |  |
| cursor_value | `text NOT NULL` |  |
| updated_at | `timestamptz NOT NULL` |  |
| connection_id | `uuid NOT NULL` | integrate_connections |

Unique constraints: `organization_id,connection_id,stream`.

Checks: column checks above.

## integrate_authority

Owner: **integrate**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Optional Ply source-of-truth configuration only; no integration execution.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| entity_type | `text NOT NULL` |  |
| authority | `text NOT NULL CHECK (authority IN ('goob','provider'))` |  |
| conflict_policy | `text NOT NULL CHECK (conflict_policy IN ('manual','authoritative_wins'))` |  |
| connection_id | `uuid NOT NULL` | integrate_connections |

Unique constraints: `organization_id,connection_id,entity_type`.

Checks: column checks above.

## org_member_roles

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| member_id | `uuid NOT NULL` | org_members |
| role_id | `uuid NOT NULL` | org_roles |

Unique constraints: `organization_id,member_id,role_id`.

Checks: column checks above.

## org_technicians

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| employee_number | `text NOT NULL` |  |
| active | `boolean NOT NULL DEFAULT true` |  |
| member_id | `uuid NOT NULL` | org_members |

Unique constraints: `organization_id,member_id`; `organization_id,employee_number`.

Checks: column checks above.

## crm_customer_properties

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| relationship | `text NOT NULL CHECK (relationship IN ('owner','tenant','manager','billing'))` |  |
| valid_from | `date NOT NULL` |  |
| valid_until | `date` |  |
| customer_id | `uuid NOT NULL` | crm_customers |
| property_id | `uuid NOT NULL` | crm_properties |

Unique constraints: `organization_id,customer_id,property_id,relationship,valid_from`.

Checks: `valid_until IS NULL OR valid_until >= valid_from`.

## crm_equipment

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Current location projection; relocations and replacements remain in history; trade is derived from equipment type.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |
| make | `text` |  |
| model | `text` |  |
| serial_number | `text` |  |
| installed_on | `date` |  |
| warranty_until | `date` |  |
| warranty_terms | `text` |  |
| archived_at | `timestamptz` |  |
| type_id | `uuid NOT NULL` | crm_equipment_types |
| property_id | `uuid NOT NULL` | crm_properties |
| warranty_document_id | `uuid` | crm_files |

Unique constraints: primary key only.

Checks: `warranty_until IS NULL OR installed_on IS NULL OR warranty_until >= installed_on`.

## cat_price_versions

Owner: **cat**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| version | `integer NOT NULL CHECK (version > 0)` |  |
| valid_from | `date NOT NULL` |  |
| valid_until | `date` |  |
| unit_price | `numeric(19,4) NOT NULL CHECK (unit_price >= 0)` |  |
| pricebook_id | `uuid NOT NULL` | cat_pricebooks |
| unit_id | `uuid NOT NULL` | cat_units |
| material_id | `uuid` | cat_materials |
| service_id | `uuid` | cat_services |

Unique constraints: `organization_id,pricebook_id,material_id,version`; `organization_id,pricebook_id,service_id,version`.

Checks: `num_nonnulls(material_id,service_id) = 1`; `valid_until IS NULL OR valid_until >= valid_from`.

## cat_checklist_templates

Owner: **cat**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| name | `text NOT NULL` |  |
| version | `integer NOT NULL CHECK (version > 0)` |  |
| service_id | `uuid NOT NULL` | cat_services |

Unique constraints: `organization_id,service_id,version`.

Checks: column checks above.

## cat_material_requirements

Owner: **cat**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Quantity uses the material base unit; no implicit unit conversions.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity > 0)` |  |
| service_id | `uuid NOT NULL` | cat_services |
| material_id | `uuid NOT NULL` | cat_materials |

Unique constraints: `organization_id,service_id,material_id`.

Checks: column checks above.

## import_batches

Owner: **import**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| source_system | `text NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('staged','review','approved','applied','rejected'))` |  |
| started_at | `timestamptz NOT NULL` |  |
| source_file_id | `uuid NOT NULL` | crm_files |
| requested_by | `uuid NOT NULL` | org_members |

Unique constraints: `organization_id,idempotency_key`.

Checks: column checks above.

## agree_benefit_definitions

Owner: **agree**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| name | `text NOT NULL` |  |
| unit | `text NOT NULL` |  |
| service_scope | `text NOT NULL CHECK (service_scope IN ('all','specific'))` |  |
| period_grant | `numeric(18,4) NOT NULL CHECK (period_grant >= 0)` |  |
| eligibility_description | `text NOT NULL` |  |
| requires_approval | `boolean NOT NULL DEFAULT true` |  |
| plan_version_id | `uuid NOT NULL` | agree_plan_versions |
| service_id | `uuid` | cat_services |

Unique constraints: `organization_id,plan_version_id,code`.

Checks: `(service_scope='all' AND service_id IS NULL) OR (service_scope='specific' AND service_id IS NOT NULL)`.

## agree_agreements

Owner: **agree**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Frozen terms and version references; lifecycle dates/status may change only with change history.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| agreement_number | `text NOT NULL` |  |
| starts_on | `date NOT NULL` |  |
| ends_on | `date NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('draft','active','expired','cancelled','review'))` |  |
| renewal_mode | `text NOT NULL CHECK (renewal_mode IN ('manual','automatic','none'))` |  |
| renewal_notice_days | `integer NOT NULL DEFAULT 30 CHECK (renewal_notice_days >= 0)` |  |
| interpretation_state | `text NOT NULL CHECK (interpretation_state IN ('unreviewed','approved','ambiguous','rejected'))` |  |
| interpretation_approved_at | `timestamptz` |  |
| terms_snapshot | `text NOT NULL` |  |
| customer_id | `uuid NOT NULL` | crm_customers |
| plan_version_id | `uuid NOT NULL` | agree_plan_versions |
| source_file_id | `uuid` | crm_files |
| interpretation_reviewer_id | `uuid` | org_members |

Unique constraints: `organization_id,agreement_number`.

Checks: `ends_on >= starts_on`; `interpretation_state <> 'approved' OR (interpretation_reviewer_id IS NOT NULL AND interpretation_approved_at IS NOT NULL)`.

## job_jobs

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| job_number | `text NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('draft','scheduled','in_progress','completed','cancelled','return_required'))` |  |
| planned_scope | `text NOT NULL` |  |
| version | `integer NOT NULL DEFAULT 1 CHECK (version > 0)` |  |
| billing_customer_id | `uuid NOT NULL` | crm_customers |
| property_id | `uuid NOT NULL` | crm_properties |
| branch_id | `uuid NOT NULL` | org_branches |
| job_type_id | `uuid NOT NULL` | cat_job_types |

Unique constraints: `organization_id,job_number`.

Checks: column checks above.

## inv_supplier_materials

Owner: **inv**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| supplier_sku | `text NOT NULL` |  |
| lead_days | `integer CHECK (lead_days >= 0)` |  |
| supplier_id | `uuid NOT NULL` | inv_suppliers |
| material_id | `uuid NOT NULL` | cat_materials |

Unique constraints: `organization_id,supplier_id,supplier_sku`.

Checks: column checks above.

## ai_runs

Owner: **ai**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| provider | `text NOT NULL` |  |
| model | `text NOT NULL` |  |
| prompt_version | `text NOT NULL` |  |
| started_at | `timestamptz NOT NULL` |  |
| finished_at | `timestamptz` |  |
| status | `text NOT NULL CHECK (status IN ('proposed','completed','failed'))` |  |
| input_digest | `text NOT NULL` |  |
| metadata | `jsonb NOT NULL DEFAULT '{}'::jsonb` |  |
| requested_by | `uuid NOT NULL` | org_members |

Unique constraints: primary key only.

Checks: `finished_at IS NULL OR finished_at >= started_at`.

## audit_events

Owner: **audit**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE. Record pointer deliberately survives deletions/archival; structured tenant and actor FK; no automatic application event producer.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| actor_kind | `text NOT NULL CHECK (actor_kind IN ('employee','system','import'))` |  |
| occurred_at | `timestamptz NOT NULL` |  |
| record_table | `text NOT NULL` |  |
| record_id | `uuid NOT NULL` |  |
| action | `text NOT NULL` |  |
| before_values | `jsonb` |  |
| after_values | `jsonb` |  |
| reason | `text NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| actor_id | `uuid` | org_members |

Unique constraints: `organization_id,idempotency_key`.

Checks: `actor_kind <> 'employee' OR actor_id IS NOT NULL`.

## org_technician_qualifications

Owner: **org**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| valid_from | `date NOT NULL` |  |
| valid_until | `date` |  |
| credential_reference | `text` |  |
| technician_id | `uuid NOT NULL` | org_technicians |
| qualification_id | `uuid NOT NULL` | org_qualifications |

Unique constraints: `organization_id,technician_id,qualification_id,valid_from`.

Checks: `valid_until IS NULL OR valid_until >= valid_from`.

## crm_equipment_history

Owner: **crm**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| kind | `text NOT NULL CHECK (kind IN ('installed','relocated','replaced','retired'))` |  |
| effective_at | `timestamptz NOT NULL` |  |
| reason | `text NOT NULL` |  |
| equipment_id | `uuid NOT NULL` | crm_equipment |
| from_property_id | `uuid` | crm_properties |
| to_property_id | `uuid` | crm_properties |
| replacement_equipment_id | `uuid` | crm_equipment |
| evidence_id | `uuid` | crm_files |

Unique constraints: primary key only.

Checks: `kind <> 'relocated' OR (from_property_id IS NOT NULL AND to_property_id IS NOT NULL AND from_property_id <> to_property_id)`; `kind <> 'replaced' OR (replacement_equipment_id IS NOT NULL AND replacement_equipment_id <> equipment_id)`.

## crm_notes

Owner: **crm**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| body | `text NOT NULL` |  |
| author_id | `uuid NOT NULL` | org_members |
| customer_id | `uuid` | crm_customers |
| property_id | `uuid` | crm_properties |
| equipment_id | `uuid` | crm_equipment |
| attachment_id | `uuid` | crm_files |

Unique constraints: primary key only.

Checks: `num_nonnulls(customer_id,property_id,equipment_id) = 1`.

## cat_checklist_items

Owner: **cat**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| position | `integer NOT NULL CHECK (position > 0)` |  |
| instruction | `text NOT NULL` |  |
| required | `boolean NOT NULL DEFAULT true` |  |
| template_id | `uuid NOT NULL` | cat_checklist_templates |

Unique constraints: `organization_id,template_id,position`.

Checks: column checks above.

## import_field_mappings

Owner: **import**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| source_field | `text NOT NULL` |  |
| target_table | `text NOT NULL` |  |
| target_field | `text NOT NULL` |  |
| transform_description | `text NOT NULL` |  |
| batch_id | `uuid NOT NULL` | import_batches |

Unique constraints: `organization_id,batch_id,source_field,target_table,target_field`.

Checks: column checks above.

## import_staging_records

Owner: **import**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| source_identifier | `text NOT NULL` |  |
| original_values | `jsonb NOT NULL` |  |
| normalized_values | `jsonb NOT NULL DEFAULT '{}'::jsonb` |  |
| status | `text NOT NULL CHECK (status IN ('pending','uncertain','approved','rejected','applied'))` |  |
| batch_id | `uuid NOT NULL` | import_batches |

Unique constraints: `organization_id,batch_id,source_identifier`.

Checks: column checks above.

## agree_coverage

Owner: **agree**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Every scope names a property. Explicit all/specific service scope; NULL never means wildcard on its own.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| scope_kind | `text NOT NULL CHECK (scope_kind IN ('property','equipment','trade'))` |  |
| service_scope | `text NOT NULL CHECK (service_scope IN ('all','specific'))` |  |
| valid_from | `date NOT NULL` |  |
| valid_until | `date NOT NULL` |  |
| review_state | `text NOT NULL CHECK (review_state IN ('approved','ambiguous','rejected'))` |  |
| agreement_id | `uuid NOT NULL` | agree_agreements |
| property_id | `uuid NOT NULL` | crm_properties |
| equipment_id | `uuid` | crm_equipment |
| trade_id | `uuid` | org_trades |
| service_id | `uuid` | cat_services |

Unique constraints: primary key only.

Checks: `(scope_kind='property' AND equipment_id IS NULL AND trade_id IS NULL) OR (scope_kind='equipment' AND equipment_id IS NOT NULL AND trade_id IS NULL) OR (scope_kind='trade' AND trade_id IS NOT NULL AND equipment_id IS NULL)`; `(service_scope='all' AND service_id IS NULL) OR (service_scope='specific' AND service_id IS NOT NULL)`; `valid_until >= valid_from`.

## agree_changes

Owner: **agree**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| kind | `text NOT NULL` |  |
| effective_at | `timestamptz NOT NULL` |  |
| reason | `text NOT NULL` |  |
| before_values | `jsonb NOT NULL` |  |
| after_values | `jsonb NOT NULL` |  |
| agreement_id | `uuid NOT NULL` | agree_agreements |
| approved_by | `uuid NOT NULL` | org_members |
| renewal_agreement_id | `uuid` | agree_agreements |

Unique constraints: primary key only.

Checks: column checks above.

## job_trades

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| job_id | `uuid NOT NULL` | job_jobs |
| trade_id | `uuid NOT NULL` | org_trades |

Unique constraints: `organization_id,job_id,trade_id`.

Checks: column checks above.

## job_equipment

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| job_id | `uuid NOT NULL` | job_jobs |
| equipment_id | `uuid NOT NULL` | crm_equipment |

Unique constraints: `organization_id,job_id,equipment_id`.

Checks: column checks above.

## job_tasks

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| description | `text NOT NULL` |  |
| planned_quantity | `numeric(18,4) NOT NULL CHECK (planned_quantity > 0)` |  |
| status | `text NOT NULL CHECK (status IN ('planned','cancelled','confirmed'))` |  |
| job_id | `uuid NOT NULL` | job_jobs |
| service_id | `uuid NOT NULL` | cat_services |
| checklist_template_id | `uuid` | cat_checklist_templates |

Unique constraints: primary key only.

Checks: column checks above.

## job_appointments

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| starts_at | `timestamptz NOT NULL` |  |
| ends_at | `timestamptz NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('scheduled','completed','cancelled'))` |  |
| job_id | `uuid NOT NULL` | job_jobs |

Unique constraints: primary key only.

Checks: `ends_at > starts_at`.

## job_availability

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| starts_at | `timestamptz NOT NULL` |  |
| ends_at | `timestamptz NOT NULL` |  |
| kind | `text NOT NULL CHECK (kind IN ('available','unavailable'))` |  |
| reason | `text NOT NULL` |  |
| technician_id | `uuid NOT NULL` | org_technicians |

Unique constraints: primary key only.

Checks: `ends_at > starts_at`.

## job_time_entries

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| starts_at | `timestamptz NOT NULL` |  |
| ends_at | `timestamptz NOT NULL` |  |
| kind | `text NOT NULL CHECK (kind IN ('labor','travel','break'))` |  |
| job_id | `uuid NOT NULL` | job_jobs |
| technician_id | `uuid NOT NULL` | org_technicians |
| approved_by | `uuid` | org_members |

Unique constraints: primary key only.

Checks: `ends_at > starts_at`.

## job_status_history

Owner: **job**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| from_status | `text` |  |
| to_status | `text NOT NULL` |  |
| changed_at | `timestamptz NOT NULL` |  |
| reason | `text NOT NULL` |  |
| job_id | `uuid NOT NULL` | job_jobs |
| actor_id | `uuid NOT NULL` | org_members |

Unique constraints: primary key only.

Checks: column checks above.

## job_return_links

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| reason | `text NOT NULL` |  |
| original_job_id | `uuid NOT NULL` | job_jobs |
| return_job_id | `uuid NOT NULL` | job_jobs |

Unique constraints: `organization_id,original_job_id,return_job_id`.

Checks: `original_job_id <> return_job_id`.

## job_required_materials

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity > 0)` |  |
| job_id | `uuid NOT NULL` | job_jobs |
| material_id | `uuid NOT NULL` | cat_materials |

Unique constraints: `organization_id,job_id,material_id`.

Checks: column checks above.

## job_readiness_checks

Owner: **job**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| checked_at | `timestamptz NOT NULL` |  |
| result | `text NOT NULL CHECK (result IN ('ready','blocked','unknown'))` |  |
| rule_code | `text NOT NULL` |  |
| reason | `text NOT NULL` |  |
| job_id | `uuid NOT NULL` | job_jobs |
| material_id | `uuid` | cat_materials |
| evidence_file_id | `uuid` | crm_files |

Unique constraints: primary key only.

Checks: column checks above.

## inv_locations

Owner: **inv**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| name | `text NOT NULL` |  |
| kind | `text NOT NULL CHECK (kind IN ('warehouse','truck','quarantine','other'))` |  |
| active | `boolean NOT NULL DEFAULT true` |  |
| branch_id | `uuid NOT NULL` | org_branches |
| technician_id | `uuid` | org_technicians |

Unique constraints: `organization_id,code`.

Checks: column checks above.

## bill_quotes

Owner: **bill**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| quote_number | `text NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('draft','accepted','rejected','expired'))` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |
| valid_until | `date NOT NULL` |  |
| customer_id | `uuid NOT NULL` | crm_customers |
| property_id | `uuid NOT NULL` | crm_properties |
| job_id | `uuid` | job_jobs |

Unique constraints: `organization_id,quote_number`.

Checks: column checks above.

## bill_membership_schedules

Owner: **bill**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| period_start | `date NOT NULL` |  |
| period_end | `date NOT NULL` |  |
| due_on | `date NOT NULL` |  |
| amount | `numeric(19,2) NOT NULL CHECK (amount >= 0)` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |
| status | `text NOT NULL CHECK (status IN ('planned','billed','cancelled'))` |  |
| agreement_id | `uuid NOT NULL` | agree_agreements |

Unique constraints: `organization_id,agreement_id,period_start`.

Checks: `period_end >= period_start`.

## ai_extracted_terms

Owner: **ai**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| field_name | `text NOT NULL` |  |
| proposed_value | `jsonb NOT NULL` |  |
| source_locator | `text NOT NULL` |  |
| evidence_excerpt | `text NOT NULL` |  |
| confidence | `numeric(5,4) CHECK (confidence BETWEEN 0 AND 1)` |  |
| run_id | `uuid NOT NULL` | ai_runs |
| source_file_id | `uuid NOT NULL` | crm_files |

Unique constraints: primary key only.

Checks: column checks above.

## ai_change_sets

Owner: **ai**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| status | `text NOT NULL CHECK (status IN ('proposed','approved','rejected','executed','failed'))` |  |
| summary | `text NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| run_id | `uuid NOT NULL` | ai_runs |

Unique constraints: `organization_id,idempotency_key`.

Checks: column checks above.

## follow_tasks

Owner: **follow**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| title | `text NOT NULL` |  |
| due_at | `timestamptz NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('open','done','cancelled'))` |  |
| remind_at | `timestamptz` |  |
| assigned_to | `uuid NOT NULL` | org_members |
| customer_id | `uuid` | crm_customers |
| job_id | `uuid` | job_jobs |

Unique constraints: primary key only.

Checks: column checks above.

## import_validation_issues

Owner: **import**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| field_name | `text NOT NULL` |  |
| severity | `text NOT NULL CHECK (severity IN ('warning','error'))` |  |
| code | `text NOT NULL` |  |
| description | `text NOT NULL` |  |
| record_id | `uuid NOT NULL` | import_staging_records |

Unique constraints: primary key only.

Checks: column checks above.

## import_duplicate_candidates

Owner: **import**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Candidate is untrusted staging evidence, not an authoritative domain FK.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| candidate_table | `text NOT NULL` |  |
| candidate_id | `uuid NOT NULL` |  |
| reason | `text NOT NULL` |  |
| confidence | `numeric(5,4) CHECK (confidence BETWEEN 0 AND 1)` |  |
| record_id | `uuid NOT NULL` | import_staging_records |

Unique constraints: primary key only.

Checks: column checks above.

## import_decisions

Owner: **import**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| decision | `text NOT NULL CHECK (decision IN ('accept','reject','merge','defer'))` |  |
| reason | `text NOT NULL` |  |
| decided_at | `timestamptz NOT NULL` |  |
| record_id | `uuid NOT NULL` | import_staging_records |
| reviewer_id | `uuid NOT NULL` | org_members |

Unique constraints: primary key only.

Checks: column checks above.

## agree_benefit_accounts

Owner: **agree**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| balance_state | `text NOT NULL CHECK (balance_state IN ('known','unknown'))` |  |
| period_start | `date NOT NULL` |  |
| period_end | `date NOT NULL` |  |
| agreement_id | `uuid NOT NULL` | agree_agreements |
| benefit_definition_id | `uuid NOT NULL` | agree_benefit_definitions |
| source_record_id | `uuid` | import_staging_records |

Unique constraints: `organization_id,agreement_id,benefit_definition_id,period_start`.

Checks: `period_end >= period_start`.

## job_assignments

Owner: **job**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| appointment_id | `uuid NOT NULL` | job_appointments |
| technician_id | `uuid NOT NULL` | org_technicians |

Unique constraints: `organization_id,appointment_id,technician_id`.

Checks: column checks above.

## job_confirmed_work

Owner: **job**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| description | `text NOT NULL` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity > 0)` |  |
| confirmed_at | `timestamptz NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| job_id | `uuid NOT NULL` | job_jobs |
| task_id | `uuid` | job_tasks |
| service_id | `uuid NOT NULL` | cat_services |
| unit_id | `uuid NOT NULL` | cat_units |
| confirmed_by | `uuid NOT NULL` | org_members |

Unique constraints: `organization_id,idempotency_key`.

Checks: column checks above.

## inv_stock_accounts

Owner: **inv**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion. Lock row before changing movements/reservations; on-hand is derived, not an editable opening quantity.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| location_id | `uuid NOT NULL` | inv_locations |
| material_id | `uuid NOT NULL` | cat_materials |

Unique constraints: `organization_id,location_id,material_id`.

Checks: column checks above.

## bill_quote_lines

Owner: **bill**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| position | `integer NOT NULL CHECK (position > 0)` |  |
| kind | `text NOT NULL CHECK (kind IN ('service','labor','material'))` |  |
| description | `text NOT NULL` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity > 0)` |  |
| unit_price | `numeric(19,4) NOT NULL CHECK (unit_price >= 0)` |  |
| discount_amount | `numeric(19,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0)` |  |
| tax_rate | `numeric(9,6) NOT NULL DEFAULT 0 CHECK (tax_rate BETWEEN 0 AND 1)` |  |
| tax_jurisdiction | `text NOT NULL` |  |
| tax_amount | `numeric(19,2) NOT NULL CHECK (tax_amount >= 0)` |  |
| line_total | `numeric(19,2) NOT NULL CHECK (line_total >= 0)` |  |
| quote_id | `uuid NOT NULL` | bill_quotes |
| unit_id | `uuid NOT NULL` | cat_units |
| service_id | `uuid` | cat_services |
| material_id | `uuid` | cat_materials |
| price_version_id | `uuid` | cat_price_versions |
| labor_rate_id | `uuid` | cat_labor_rates |

Unique constraints: `organization_id,quote_id,position`.

Checks: `discount_amount <= round(quantity*unit_price,2)`; `tax_amount = round((round(quantity*unit_price,2)-discount_amount)*tax_rate,2)`; `line_total = round(quantity*unit_price,2)-discount_amount+tax_amount`.

## bill_accepted_scopes

Owner: **bill**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| accepted_at | `timestamptz NOT NULL` |  |
| accepted_name | `text NOT NULL` |  |
| scope_snapshot | `jsonb NOT NULL` |  |
| quote_snapshot | `jsonb NOT NULL` |  |
| quote_id | `uuid NOT NULL` | bill_quotes |
| recorded_by | `uuid NOT NULL` | org_members |
| evidence_id | `uuid` | crm_files |

Unique constraints: `organization_id,quote_id`.

Checks: column checks above.

## ai_actions

Owner: **ai**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE. Non-authoritative proposal only; target is an untrusted suggestion, not a command.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| position | `integer NOT NULL CHECK (position > 0)` |  |
| action_type | `text NOT NULL` |  |
| target_table | `text NOT NULL` |  |
| target_id | `uuid` |  |
| expected_version | `integer` |  |
| proposed_values | `jsonb NOT NULL` |  |
| change_set_id | `uuid NOT NULL` | ai_change_sets |
| evidence_term_id | `uuid` | ai_extracted_terms |

Unique constraints: `organization_id,change_set_id,position`.

Checks: column checks above.

## ai_decisions

Owner: **ai**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| decision | `text NOT NULL CHECK (decision IN ('approved','rejected'))` |  |
| reason | `text NOT NULL` |  |
| decided_at | `timestamptz NOT NULL` |  |
| change_set_id | `uuid NOT NULL` | ai_change_sets |
| reviewer_id | `uuid NOT NULL` | org_members |

Unique constraints: primary key only.

Checks: column checks above.

## follow_message_drafts

Owner: **follow**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| channel | `text NOT NULL CHECK (channel IN ('email','sms'))` |  |
| subject | `text` |  |
| body | `text NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('draft','approved','cancelled'))` |  |
| contact_id | `uuid NOT NULL` | crm_contacts |
| created_by | `uuid NOT NULL` | org_members |
| task_id | `uuid` | follow_tasks |
| approved_by | `uuid` | org_members |

Unique constraints: primary key only.

Checks: `status <> 'approved' OR approved_by IS NOT NULL`.

## import_outcomes

Owner: **import**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| idempotency_key | `text NOT NULL` |  |
| target_table | `text NOT NULL` |  |
| target_id | `uuid` |  |
| outcome | `text NOT NULL` |  |
| executed_at | `timestamptz NOT NULL` |  |
| record_id | `uuid NOT NULL` | import_staging_records |
| decision_id | `uuid NOT NULL` | import_decisions |

Unique constraints: `organization_id,idempotency_key`.

Checks: column checks above.

## job_work_evidence

Owner: **job**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| description | `text NOT NULL` |  |
| work_id | `uuid NOT NULL` | job_confirmed_work |
| file_id | `uuid NOT NULL` | crm_files |

Unique constraints: `organization_id,work_id,file_id`.

Checks: column checks above.

## agree_benefit_ledger

Owner: **agree**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| kind | `text NOT NULL CHECK (kind IN ('grant','consumption','expiration','reversal','adjustment'))` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity <> 0)` |  |
| occurred_at | `timestamptz NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| reason | `text NOT NULL` |  |
| account_id | `uuid NOT NULL` | agree_benefit_accounts |
| job_id | `uuid` | job_jobs |
| work_id | `uuid` | job_confirmed_work |
| source_record_id | `uuid` | import_staging_records |
| reverses_id | `uuid` | agree_benefit_ledger |
| approved_by | `uuid NOT NULL` | org_members |

Unique constraints: `organization_id,idempotency_key`; `organization_id,reverses_id`.

Checks: `(kind='grant' AND quantity>0) OR (kind IN ('consumption','expiration') AND quantity<0) OR kind IN ('reversal','adjustment')`; `(kind='reversal') = (reverses_id IS NOT NULL)`; `kind <> 'consumption' OR work_id IS NOT NULL`.

## agree_planned_visits

Owner: **agree**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| due_from | `date NOT NULL` |  |
| due_until | `date NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('planned','scheduled','completed','cancelled'))` |  |
| agreement_id | `uuid NOT NULL` | agree_agreements |
| property_id | `uuid NOT NULL` | crm_properties |
| service_id | `uuid NOT NULL` | cat_services |
| job_id | `uuid` | job_jobs |
| completed_work_id | `uuid` | job_confirmed_work |

Unique constraints: primary key only.

Checks: `due_until >= due_from`; `status <> 'completed' OR completed_work_id IS NOT NULL`.

## inv_movements

Owner: **inv**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE. Single row stores both legs of a transfer; equal quantity/cost by construction. Posted entries are append-only.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| kind | `text NOT NULL CHECK (kind IN ('opening','receipt','transfer','consumption','usable_return','damaged_return','adjustment','reversal'))` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity > 0)` |  |
| unit_cost | `numeric(19,4) NOT NULL CHECK (unit_cost >= 0)` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |
| occurred_at | `timestamptz NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| reason | `text NOT NULL` |  |
| material_id | `uuid NOT NULL` | cat_materials |
| from_account_id | `uuid` | inv_stock_accounts |
| to_account_id | `uuid` | inv_stock_accounts |
| job_id | `uuid` | job_jobs |
| work_id | `uuid` | job_confirmed_work |
| source_record_id | `uuid` | import_staging_records |
| reverses_id | `uuid` | inv_movements |
| approved_by | `uuid NOT NULL` | org_members |

Unique constraints: `organization_id,idempotency_key`; `organization_id,reverses_id`.

Checks: `num_nonnulls(from_account_id,to_account_id) >= 1`; `from_account_id IS NULL OR to_account_id IS NULL OR from_account_id <> to_account_id`; `kind <> 'transfer' OR (from_account_id IS NOT NULL AND to_account_id IS NOT NULL)`; `kind NOT IN ('opening','receipt','usable_return','damaged_return') OR (from_account_id IS NULL AND to_account_id IS NOT NULL)`; `kind <> 'consumption' OR (from_account_id IS NOT NULL AND to_account_id IS NULL AND work_id IS NOT NULL)`; `(kind='reversal') = (reverses_id IS NOT NULL)`; `kind <> 'opening' OR source_record_id IS NOT NULL`.

## inv_replenishment_policies

Owner: **inv**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| minimum_quantity | `numeric(18,4) NOT NULL CHECK (minimum_quantity >= 0)` |  |
| target_quantity | `numeric(18,4) NOT NULL CHECK (target_quantity >= minimum_quantity)` |  |
| account_id | `uuid NOT NULL` | inv_stock_accounts |
| preferred_supplier_id | `uuid` | inv_suppliers |

Unique constraints: `organization_id,account_id`.

Checks: column checks above.

## bill_invoices

Owner: **bill**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| invoice_number | `text NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('draft','review','issued','void'))` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |
| subtotal | `numeric(19,2) NOT NULL CHECK (subtotal >= 0)` |  |
| discount_total | `numeric(19,2) NOT NULL CHECK (discount_total >= 0)` |  |
| tax_total | `numeric(19,2) NOT NULL CHECK (tax_total >= 0)` |  |
| total | `numeric(19,2) NOT NULL CHECK (total >= 0)` |  |
| version | `integer NOT NULL DEFAULT 1 CHECK (version > 0)` |  |
| billing_customer_id | `uuid NOT NULL` | crm_customers |
| job_id | `uuid` | job_jobs |
| accepted_scope_id | `uuid` | bill_accepted_scopes |

Unique constraints: `organization_id,invoice_number`.

Checks: `total = subtotal-discount_total+tax_total`.

## ai_execution_outcomes

Owner: **ai**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| status | `text NOT NULL CHECK (status IN ('succeeded','failed','skipped'))` |  |
| record_table | `text` |  |
| record_id | `uuid` |  |
| error_code | `text` |  |
| executed_at | `timestamptz NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| action_id | `uuid NOT NULL` | ai_actions |
| decision_id | `uuid NOT NULL` | ai_decisions |

Unique constraints: `organization_id,idempotency_key`.

Checks: column checks above.

## follow_delivery_attempts

Owner: **follow**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| attempt | `integer NOT NULL CHECK (attempt > 0)` |  |
| attempted_at | `timestamptz NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('pending','succeeded','failed'))` |  |
| provider_reference | `text` |  |
| error_code | `text` |  |
| retry_after | `timestamptz` |  |
| draft_id | `uuid NOT NULL` | follow_message_drafts |

Unique constraints: `organization_id,draft_id,attempt`.

Checks: column checks above.

## agree_benefit_reservations

Owner: **agree**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity > 0)` |  |
| status | `text NOT NULL CHECK (status IN ('active','released','consumed'))` |  |
| reserved_at | `timestamptz NOT NULL` |  |
| resolved_at | `timestamptz` |  |
| resolution_reason | `text` |  |
| idempotency_key | `text NOT NULL` |  |
| account_id | `uuid NOT NULL` | agree_benefit_accounts |
| job_id | `uuid NOT NULL` | job_jobs |
| consumption_entry_id | `uuid` | agree_benefit_ledger |

Unique constraints: `organization_id,idempotency_key`.

Checks: `(status='active' AND resolved_at IS NULL) OR (status<>'active' AND resolved_at IS NOT NULL AND resolution_reason IS NOT NULL)`; `(status='consumed') = (consumption_entry_id IS NOT NULL)`.

## inv_reservations

Owner: **inv**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity > 0)` |  |
| status | `text NOT NULL CHECK (status IN ('active','released','consumed'))` |  |
| reserved_at | `timestamptz NOT NULL` |  |
| resolved_at | `timestamptz` |  |
| resolution_reason | `text` |  |
| idempotency_key | `text NOT NULL` |  |
| account_id | `uuid NOT NULL` | inv_stock_accounts |
| job_id | `uuid NOT NULL` | job_jobs |
| consumption_movement_id | `uuid` | inv_movements |

Unique constraints: `organization_id,idempotency_key`.

Checks: `(status='active' AND resolved_at IS NULL) OR (status<>'active' AND resolved_at IS NOT NULL AND resolution_reason IS NOT NULL)`; `(status='consumed') = (consumption_movement_id IS NOT NULL)`.

## bill_invoice_lines

Owner: **bill**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| position | `integer NOT NULL CHECK (position > 0)` |  |
| kind | `text NOT NULL CHECK (kind IN ('service','labor','material'))` |  |
| description | `text NOT NULL` |  |
| quantity | `numeric(18,4) NOT NULL CHECK (quantity > 0)` |  |
| unit_price | `numeric(19,4) NOT NULL CHECK (unit_price >= 0)` |  |
| discount_amount | `numeric(19,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0)` |  |
| tax_rate | `numeric(9,6) NOT NULL DEFAULT 0 CHECK (tax_rate BETWEEN 0 AND 1)` |  |
| tax_jurisdiction | `text NOT NULL` |  |
| tax_amount | `numeric(19,2) NOT NULL CHECK (tax_amount >= 0)` |  |
| line_total | `numeric(19,2) NOT NULL CHECK (line_total >= 0)` |  |
| invoice_id | `uuid NOT NULL` | bill_invoices |
| unit_id | `uuid NOT NULL` | cat_units |
| service_id | `uuid` | cat_services |
| material_id | `uuid` | cat_materials |
| price_version_id | `uuid` | cat_price_versions |
| labor_rate_id | `uuid` | cat_labor_rates |
| work_id | `uuid` | job_confirmed_work |
| benefit_entry_id | `uuid` | agree_benefit_ledger |

Unique constraints: `organization_id,invoice_id,position`.

Checks: `discount_amount <= round(quantity*unit_price,2)`; `tax_amount = round((round(quantity*unit_price,2)-discount_amount)*tax_rate,2)`; `line_total = round(quantity*unit_price,2)-discount_amount+tax_amount`.

## bill_issued_snapshots

Owner: **bill**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| issued_at | `timestamptz NOT NULL` |  |
| customer_snapshot | `jsonb NOT NULL` |  |
| address_snapshot | `jsonb NOT NULL` |  |
| lines_snapshot | `jsonb NOT NULL CHECK (jsonb_typeof(lines_snapshot)='array')` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |
| total | `numeric(19,2) NOT NULL CHECK (total >= 0)` |  |
| idempotency_key | `text NOT NULL` |  |
| invoice_id | `uuid NOT NULL` | bill_invoices |
| issued_by | `uuid NOT NULL` | org_members |

Unique constraints: `organization_id,invoice_id`; `organization_id,idempotency_key`.

Checks: column checks above.

## report_events

Owner: **report**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE. Optional ordinary PostgreSQL reporting projection. No retention policy or hypertable; authoritative records are elsewhere.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| event_type | `text NOT NULL CHECK (event_type IN ('job_status','readiness','inventory','billing_exception','billing_resolution'))` |  |
| occurred_at | `timestamptz NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| is_fictional | `boolean NOT NULL DEFAULT false` |  |
| payload | `jsonb NOT NULL DEFAULT '{}'::jsonb` |  |
| job_id | `uuid` | job_jobs |
| movement_id | `uuid` | inv_movements |
| invoice_id | `uuid` | bill_invoices |

Unique constraints: `organization_id,idempotency_key`.

Checks: column checks above.

## bill_review_flags

Owner: **bill**. PK: `organization_id,id`. Mutable operational record; FK-restricted deletion.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| code | `text NOT NULL` |  |
| reason | `text NOT NULL` |  |
| status | `text NOT NULL CHECK (status IN ('open','resolved','dismissed'))` |  |
| resolution | `text` |  |
| resolved_at | `timestamptz` |  |
| invoice_id | `uuid NOT NULL` | bill_invoices |
| line_id | `uuid` | bill_invoice_lines |
| evidence_file_id | `uuid` | crm_files |
| evidence_work_id | `uuid` | job_confirmed_work |
| reviewer_id | `uuid` | org_members |

Unique constraints: primary key only.

Checks: `status = 'open' OR (resolution IS NOT NULL AND resolved_at IS NOT NULL AND reviewer_id IS NOT NULL)`.

## bill_corrections

Owner: **bill**. PK: `organization_id,id`. Append-only; a trigger rejects UPDATE/DELETE.

| Column | SQL type/default/nullability | Reference |
|---|---|---|
| organization_id | `uuid NOT NULL` | org_organizations.id |
| id | `uuid NOT NULL DEFAULT gen_random_uuid()` |  |
| created_at | `timestamptz NOT NULL DEFAULT now()` |  |
| kind | `text NOT NULL CHECK (kind IN ('credit','correction'))` |  |
| amount | `numeric(19,2) NOT NULL CHECK (amount <> 0)` |  |
| currency | `text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')` |  |
| reason | `text NOT NULL` |  |
| issued_at | `timestamptz NOT NULL` |  |
| line_snapshot | `jsonb NOT NULL` |  |
| idempotency_key | `text NOT NULL` |  |
| issued_snapshot_id | `uuid NOT NULL` | bill_issued_snapshots |
| approved_by | `uuid NOT NULL` | org_members |

Unique constraints: `organization_id,idempotency_key`.

Checks: column checks above.

## Tooling tables

`goob_db_meta.migrations`: version text PK, sha256 text NOT NULL, applied_at timestamptz NOT NULL. Database-owned migration history, no tenant. Checksums prevent silently rewriting applied SQL.

`goob_db_meta.fixture_rows`: organization_id UUID, table_name text, record_id UUID, row_snapshot JSONB, as_of date; composite primary key (organization_id,table_name,record_id). Tooling-owned fixture manifest, no domain cascade or application dependency. Full snapshots detect edits and restrict reset to the exact known fixture set.

Read models: `inv_balances`, `agree_balances`, `bill_invoice_reconciliation`. These views calculate from records and are never seeded. Additional integrity triggers and view definitions are in migrations 002 and 003; see INTEGRITY.md for their contracts.