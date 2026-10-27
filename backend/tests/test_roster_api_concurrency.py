"""PUT roster rechecks membership and rights after waiting on independent PostgreSQL locks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event

import pytest
from sqlalchemy import event, select

from core.rosters import lock_roster_memberships
from core.tournaments import lock_tournament
from modules.teams.models import TeamMembership
from modules.tournaments.models import TournamentRoster
from test_permissions import access
from test_registration_concurrency import session_factory
from test_roster_api import body, case, logs, roster

pytestmark = pytest.mark.postgres


def tournament_lock_probe(engine, started):
    def before_execute(connection, cursor, statement, parameters, context, executemany):
        if 'FROM tournaments' in statement and 'FOR UPDATE' in statement:
            started.set()
    event.listen(engine, 'before_cursor_execute', before_execute)
    return before_execute


@pytest.mark.parametrize('ended,status', [('p1', 422), ('manager', 403)])
def test_put_rechecks_after_membership_change_while_waiting(session_factory, access, case, ended, status):
    client, headers, users, teams, _ = access
    with session_factory() as holder:
        lock_tournament(holder, case)
        lock_roster_memberships(holder, [teams['Alpha']])
        engine = holder.get_bind()
        started = Event()
        listener = tournament_lock_probe(engine, started)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: client.put(roster(case, teams['Alpha']), headers=headers('manager'),
                                                        json=body((users['p1'], 'PLAYER'))).status_code)
                try:
                    assert started.wait(3), 'roster writer never queued on the tournament lock'
                    assert not future.done(), 'roster writer did not wait for the tournament lock'
                    membership = holder.scalar(select(TeamMembership).where(
                        TeamMembership.user_id == users[ended]))
                    membership.left_date = date.today()
                    holder.commit()
                finally:
                    holder.rollback()
                assert future.result(timeout=5) == status
        finally:
            event.remove(engine, 'before_cursor_execute', listener)
    with session_factory() as db:
        assert db.scalar(select(TournamentRoster.roster_id)) is None
    assert logs(session_factory) == []


def test_two_teams_cannot_claim_the_same_player(session_factory, access, case):
    """Serialized by the tournament lock: the second writer sees the first roster and gets 409."""
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        # p1 transfers to Beta after Alpha drafted them; Alpha's draft still references p1.
        db.add(TournamentRoster(tournament_id=case, team_id=teams['Alpha'], user_id=users['p1'],
                                role_in_team='PLAYER', display_name='p1'))
        db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['p1'])).status = 'INACTIVE'
        db.add(TeamMembership(team_id=teams['Beta'], user_id=users['p1'], role_in_team='PLAYER'))
    responses = [client.put(roster(case, teams['Beta']), headers=headers('admin'),
                            json=body((users['p1'], 'PLAYER'))).status_code,
                 client.put(roster(case, teams['Alpha']), headers=headers('admin'),
                            json={'members': []}).status_code,
                 client.put(roster(case, teams['Beta']), headers=headers('admin'),
                            json=body((users['p1'], 'PLAYER'))).status_code]
    assert responses == [409, 200, 200]
    with session_factory() as db:
        assert [(r.team_id, r.user_id) for r in db.scalars(select(TournamentRoster))] == [
            (teams['Beta'], users['p1'])]
