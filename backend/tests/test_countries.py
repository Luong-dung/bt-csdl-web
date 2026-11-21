"""W47-04 (W03-02): countries API and competition area ↔ country link."""

import pytest
from sqlalchemy import select

import routes.catalog
from modules.identity.models import AuditLog
from test_catalog_api import session_factory
from test_permissions import access

pytestmark = pytest.mark.postgres

COUNTRIES = '/api/v1/catalog/countries'
AREAS = '/api/v1/catalog/areas'


def country_logs(session_factory):
    with session_factory() as db:
        return db.scalars(select(AuditLog).where(AuditLog.resource == 'country').order_by(AuditLog.log_id)).all()


def test_seeded_countries_are_public(access):
    client, *_ = access
    codes = {c['country_code']: c['name'] for c in client.get(COUNTRIES).json()}
    assert {'VN', 'KR', 'TH'} <= set(codes) and codes['VN'] == 'Việt Nam'
    assert client.get(COUNTRIES + '/vn').json() == {'country_code': 'VN', 'name': 'Việt Nam'}
    assert client.get(COUNTRIES + '/XX').status_code == 404
    areas = {a['code']: a for a in client.get(AREAS).json()}
    assert areas['VN']['country_code'] == 'VN' and areas['GLOBAL']['country_code'] is None
    assert {a['code'] for a in client.get(AREAS, params={'country_code': 'vn'}).json()} == {'VN', 'VN-HCM', 'AOG'}


def test_create_and_rename_country_admin_only_with_audit(access, session_factory):
    client, headers, users, *_ = access
    payload = {'country_code': ' jp ', 'name': 'Nhật Bản'}
    assert client.post(COUNTRIES, json=payload).status_code == 401
    assert client.post(COUNTRIES, json=payload, headers=headers('organizer')).status_code == 403
    created = client.post(COUNTRIES, json=payload, headers=headers('admin'))
    assert created.status_code == 201 and created.json() == {'country_code': 'JP', 'name': 'Nhật Bản'}
    assert client.patch(COUNTRIES + '/JP', json={'name': 'Japan'}, headers=headers('viewer')).status_code == 403
    renamed = client.patch(COUNTRIES + '/jp', json={'name': 'Japan'}, headers=headers('admin'))
    assert renamed.status_code == 200 and renamed.json()['name'] == 'Japan'
    # Same name again is a no-op without a new audit row.
    assert client.patch(COUNTRIES + '/JP', json={'name': 'Japan'}, headers=headers('admin')).status_code == 200
    logs = country_logs(session_factory)
    assert [(log.action, log.user_id, log.resource_id) for log in logs] == [
        ('CATALOG_COUNTRY_CREATED', users['admin'], None), ('CATALOG_COUNTRY_UPDATED', users['admin'], None)]
    assert logs[0].details == {'country_code': 'JP', 'before': None, 'after': {'country_code': 'JP', 'name': 'Nhật Bản'}}
    assert logs[1].details['before']['name'] == 'Nhật Bản'


@pytest.mark.parametrize('payload', [
    {}, {'country_code': 'VNM', 'name': 'Ba chữ'}, {'country_code': 'V1', 'name': 'Số'},
    {'country_code': 'XX', 'name': 'x'}, {'country_code': 'XX'}, {'country_code': 'XX', 'name': 'Ok', 'extra': 1},
])
def test_invalid_country_422(access, session_factory, payload):
    client, headers, *_ = access
    assert client.post(COUNTRIES, json=payload, headers=headers('admin')).status_code == 422
    assert country_logs(session_factory) == []


def test_duplicate_country_409(access, session_factory):
    client, headers, *_ = access
    assert client.post(COUNTRIES, json={'country_code': 'vn', 'name': 'Khác'}, headers=headers('admin')).status_code == 409
    assert client.post(COUNTRIES, json={'country_code': 'XX', 'name': 'Việt Nam'}, headers=headers('admin')).status_code == 409
    assert client.patch(COUNTRIES + '/KR', json={'name': 'Việt Nam'}, headers=headers('admin')).status_code == 409
    assert client.patch(COUNTRIES + '/XX', json={'name': 'Mới'}, headers=headers('admin')).status_code == 404
    assert client.patch(COUNTRIES + '/KR', json={'name': None}, headers=headers('admin')).status_code == 422
    assert country_logs(session_factory) == []


def test_area_country_link_create_update_clear(access, session_factory):
    client, headers, *_ = access
    created = client.post(AREAS, json={'name': 'Seoul', 'code': 'KR-SEL', 'country_code': 'kr'}, headers=headers('admin'))
    assert created.status_code == 201 and created.json()['country_code'] == 'KR'
    area = created.json()['area_id']
    assert client.post(AREAS, json={'name': 'Nowhere', 'code': 'NOPE', 'country_code': 'XX'},
                       headers=headers('admin')).status_code == 422
    assert client.patch(f'{AREAS}/{area}', json={'country_code': 'ZZ'}, headers=headers('admin')).status_code == 422
    assert client.patch(f'{AREAS}/{area}', json={'country_code': 'K'}, headers=headers('admin')).status_code == 422
    moved = client.patch(f'{AREAS}/{area}', json={'country_code': 'vn'}, headers=headers('admin'))
    assert moved.status_code == 200 and moved.json()['country_code'] == 'VN'
    cleared = client.patch(f'{AREAS}/{area}', json={'country_code': None}, headers=headers('admin'))
    assert cleared.status_code == 200 and cleared.json()['country_code'] is None
    with session_factory() as db:
        log = db.scalars(select(AuditLog).where(AuditLog.action == 'CATALOG_AREA_UPDATED')
                         .order_by(AuditLog.log_id.desc())).first()
        assert (log.details['before']['country_code'], log.details['after']['country_code']) == ('VN', None)


def test_country_audit_failure_rolls_back(access, monkeypatch):
    client, headers, *_ = access
    def broken(*args, **kwargs):
        raise RuntimeError('audit down')
    monkeypatch.setattr(routes.catalog, 'record_audit', broken)
    with pytest.raises(RuntimeError):
        client.post(COUNTRIES, json={'country_code': 'JP', 'name': 'Nhật Bản'}, headers=headers('admin'))
    assert client.get(COUNTRIES + '/JP').status_code == 404
