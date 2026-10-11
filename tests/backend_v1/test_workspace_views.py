from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError
from operations.domain.workspace_views import Configuration, WIDGETS
from operations.domain.common import Problem


def config(page='dispatch'):
    ids = sorted(WIDGETS[page])
    return {'version': 1, 'layouts': {
        bp: [{'i': key, 'x': 0, 'y': n*7, 'w': cols, 'h': 7} for n, key in enumerate(ids)]
        for bp, cols in [('lg', 12), ('md', 6), ('sm', 1)]
    }, 'hidden': [], 'columns': ['customer', 'trade', 'status', 'technician', 'time'],
        'preferences': {'trade': 'All', 'jobStatus': 'All', 'available': False, 'names': True, 'routes': True, 'density': 'comfortable'}, 'mode': '2D'}


@pytest.mark.parametrize('page', ['overview', 'dispatch'])
def test_configuration(page):
    c = config(page)
    assert Configuration(**c).for_page(page) == c
    invalid = deepcopy(c)
    invalid['layouts']['sm'][0]['w'] = 2
    with pytest.raises(Problem):
        Configuration(**invalid).for_page(page)
    invalid = deepcopy(c)
    invalid['hidden'] = sorted(WIDGETS[page])
    with pytest.raises(Problem):
        Configuration(**invalid).for_page(page)
    invalid = deepcopy(c)
    invalid['records'] = [{'customer': 'copied data'}]
    with pytest.raises(ValidationError):
        Configuration(**invalid)


def test_personal_persistence_isolation_and_revisions(api):
    body = {'page': 'dispatch', 'name': 'My desk', 'configuration': config()}
    key = str(uuid4())
    saved = api.request('POST', '/workspace-views', body, expected=201, key=key)
    assert api.request('POST', '/workspace-views', body, expected=201, key=key)['id'] == saved['id']
    snapshot = api.request('GET', '/workspace-views?page=dispatch')
    assert snapshot['activeViewId'] == saved['id']
    assert len(snapshot['views']) == 1
    assert snapshot['views'][0]['configuration'] == body['configuration']
    assert api.request('GET', '/workspace-views?page=dispatch', role='office')['views'] == []
    assert api.request('GET', '/workspace-views?page=dispatch', role='other', company=api.other)['views'] == []
    update = {'revision': 1, 'name': 'Renamed', 'configuration': config()}
    api.request('PATCH', '/workspace-views/'+saved['id'], update, role='office', expected=404)
    api.request('PATCH', '/workspace-views/'+saved['id'], update, role='other', company=api.other, expected=404)
    updated = api.request('PATCH', '/workspace-views/'+saved['id'], update)
    assert updated['revision'] == 2
    api.request('PATCH', '/workspace-views/'+saved['id'], update, expected=409)
    api.request('DELETE', '/workspace-views/'+saved['id'], {'revision': 1}, expected=409)
    api.request('POST', '/workspace-views/selection', {'page':'overview','view_id':saved['id']}, expected=422)
    api.request('POST', '/workspace-views/selection', {'page':'dispatch','view_id':saved['id']}, role='office', expected=404)
    api.request('DELETE', '/workspace-views/'+saved['id'], {'revision':2})
    assert api.request('GET', '/workspace-views?page=dispatch')['activeViewId'] is None


def test_owner_team_default_and_personal_fallback(api):
    personal = api.request('POST', '/workspace-views', {'page':'overview','name':'Private','configuration':config('overview')}, role='viewer', expected=201)
    publication = {'page':'overview','name':'Company','configuration':config('overview'),'revision':0}
    for role in ['office','tech','viewer']:
        api.request('POST','/workspace-views/team-default',publication,role=role,expected=403)
    published = api.request('POST','/workspace-views/team-default',publication)
    assert published['revision'] == 1
    snapshot = api.request('GET','/workspace-views?page=overview',role='viewer')
    assert snapshot['activeViewId'] == personal['id']
    assert snapshot['teamDefault']['name'] == 'Company'
    api.request('POST','/workspace-views/team-default',publication,expected=409)
    api.request('POST','/workspace-views/selection',{'page':'overview','view_id':None},role='viewer')
    snapshot = api.request('GET','/workspace-views?page=overview',role='viewer')
    assert snapshot['activeViewId'] is None
    assert len(snapshot['views']) == 1
    assert snapshot['teamDefault']['id'] == published['id']
    assert api.request('GET','/workspace-views?page=overview',role='other',company=api.other)['teamDefault'] is None
    api.request('PATCH','/workspace-views/'+published['id'],{'revision':1,'name':'Bypass','configuration':config('overview')},expected=404)
    assert api.client.get('/api/v1/workspace-views?page=overview').status_code == 401


@pytest.mark.parametrize('mutation', ['widget','bounds','columns','settings'])
def test_invalid_configuration_rejected(api, mutation):
    c = config()
    if mutation == 'widget': c['layouts']['lg'][0]['i'] = 'unknown'
    if mutation == 'bounds': c['layouts']['md'][0]['x'] = 6
    if mutation == 'columns': c['columns'] = ['secret']
    if mutation == 'settings': c['preferences']['names'] = 'true'
    api.request('POST','/workspace-views',{'page':'dispatch','name':'Invalid','configuration':c},expected=422)
    assert api.request('GET','/workspace-views?page=dispatch')['views'] == []


def test_cookie_session_owns_tenant_and_stable_identity(api, engine):
    from operations.api_v1.portal_auth import password_hash
    from operations.persistence.database import sessions
    from operations.persistence.models import PortalUser
    user_id, identifier = str(uuid4()), 'workspace-'+str(uuid4())+'@test.local'
    with sessions(engine)() as db:
        db.add(PortalUser(id=user_id,identifier=identifier,password_hash=password_hash('isolated-test-password'),tenant_id=api.tenant,subject='owner',demo=True))
        db.commit()
    response=api.client.post('/api/auth/sign-in',json={'identifier':identifier,'password':'isolated-test-password'})
    assert response.status_code == 200
    account=response.json()
    assert account['userId'] == user_id
    assert account['tenant'] == api.tenant
    assert account['role'] == 'owner'
    body={'page':'dispatch','name':'Session view','configuration':config()}
    response=api.client.post('/api/v1/workspace-views',json=body,headers={'Idempotency-Key':str(uuid4()),'X-Tenant-ID':api.other})
    assert response.status_code == 201
    assert response.json()['tenant_id'] == api.tenant
    view_id=response.json()['id']
    assert api.client.get('/api/v1/workspace-views?page=dispatch').json()['activeViewId'] == view_id
    assert api.request('GET','/workspace-views?page=dispatch',role='other',company=api.other)['views'] == []
    assert api.client.post('/api/v1/workspace-views',json=body,headers={'Idempotency-Key':str(uuid4()),'Origin':'https://untrusted.test'}).status_code == 403
    assert api.client.request('DELETE','/api/v1/workspace-views/'+view_id,json={'revision':1},headers={'Idempotency-Key':str(uuid4())}).status_code == 200


@pytest.mark.parametrize('previous', ['20261013_workspace_views', '20261014_view_preferences', '20261015_merge_workspace_views', 'cloud_invoice_preferences'])
def test_merge_upgrades_both_histories_without_replacing_preferences(engine, previous):
    from alembic import command as migrations
    from alembic.config import Config
    from sqlalchemy import insert, text
    from operations.persistence.models import Tenant
    from operations.persistence.readiness import SCHEMA_REVISION, check_schema
    schema='goob_test_merge_'+uuid4().hex
    tenant=str(uuid4())
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        with engine.begin() as connection:
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", pg_catalog'))
            cfg=Config('alembic-backend.ini')
            cfg.attributes['connection']=connection
            if previous == 'cloud_invoice_preferences':
                migrations.upgrade(cfg,'20261013_invoice_editor')
                migrations.upgrade(cfg,'20261014_view_preferences')
                migrations.stamp(cfg,'20261014_view_preferences',purge=True)
                connection.execute(text("SELECT setval('invoice_number_v1',42,true)"))
            else:
                migrations.upgrade(cfg,previous)
            connection.execute(insert(Tenant).values(id=tenant,name='Merge fixture'))
            if previous in {'20261014_view_preferences','cloud_invoice_preferences'}:
                connection.execute(text("INSERT INTO view_preferences_v1(tenant_id,subject,page,revision,settings) VALUES (:tenant,'owner','dispatch',4,CAST(:settings AS jsonb))"),{'tenant':tenant,'settings':'{\"names\":false}'})
            migrations.upgrade(cfg,'head')
            assert check_schema(connection)['revision'] == SCHEMA_REVISION
            assert connection.scalar(text('SELECT count(*) FROM workspace_views_v1')) == 0
            assert connection.scalar(text('SELECT count(*) FROM tenants_v1')) == 1
            if previous == 'cloud_invoice_preferences':
                assert connection.scalar(text("SELECT nextval('invoice_number_v1')")) == 43
            if previous in {'20261014_view_preferences','cloud_invoice_preferences'}:
                row=connection.execute(text('SELECT revision,settings FROM view_preferences_v1')).one()
                assert tuple(row) == (4, {'names':False})
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
