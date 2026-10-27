from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from modules.identity.models import AuditLog, RoleAssignment, User
from modules.teams.models import Team, TeamMembership
from modules.tournaments.models import Tournament, TournamentRegistration, TournamentRoster
from test_catalog_api import session_factory
from test_permissions import access
from test_roster_api import body, case, roster

pytestmark = pytest.mark.postgres


def lock_path(tid):
    return f'/api/v1/tournaments/{tid}/roster-lock'


def lock_logs(factory):
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.action == 'TOURNAMENT_ROSTER_LOCKED')))


def locked_at(factory, tid):
    with factory() as db:
        return db.get(Tournament, tid).roster_locked_at


def draft(client, headers, users, teams, tid, alpha=(('viewer', 'PLAYER'), ('p2', 'SUBSTITUTE')),
          beta=(('p3', 'PLAYER'),)):
    for team, members in (('Alpha', alpha), ('Beta', beta)):
        response = client.put(roster(tid, teams[team]), headers=headers('admin'),
                              json=body(*((users[name], role) for name, role in members)))
        assert response.status_code == 200, response.json()


def caps(client, headers, tid, name='organizer'):
    return client.get(f'/api/v1/tournaments/{tid}/capabilities', headers=headers(name)).json()


def test_lock_snapshots_all_teams_once(access, session_factory, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    with session_factory.begin() as db:
        db.get(User, users['viewer']).username = 'viewer_at_lock'
    assert caps(client, headers, case)['allowed_status_transitions'] == ['CANCELLED']
    response = client.post(lock_path(case), headers=headers('organizer'))
    assert response.status_code == 200
    data = response.json()
    assert data['locked'] is True and data['tournament_id'] == case and data['locked_at']
    assert response.headers['cache-control'] == 'private, no-store'
    assert client.get(lock_path(case)).json() == data
    [log] = lock_logs(session_factory)
    assert log.user_id == users['organizer'] and log.resource == 'tournament_roster'
    assert log.details['team_count'] == 2 and log.details['member_count'] == 3
    # Display names are retaken at lock time from the current username.
    public = client.get(roster(case, teams['Alpha'])).json()
    assert public['locked'] and {m['display_name'] for m in public['members']} == {'viewer_at_lock', 'p2'}
    with session_factory() as db:
        assert db.get(Tournament, case).roster_locked_by == users['organizer']
    hints = caps(client, headers, case)
    assert hints['roster_locked'] and not hints['can_lock_roster'] and not hints['can_approve_registrations']
    assert hints['allowed_status_transitions'] == ['CANCELLED', 'ONGOING']
    assert not client.get(f'{roster(case, teams["Alpha"])}/capabilities',
                          headers=headers('manager')).json()['can_edit_roster']


def test_lock_is_idempotent_even_after_lifecycle_changes(access, session_factory, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    first = client.post(lock_path(case), headers=headers('organizer')).json()
    assert client.post(lock_path(case), headers=headers('admin')).json() == first
    for state in ('ONGOING', 'CANCELLED'):
        assert client.post(f'/api/v1/tournaments/{case}/status', headers=headers('organizer'),
                           json={'status': state}).status_code == 200
        assert client.post(lock_path(case), headers=headers('organizer')).json() == first
    assert len(lock_logs(session_factory)) == 1
    # Repeating still requires tournament rights.
    assert client.post(lock_path(case), headers=headers('manager')).status_code == 403


@pytest.mark.parametrize('name,status', [(None, 401), ('viewer', 403), ('manager', 403),
                                         ('scoped', 200), ('admin', 200)])
def test_lock_requires_tournament_manager(access, session_factory, case, name, status):
    client, headers, users, teams, roles = access
    draft(client, headers, users, teams, case)
    if name == 'scoped':
        with session_factory.begin() as db:
            db.add(RoleAssignment(user_id=users['referee'], role_id=roles['ORGANIZER'],
                                  scope_type='TOURNAMENT', scope_id=case))
        name = 'referee'
    response = client.post(lock_path(case), headers=headers(name) if name else {})
    assert response.status_code == status
    assert (locked_at(session_factory, case) is not None) == (status == 200)
    assert len(lock_logs(session_factory)) == (status == 200)


@pytest.mark.parametrize('state', ['ONGOING', 'COMPLETED', 'CANCELLED'])
def test_unlocked_tournament_outside_upcoming_cannot_lock(access, session_factory, case, state):
    """Legacy tournaments that started before W44-2-04 are not backfilled."""
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    with session_factory.begin() as db:
        db.get(Tournament, case).status = state
    assert client.post(lock_path(case), headers=headers('organizer')).status_code == 409
    assert locked_at(session_factory, case) is None and lock_logs(session_factory) == []


def break_no_approved(db, users, teams, tid):
    for registration in db.scalars(select(TournamentRegistration)):
        registration.status, registration.reviewed_at = 'PENDING', None
    db.execute(TournamentRoster.__table__.delete())


def break_missing_player(db, users, teams, tid):
    row = db.scalar(select(TournamentRoster).where(TournamentRoster.user_id == users['p3']))
    db.delete(row)
    db.flush()  # sessions here do not autoflush before the caller's next query


def break_only_substitute(db, users, teams, tid):
    db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['p3'])).role_in_team = 'SUBSTITUTE'
    db.scalar(select(TournamentRoster).where(TournamentRoster.user_id == users['p3'])).role_in_team = 'SUBSTITUTE'


def break_left_team(db, users, teams, tid):
    db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['p2'])).left_date = date.today()


def break_inactive(db, users, teams, tid):
    db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['p2'])).status = 'INACTIVE'


def break_role_changed(db, users, teams, tid):
    db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['p2'])).role_in_team = 'COACH'


def break_rejected_team(db, users, teams, tid):
    registration = db.scalar(select(TournamentRegistration).where(TournamentRegistration.team_id == teams['Beta']))
    registration.status = 'REJECTED'


def break_wrong_game(db, users, teams, tid):
    db.get(Team, teams['Beta']).game_id = 2


@pytest.mark.parametrize('breaker', [break_no_approved, break_missing_player, break_only_substitute,
                                     break_left_team, break_inactive, break_role_changed,
                                     break_rejected_team, break_wrong_game])
def test_invalid_snapshot_blocks_lock_without_side_effects(access, session_factory, case, breaker):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    with session_factory.begin() as db:
        breaker(db, users, teams, case)
        before = sorted((r.user_id, r.display_name) for r in db.scalars(select(TournamentRoster)))
        db.get(User, users['viewer']).username = 'must_not_snapshot'
    response = client.post(lock_path(case), headers=headers('organizer'))
    assert response.status_code == 409, response.json()
    assert locked_at(session_factory, case) is None and lock_logs(session_factory) == []
    with session_factory() as db:
        assert sorted((r.user_id, r.display_name) for r in db.scalars(select(TournamentRoster))) == before


def test_empty_approved_roster_cannot_lock_but_other_teams_can_be_empty_drafts(access, session_factory, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case, beta=())
    assert client.post(lock_path(case), headers=headers('organizer')).status_code == 409
    draft(client, headers, users, teams, case)
    assert client.post(lock_path(case), headers=headers('organizer')).status_code == 200


def test_audit_failure_rolls_back_lock_and_snapshot(access, session_factory, case, monkeypatch):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    with session_factory.begin() as db:
        db.get(User, users['viewer']).username = 'renamed'

    def broken_audit(*_):
        raise IntegrityError('audit', {}, Exception('forced'))
    monkeypatch.setattr('routes.rosters.record_audit', broken_audit)
    assert client.post(lock_path(case), headers=headers('organizer')).status_code == 409
    assert locked_at(session_factory, case) is None
    with session_factory() as db:
        assert db.scalar(select(TournamentRoster.display_name).where(
            TournamentRoster.user_id == users['viewer'])) == 'viewer'


def test_locked_snapshot_survives_membership_changes_and_blocks_writes(access, session_factory, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    assert client.post(lock_path(case), headers=headers('organizer')).status_code == 200
    snapshot = client.get(roster(case, teams['Alpha'])).json()
    membership = client.get(f'/api/v1/teams/{teams["Alpha"]}/members', headers=headers('manager')).json()
    viewer_mid = next(m['membership_id'] for m in membership if m['user_id'] == users['viewer'])
    assert client.post(f'/api/v1/teams/{teams["Alpha"]}/members/{viewer_mid}/end',
                       headers=headers('manager')).status_code == 200
    assert client.get(roster(case, teams['Alpha'])).json() == snapshot
    assert client.put(roster(case, teams['Alpha']), headers=headers('manager'),
                      json=body((users['p1'], 'PLAYER'))).status_code == 409


def start(client, headers, tid, name='organizer'):
    return client.post(f'/api/v1/tournaments/{tid}/status', headers=headers(name), json={'status': 'ONGOING'})


def test_start_requires_locked_roster(access, session_factory, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    response = start(client, headers, case)
    assert response.status_code == 409 and 'khóa đội hình' in response.json()['detail']
    assert client.get(f'/api/v1/tournaments/{case}').json()['status'] == 'UPCOMING'
    assert client.post(lock_path(case), headers=headers('organizer')).status_code == 200
    assert start(client, headers, case).status_code == 200
    assert caps(client, headers, case)['allowed_status_transitions'] == ['CANCELLED', 'COMPLETED']


def test_start_rechecks_players_of_locked_snapshot(access, session_factory, case):
    """Defensive: a snapshot edited outside the API must not start with a team lacking a PLAYER."""
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    assert client.post(lock_path(case), headers=headers('organizer')).status_code == 200
    with session_factory.begin() as db:
        break_missing_player(db, users, teams, case)
    response = start(client, headers, case)
    assert response.status_code == 409 and str(teams['Beta']) in response.json()['detail']
    assert client.get(f'/api/v1/tournaments/{case}').json()['status'] == 'UPCOMING'


def test_legacy_ongoing_tournament_keeps_transitions(access, session_factory, case):
    client, headers, *_ = access
    with session_factory.begin() as db:
        db.get(Tournament, case).status = 'ONGOING'
    assert caps(client, headers, case)['allowed_status_transitions'] == ['CANCELLED', 'COMPLETED']
    assert client.post(f'/api/v1/tournaments/{case}/status', headers=headers('organizer'),
                       json={'status': 'COMPLETED'}).status_code == 200


def test_lock_blocks_new_approval_but_not_pending_resolution(access, session_factory, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    with session_factory.begin() as db:
        gamma = Team(name='Gamma', tag='G', game_id=1)
        db.add(gamma)
        db.flush()
        pending = TournamentRegistration(tournament_id=case, team_id=gamma.team_id, status='PENDING')
        db.add(pending)
        db.flush()
        rid = pending.registration_id
    assert client.post(lock_path(case), headers=headers('organizer')).status_code == 200
    decide = f'/api/v1/tournaments/{case}/registrations/{rid}/decision'
    assert client.post(decide, headers=headers('organizer'), json={'status': 'APPROVED'}).status_code == 409
    assert client.post(decide, headers=headers('organizer'), json={'status': 'REJECTED'}).status_code == 200
    # The rejected team never had a roster, so starting still succeeds.
    assert start(client, headers, case).status_code == 200
