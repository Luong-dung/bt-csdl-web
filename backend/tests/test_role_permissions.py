"""W48-04: global permissions read from role_permissions (SQLite by default, PostgreSQL with --postgres)."""
from datetime import date, timedelta

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, inspect, select, text

from config.database import get_db
from core.permissions import PERMISSIONS, ROLE_PERMISSIONS, TOURNAMENT_CREATE
from core.security import create_access_token, hash_password
from main import create_app
from middleware.auth import has_permission, has_role
from modules.identity.models import Permission, Role, RoleAssignment, User, role_permissions
from seed import ROLE_NAMES, seed_reference_data
from test_roster_migration import migration_config

pytestmark = pytest.mark.postgres
PREVIOUS = 'f47a04b00001'
# The role checks each permission replaced (pre-W48-04 code); the default grants must match them.
LEGACY_ROLES = {
    'CATALOG_MANAGE': ('ADMIN',),
    'ORGANIZATION_CREATE': ('ADMIN',),
    'TOURNAMENT_CREATE': ('ADMIN', 'ORGANIZER'),
    'AUDIT_LOG_VIEW_ALL': ('ADMIN',),
    'ROLE_ASSIGNMENT_MANAGE': ('ADMIN',),
}
CAPABILITY = {'CATALOG_MANAGE': 'can_manage_catalog', 'TOURNAMENT_CREATE': 'can_create_tournament',
              'AUDIT_LOG_VIEW_ALL': 'can_view_audit', 'ORGANIZATION_CREATE': 'can_create_organization'}


@pytest.fixture
def env(base_session_factory):
    factory = base_session_factory
    with factory.begin() as db:
        roles = dict(db.execute(select(Role.role_name, Role.role_id)).all())
        users = {}
        for name in ROLE_NAMES:
            user = User(username=f'rp_{name.lower()}', email=f'rp_{name.lower()}@example.com',
                        password_hash=hash_password('Password-2026'), role_id=roles[name])
            db.add(user)
            db.flush()
            users[name] = user.user_id
    app = create_app()

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    def headers(user_id):
        return {'Authorization': 'Bearer ' + create_access_token({'sub': str(user_id)})}

    return factory, client, users, roles, headers


def test_default_grants_match_legacy_role_checks(env):
    factory, client, users, _, headers = env
    assert set(LEGACY_ROLES) == {name for name, _ in PERMISSIONS}
    with factory() as db:
        for role_name, user_id in users.items():
            user = db.get(User, user_id)
            for permission, legacy in LEGACY_ROLES.items():
                assert has_permission(user, permission) == has_role(user, *legacy) == (role_name in legacy), \
                    (role_name, permission)
    for role_name, user_id in users.items():
        body = client.get('/api/v1/auth/capabilities', headers=headers(user_id)).json()
        assert body == {field: role_name in LEGACY_ROLES[p] for p, field in CAPABILITY.items()}, role_name


def test_global_assignment_grants_but_scoped_assignment_does_not(env):
    factory, _, users, roles, _ = env
    with factory.begin() as db:
        db.add_all([
            RoleAssignment(user_id=users['VIEWER'], role_id=roles['ORGANIZER'], scope_type='GLOBAL'),
            RoleAssignment(user_id=users['PLAYER'], role_id=roles['ORGANIZER'], scope_type='TOURNAMENT', scope_id=1),
            RoleAssignment(user_id=users['REFEREE'], role_id=roles['ADMIN'], scope_type='GLOBAL',
                           revoked_at=func.now()),
        ])
    with factory() as db:
        viewer, player, referee = (db.get(User, users[n]) for n in ('VIEWER', 'PLAYER', 'REFEREE'))
        assert has_permission(viewer, TOURNAMENT_CREATE) and has_role(viewer, 'ADMIN', 'ORGANIZER')
        assert not has_permission(player, TOURNAMENT_CREATE) and not has_role(player, 'ADMIN', 'ORGANIZER')
        # Revoked assignments grant nothing.
        assert not any(has_permission(referee, name) for name, _ in PERMISSIONS)


def test_checks_follow_the_table_not_hard_coded_roles(env):
    factory, client, users, roles, headers = env
    organizer = headers(users['ORGANIZER'])
    body = {'name': 'RP cup', 'game_id': 1, 'format': 'SINGLE_ELIM',
            'start_date': (date.today() + timedelta(days=7)).isoformat()}
    with factory.begin() as db:
        body['game_id'] = db.scalar(text('SELECT min(game_id) FROM games'))
        tournament_create, catalog = (db.scalar(select(Permission.permission_id).where(
            Permission.permission_name == n)) for n in (TOURNAMENT_CREATE, 'CATALOG_MANAGE'))
        db.execute(delete(role_permissions).where(role_permissions.c.role_id == roles['ORGANIZER'],
                                                  role_permissions.c.permission_id == tournament_create))
        db.execute(role_permissions.insert().values(role_id=roles['ORGANIZER'], permission_id=catalog))
    assert client.post('/api/v1/tournaments', json=body, headers=organizer).status_code == 403
    caps = client.get('/api/v1/auth/capabilities', headers=organizer).json()
    assert (caps['can_create_tournament'], caps['can_manage_catalog']) == (False, True)
    assert client.post('/api/v1/catalog/publishers', json={'name': 'RP publisher'},
                       headers=organizer).status_code == 201
    # ADMIN is not special-cased for global permissions either.
    with factory.begin() as db:
        db.execute(delete(role_permissions).where(role_permissions.c.role_id == roles['ADMIN']))
    admin = headers(users['ADMIN'])
    assert client.get('/api/v1/admin/audit-logs', headers=admin).status_code == 403
    assert client.get('/api/v1/admin/role-assignments', headers=admin).status_code == 403
    assert client.post('/api/v1/organizations', json={'name': 'RP org'}, headers=admin).status_code == 403


def test_reseed_keeps_removed_grants_removed(env):
    factory, _, _, roles, _ = env
    with factory.begin() as db:
        db.execute(delete(role_permissions).where(role_permissions.c.role_id == roles['ORGANIZER']))
    with factory.begin() as db:
        added = seed_reference_data(db)
        assert (added['permissions'], added['role_permissions']) == (0, 0)
        assert db.scalar(select(func.count()).select_from(role_permissions)) == len(ROLE_PERMISSIONS['ADMIN'])


def test_role_permissions_upgrade_downgrade(request, base_session_factory):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    with base_session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, PREVIOUS)
        assert not inspect(connection).has_table('role_permissions')
        assert connection.scalar(text('SELECT count(*) FROM permissions')) == 0
        # Upgrading a database that already has roles writes the default permissions and grants.
        command.upgrade(config, 'head')
        inspector = inspect(connection)
        assert inspector.get_pk_constraint('role_permissions')['constrained_columns'] == ['role_id', 'permission_id']
        assert {(fk['referred_table'], fk['options'].get('ondelete')) for fk in inspector.get_foreign_keys(
            'role_permissions')} == {('roles', 'CASCADE'), ('permissions', 'CASCADE')}
        grants = set(connection.execute(text(
            'SELECT r.role_name, p.permission_name FROM role_permissions rp JOIN roles r USING (role_id) '
            'JOIN permissions p USING (permission_id)')).all())
        assert grants == {(role, p) for role, names in ROLE_PERMISSIONS.items() for p in names}
        # A second downgrade/upgrade round trip is clean.
        command.downgrade(config, PREVIOUS)
        command.upgrade(config, 'head')
        assert connection.scalar(text('SELECT count(*) FROM role_permissions')) == len(grants)
