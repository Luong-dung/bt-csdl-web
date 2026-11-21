"""W47-04 (W05-01): DELETE /tournaments/{id} only for tournaments without competition data."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

import routes.tournaments
from modules.identity.models import AuditLog
from modules.teams.models import TeamMembership
from modules.tournaments.models import Stage, Tournament, TournamentStanding
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


def path(tid):
    return f'/api/v1/tournaments/{tid}'


def deleted_logs(session_factory):
    with session_factory() as db:
        return db.scalars(select(AuditLog).where(AuditLog.action == 'TOURNAMENT_DELETED')).all()


def exists(session_factory, tid):
    with session_factory() as db:
        return db.get(Tournament, tid) is not None


def test_manager_deletes_empty_tournament_with_audit(access, session_factory):
    client, headers, users, *_ = access
    tid = organizer_tournament(client, headers)
    assert client.get(path(tid) + '/capabilities', headers=headers('organizer')).json()['can_delete'] is True
    response = client.delete(path(tid), headers=headers('organizer'))
    assert response.status_code == 204 and response.content == b''
    assert not exists(session_factory, tid)
    assert client.get(path(tid)).status_code == 404
    [log] = deleted_logs(session_factory)
    assert (log.user_id, log.resource, log.resource_id, log.tournament_id) == (
        users['organizer'], 'tournament', tid, tid)
    assert log.details['before']['name'] == 'Organizer cup' and log.details['after'] is None
    # The global audit log keeps the history of the deleted tournament.
    rows = client.get('/api/v1/admin/audit-logs', params={'tournament_id': tid}, headers=headers('admin')).json()
    assert [row['action'] for row in rows] == ['TOURNAMENT_DELETED', 'TOURNAMENT_CREATED']
    assert client.delete(path(tid), headers=headers('organizer')).status_code == 404


def test_permission_matrix(access, session_factory):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    assert client.delete(path(tid)).status_code == 401
    for name in ('viewer', 'manager', 'referee'):
        assert client.delete(path(tid), headers=headers(name)).status_code == 403
    assert client.delete(path(999999), headers=headers('admin')).status_code == 404
    assert client.delete(path(0), headers=headers('admin')).status_code == 422
    assert exists(session_factory, tid) and deleted_logs(session_factory) == []
    assert client.delete(path(tid), headers=headers('admin')).status_code == 204


@pytest.mark.parametrize('status', ['ONGOING', 'COMPLETED', 'CANCELLED'])
def test_only_upcoming_can_be_deleted(access, session_factory, status):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.get(Tournament, tid).status = status
    response = client.delete(path(tid), headers=headers('admin'))
    assert response.status_code == 409 and 'CANCELLED' in response.json()['detail']
    assert exists(session_factory, tid)
    assert client.get(path(tid) + '/capabilities', headers=headers('admin')).json()['can_delete'] is False


def test_locked_roster_blocks_delete(access, session_factory):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.get(Tournament, tid).roster_locked_at = datetime.now(timezone.utc)
    assert client.delete(path(tid), headers=headers('admin')).status_code == 409


@pytest.mark.parametrize('cancel', [False, True])
def test_any_registration_blocks_delete_and_is_kept(access, session_factory, cancel):
    client, headers, users, teams, _ = access
    tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=teams['Alpha'], user_id=users['manager'], role_in_team='MANAGER'))
    regs = path(tid) + '/registrations'
    rid = client.post(regs, json={'team_id': teams['Alpha']}, headers=headers('manager')).json()['registration_id']
    if cancel:  # even a cancelled registration is history
        assert client.post(f'{regs}/{rid}/cancel', headers=headers('manager')).status_code == 200
    response = client.delete(path(tid), headers=headers('organizer'))
    assert response.status_code == 409 and 'đơn đăng ký' in response.json()['detail']
    assert [r['registration_id'] for r in client.get(regs, headers=headers('organizer')).json()] == [rid]
    assert deleted_logs(session_factory) == []


def test_stage_blocks_delete(access, session_factory):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    assert client.post(path(tid) + '/stages', json={'name': 'Groups', 'sequence_order': 1},
                       headers=headers('organizer')).status_code == 201
    response = client.delete(path(tid), headers=headers('organizer'))
    assert response.status_code == 409 and 'giai đoạn' in response.json()['detail']
    with session_factory() as db:
        assert len(db.scalars(select(Stage).where(Stage.tournament_id == tid)).all()) == 1


def test_standing_blocks_delete(access, session_factory):
    client, headers, _, teams, _ = access
    tid = organizer_tournament(client, headers)
    # Legacy standings row inserted directly (matches always need a stage, covered above).
    with session_factory.begin() as db:
        db.add(TournamentStanding(tournament_id=tid, team_id=teams['Alpha'], final_rank=1))
    assert client.delete(path(tid), headers=headers('admin')).status_code == 409
    assert exists(session_factory, tid)


@pytest.mark.parametrize('revoke', [False, True])
def test_referee_assignment_history_blocks_delete(access, session_factory, revoke):
    client, headers, users, *_ = access
    tid = organizer_tournament(client, headers)
    granted = client.post(path(tid) + '/referees', json={'user_id': users['referee']}, headers=headers('organizer'))
    assert granted.status_code == 201
    if revoke:
        aid = granted.json()['assignment_id']
        assert client.delete(f'{path(tid)}/referees/{aid}', headers=headers('organizer')).status_code == 200
    response = client.delete(path(tid), headers=headers('organizer'))
    assert response.status_code == 409 and 'phân quyền' in response.json()['detail']


def test_audit_failure_rolls_back_delete(access, session_factory, monkeypatch):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    def broken(*args, **kwargs):
        raise RuntimeError('audit down')
    monkeypatch.setattr(routes.tournaments, 'record_audit', broken)
    with pytest.raises(RuntimeError):
        client.delete(path(tid), headers=headers('organizer'))
    assert exists(session_factory, tid)
