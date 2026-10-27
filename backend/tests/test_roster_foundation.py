from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from core.audit import record_audit
from core.rosters import get_editable_roster_context, lock_roster_memberships, lock_roster_rows
from modules.identity.models import AuditLog, RoleAssignment, User
from modules.teams.models import Team, TeamMembership
from modules.tournaments.models import Tournament, TournamentRegistration, TournamentRoster
from modules.tournaments.roster_schemas import RosterReplace
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


@pytest.fixture
def accepted(access, session_factory):
    client, headers, users, teams, _ = access
    tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.add(TournamentRegistration(tournament_id=tid, team_id=teams['Alpha'], status='APPROVED',
                                     reviewed_at=datetime.now(timezone.utc)))
        db.add_all([
            TeamMembership(team_id=teams['Alpha'], user_id=users['manager'], role_in_team='MANAGER'),
            TeamMembership(team_id=teams['Alpha'], user_id=users['viewer'], role_in_team='PLAYER'),
        ])
    return tid


def caps(tid, team_id):
    return f'/api/v1/tournaments/{tid}/teams/{team_id}/roster/capabilities'


@pytest.mark.parametrize('name,view,edit,lock', [
    ('admin', True, True, True), ('organizer', True, False, True),
    ('manager', True, True, False), ('viewer', False, False, False),
])
def test_roster_capabilities_match_context_permissions(access, session_factory, accepted, name, view, edit, lock):
    client, headers, users, teams, _ = access
    response = client.get(caps(accepted, teams['Alpha']), headers=headers(name))
    assert response.status_code == 200
    assert response.json() == {'tournament_id': accepted, 'team_id': teams['Alpha'],
                               'can_view_roster': view, 'can_edit_roster': edit}
    assert response.headers['cache-control'] == 'private, no-store'
    tournament_caps = client.get(f'/api/v1/tournaments/{accepted}/capabilities', headers=headers(name)).json()
    assert tournament_caps['can_lock_roster'] == lock
    assert tournament_caps['roster_locked'] is False
    with session_factory() as db:
        if edit:
            tournament, actor = get_editable_roster_context(db, accepted, teams['Alpha'], db.get(User, users[name]))
            assert tournament.tournament_id == accepted and actor.user_id == users[name]
        else:
            with pytest.raises(HTTPException) as exc:
                get_editable_roster_context(db, accepted, teams['Alpha'], db.get(User, users[name]))
            assert exc.value.status_code == 403


@pytest.mark.parametrize('scope', ['TEAM', 'ORGANIZATION', 'GLOBAL'])
def test_roster_scope_assignments_and_revocation(access, session_factory, accepted, scope):
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        scope_id = teams['Alpha'] if scope == 'TEAM' else db.get(Team, teams['Alpha']).organization_id
        db.add(RoleAssignment(user_id=users['referee'], role_id=roles['TEAM_MANAGER'],
                              scope_type=scope, scope_id=None if scope == 'GLOBAL' else scope_id))
    response = client.get(caps(accepted, teams['Alpha']), headers=headers('referee')).json()
    assert response['can_edit_roster'] == (scope != 'GLOBAL')
    assert not client.get(caps(accepted, teams['Beta']), headers=headers('referee')).json()['can_edit_roster']
    with session_factory.begin() as db:
        db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == users['referee']))
    assert not client.get(caps(accepted, teams['Alpha']), headers=headers('referee')).json()['can_edit_roster']


@pytest.mark.parametrize('state,locked', [('UPCOMING', True), ('ONGOING', False),
                                         ('COMPLETED', False), ('CANCELLED', False)])
def test_lifecycle_closes_roster_context_and_hints(access, session_factory, accepted, state, locked):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        tournament = db.get(Tournament, accepted)
        tournament.status = state
        if locked:
            tournament.roster_locked_at = datetime.now(timezone.utc)
            tournament.roster_locked_by = users['organizer']
    data = client.get(caps(accepted, teams['Alpha']), headers=headers('manager')).json()
    assert not data['can_edit_roster']
    hints = client.get(f'/api/v1/tournaments/{accepted}/capabilities', headers=headers('organizer')).json()
    assert not hints['can_lock_roster'] and not hints['can_approve_registrations']
    assert hints['can_review_registrations'] == (state == 'UPCOMING')
    with session_factory() as db:
        with pytest.raises(HTTPException) as exc:
            get_editable_roster_context(db, accepted, teams['Alpha'], db.get(User, users['manager']))
        assert exc.value.status_code == 409


def test_pending_team_cannot_edit_and_context_does_not_commit(access, session_factory, accepted):
    _, _, users, teams, _ = access
    with session_factory.begin() as db:
        db.scalar(select(TournamentRegistration)).status = 'PENDING'
        db.scalar(select(TournamentRegistration)).reviewed_at = None
    with session_factory() as db:
        with pytest.raises(HTTPException) as exc:
            get_editable_roster_context(db, accepted, teams['Alpha'], db.get(User, users['manager']))
        assert exc.value.status_code == 409
    with session_factory.begin() as db:
        registration = db.scalar(select(TournamentRegistration))
        registration.status = 'APPROVED'
        registration.reviewed_at = datetime.now(timezone.utc)
    with session_factory() as db:
        tournament, _ = get_editable_roster_context(db, accepted, teams['Alpha'], db.get(User, users['manager']))
        members = lock_roster_memberships(db, [teams['Alpha'], teams['Alpha']])
        assert len(members) == 2
        assert lock_roster_rows(db, accepted) == []
        tournament.description = 'must roll back'
        db.add(TournamentRoster(tournament_id=accepted, team_id=teams['Alpha'], user_id=users['viewer']))
        record_audit(db, users['manager'], 'ROSTER_ROLLBACK_PROBE', 'tournament_roster', {'tournament_id': accepted})
        db.flush()
        db.rollback()
    with session_factory() as db:
        assert db.get(Tournament, accepted).description != 'must roll back'
        assert db.scalar(select(TournamentRoster.roster_id)) is None
        assert db.scalar(select(AuditLog.log_id).where(AuditLog.action == 'ROSTER_ROLLBACK_PROBE')) is None


def test_lock_status_public_but_private_actor_and_draft_never_leak(access, session_factory, accepted):
    client, headers, users, teams, _ = access
    path = f'/api/v1/tournaments/{accepted}/roster-lock'
    response = client.get(path)
    assert response.json() == {'tournament_id': accepted, 'locked': False, 'locked_at': None}
    assert response.headers['cache-control'] == 'private, no-store'
    assert client.get(caps(accepted, teams['Alpha'])).status_code == 401
    with session_factory.begin() as db:
        db.get(Tournament, accepted).roster_locked_at = datetime.now(timezone.utc)
        db.get(Tournament, accepted).roster_locked_by = users['organizer']
    data = client.get(path).json()
    assert data['locked'] and data['locked_at'] and set(data) == {'tournament_id', 'locked', 'locked_at'}
    assert client.get(caps(accepted, teams['Alpha']), headers=headers('viewer')).json()['can_view_roster']


@pytest.mark.parametrize('suffix,expected', [('/0/roster-lock', 422), ('/2147483648/roster-lock', 422),
                                            ('/999999/roster-lock', 404)])
def test_lock_state_ids_and_no_cache(access, suffix, expected):
    client, *_ = access
    response = client.get('/api/v1/tournaments' + suffix)
    assert response.status_code == expected
    assert response.headers['cache-control'] == 'private, no-store'


@pytest.mark.parametrize('action', ['reject', 'cancel'])
def test_locked_tournament_can_resolve_pending_without_changing_approved_teams(access, session_factory, accepted, action):
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        tournament = db.get(Tournament, accepted)
        tournament.roster_locked_at = datetime.now(timezone.utc)
        pending = TournamentRegistration(tournament_id=accepted, team_id=teams['Beta'])
        db.add(pending)
        db.flush()
        rid = pending.registration_id
        if action == 'cancel':
            db.add(RoleAssignment(user_id=users['referee'], role_id=roles['TEAM_MANAGER'],
                                  scope_type='TEAM', scope_id=teams['Beta']))
    path = f'/api/v1/tournaments/{accepted}/registrations'
    assert client.post(f'{path}/{rid}/decision', headers=headers('organizer'),
                       json={'status': 'APPROVED'}).status_code == 409
    assert client.post(path, headers=headers('admin'), json={'team_id': teams['Beta']}).status_code == 409
    # Locking does not grant new team/tournament rights to an unrelated viewer.
    suffix = 'decision' if action == 'reject' else 'cancel'
    payload = {'status': 'REJECTED', 'rejection_reason': 'Roster already locked'} if action == 'reject' else {}
    assert client.post(f'{path}/{rid}/{suffix}', headers=headers('viewer'), json=payload).status_code == 403
    assert client.post(f'{path}/{rid}/{suffix}', headers=headers('manager'), json=payload).status_code == 403
    auth = headers('organizer' if action == 'reject' else 'referee')
    result = client.post(f'{path}/{rid}/{suffix}', headers=auth, json=payload)
    assert result.status_code == 200, result.text
    expected = 'REJECTED' if action == 'reject' else 'CANCELLED'
    assert result.json()['status'] == expected
    assert client.post(f'{path}/{rid}/{suffix}', headers=auth, json=payload).status_code == 409
    with session_factory() as db:
        assert db.get(TournamentRegistration, rid).status == expected
        assert list(db.scalars(select(TournamentRegistration.team_id).where(
            TournamentRegistration.tournament_id == accepted, TournamentRegistration.status == 'APPROVED',
        ))) == [teams['Alpha']]
        logs = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'tournament_registration')))
        assert len(logs) == 1
        assert logs[0].action == 'TOURNAMENT_REGISTRATION_' + expected
        assert logs[0].user_id == users['organizer' if action == 'reject' else 'referee']
        assert logs[0].details['before']['status'] == 'PENDING'
        assert logs[0].details['after']['status'] == expected


@pytest.mark.parametrize('state', ['ONGOING', 'COMPLETED', 'CANCELLED'])
def test_resolving_pending_remains_closed_after_upcoming(access, session_factory, accepted, state):
    client, headers, _, teams, _ = access
    with session_factory.begin() as db:
        tournament = db.get(Tournament, accepted)
        tournament.status = state
        tournament.roster_locked_at = datetime.now(timezone.utc)
        pending = TournamentRegistration(tournament_id=accepted, team_id=teams['Beta'])
        db.add(pending)
        db.flush()
        rid = pending.registration_id
    path = f'/api/v1/tournaments/{accepted}/registrations/{rid}'
    assert client.post(path + '/decision', headers=headers('organizer'), json={'status': 'REJECTED'}).status_code == 409
    assert client.post(path + '/cancel', headers=headers('admin')).status_code == 409
    with session_factory() as db:
        assert db.get(TournamentRegistration, rid).status == 'PENDING'
        assert db.scalar(select(AuditLog.log_id).where(AuditLog.resource == 'tournament_registration')) is None


@pytest.mark.parametrize('field,value', [('role_in_team', 'MANAGER'), ('display_name', '  ')])
def test_roster_database_rejects_invalid_snapshot(access, session_factory, accepted, field, value):
    _, _, users, teams, _ = access
    with session_factory() as db:
        values = dict(tournament_id=accepted, team_id=teams['Alpha'], user_id=users['viewer'], role_in_team='PLAYER')
        values[field] = value
        db.add(TournamentRoster(**values))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_snapshot_unique_and_restrict_preserve_user_team_history(access, session_factory, accepted):
    _, _, users, teams, _ = access
    with session_factory.begin() as db:
        db.add(TournamentRoster(tournament_id=accepted, team_id=teams['Alpha'], user_id=users['viewer'],
                                display_name='Snapshot name', role_in_team='PLAYER'))
    with session_factory() as db:
        db.add(TournamentRoster(tournament_id=accepted, team_id=teams['Beta'], user_id=users['viewer']))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
    for model, field, value in [(User, User.user_id, users['viewer']), (Team, Team.team_id, teams['Alpha'])]:
        with session_factory() as db:
            with pytest.raises(IntegrityError):
                db.execute(delete(model).where(field == value))
            db.rollback()
    with session_factory.begin() as db:
        member = db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['viewer']))
        member.status = 'ENDED'
        db.get(User, users['viewer']).real_name = 'Changed name'
    with session_factory() as db:
        snapshot = db.scalar(select(TournamentRoster))
        assert snapshot.display_name == 'Snapshot name' and snapshot.role_in_team == 'PLAYER'


@pytest.mark.parametrize('members', [
    [{'user_id': True, 'role_in_team': 'PLAYER'}], [{'user_id': '1', 'role_in_team': 'PLAYER'}],
    [{'user_id': 0, 'role_in_team': 'PLAYER'}], [{'user_id': 2147483648, 'role_in_team': 'PLAYER'}],
    [{'user_id': 1, 'role_in_team': 'COACH'}], [{'user_id': 1, 'role_in_team': 'PLAYER', 'email': 'leak'}],
    [{'user_id': 1, 'role_in_team': 'PLAYER'}] * 2,
    [{'user_id': i + 1, 'role_in_team': 'PLAYER'} for i in range(101)],
])
def test_replace_contract_rejects_ambiguous_or_unbounded_input(members):
    with pytest.raises(ValidationError):
        RosterReplace(members=members)


def test_empty_draft_and_valid_replace_contract():
    assert RosterReplace(members=[]).members == []
    assert RosterReplace(members=[{'user_id': 1, 'role_in_team': 'SUBSTITUTE'}]).members[0].user_id == 1
