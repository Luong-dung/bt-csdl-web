"""Foundation lock protocol on independent PostgreSQL transactions, not savepoints."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select

from core.rosters import get_editable_roster_context, lock_roster_memberships, lock_roster_teams
from core.tournaments import lock_tournament
from modules.identity.models import User
from modules.teams.models import TeamMembership
from modules.tournaments.models import TournamentRoster
from test_permissions import access
from test_registration_concurrency import session_factory
from test_roster_foundation import accepted

pytestmark = pytest.mark.postgres


def team_lock_probe(engine, started):
    def before_execute(connection, cursor, statement, parameters, context, executemany):
        if 'FROM teams' in statement and 'FOR UPDATE' in statement:
            started.set()
    event.listen(engine, 'before_cursor_execute', before_execute)
    return before_execute


def test_snapshot_validation_serializes_membership_writer(session_factory, access, accepted):
    client, headers, users, teams, _ = access
    with session_factory() as holder:
        lock_tournament(holder, accepted)
        memberships = lock_roster_memberships(holder, [teams['Alpha']])
        mid = next(m.membership_id for m in memberships if m.user_id == users['viewer'])
        engine = holder.get_bind()
        started, finished = Event(), Event()
        listener = team_lock_probe(engine, started)

        def leave():
            try:
                return client.post(f"/api/v1/teams/{teams['Alpha']}/members/{mid}/end",
                                   headers=headers('viewer')).status_code
            finally:
                finished.set()

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(leave)
                try:
                    assert started.wait(3), 'membership writer never attempted the team lock'
                    assert not finished.wait(0.2), 'membership changed during snapshot validation'
                    holder.add(TournamentRoster(tournament_id=accepted, team_id=teams['Alpha'],
                                                user_id=users['viewer'], display_name='Frozen viewer'))
                    holder.commit()
                finally:
                    holder.rollback()  # release locks even if an assertion failed
                assert future.result(timeout=5) == 200
        finally:
            event.remove(engine, 'before_cursor_execute', listener)
    with session_factory() as db:
        assert db.get(TeamMembership, mid).status == 'ENDED'
        snapshot = db.scalar(select(TournamentRoster))
        assert snapshot.display_name == 'Frozen viewer' and snapshot.role_in_team == 'PLAYER'


def test_roster_context_rechecks_team_rights_after_waiting(session_factory, access, accepted):
    _, _, users, teams, _ = access
    with session_factory() as holder:
        lock_roster_teams(holder, [teams['Alpha']])
        engine = holder.get_bind()
        started = Event()
        listener = team_lock_probe(engine, started)

        def edit_context():
            with session_factory() as db:
                try:
                    get_editable_roster_context(db, accepted, teams['Alpha'], db.get(User, users['manager']))
                    return 200
                except HTTPException as exc:
                    return exc.status_code

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(edit_context)
                try:
                    assert started.wait(3)
                    member = holder.scalar(select(TeamMembership).where(TeamMembership.user_id == users['manager']))
                    member.status = 'ENDED'
                    holder.commit()
                finally:
                    holder.rollback()
                assert future.result(timeout=5) == 403
        finally:
            event.remove(engine, 'before_cursor_execute', listener)
