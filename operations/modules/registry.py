REGISTRY = {
    'crm': {'requires': [], 'permissions': ['read'], 'navigation': 'Customers'},
    'agreements': {'requires': ['crm'], 'permissions': ['read'], 'navigation': 'Coverage'},
    'inventory': {'requires': [], 'permissions': ['read'], 'navigation': 'Materials'},
    'billing': {'requires': [], 'permissions': ['approve'], 'navigation': 'Billing review'},
    'workflow': {'requires': ['crm', 'agreements', 'inventory', 'billing'], 'permissions': ['propose', 'approve'], 'navigation': 'Work review'},
    'readiness': {'requires': ['inventory'], 'permissions': ['read'], 'navigation': 'Readiness'},
}
for module in REGISTRY.values():
    module.update(optional_integrations=[], settings={}, events=[])
REGISTRY['workflow']['events'] = ['work.approved.v1']
ROLES = {'owner': {'read', 'propose', 'approve', 'configure'}, 'billing_reviewer': {'read', 'propose', 'approve'}, 'technician': {'read', 'propose'}, 'dispatcher': {'read'}}

def guard(db, tenant, role, module, permission):
    if permission not in ROLES.get(role, set()):
        raise ValueError('This demo role does not have permission for this command.')
    import json
    row = db.execute('SELECT modules FROM tenants WHERE id=?', (tenant,)).fetchone()
    if not row or module not in json.loads(row['modules']):
        raise ValueError('Module disabled or tenant unavailable.')
    for dependency in REGISTRY[module]['requires']:
        guard(db, tenant, role, dependency, 'read')

def configure(db, tenant, role, enabled):
    import json
    if 'configure' not in ROLES.get(role, set()):
        raise ValueError('Owner permission required.')
    if not isinstance(enabled, list) or any(x not in REGISTRY for x in enabled):
        raise ValueError('Unknown module.')
    for name in enabled:
        if not set(REGISTRY[name]['requires']).issubset(enabled):
            raise ValueError(f'{name} requires {REGISTRY[name]["requires"]}. Disable dependants first.')
    db.execute('UPDATE tenants SET modules=? WHERE id=?', (json.dumps(enabled), tenant))
