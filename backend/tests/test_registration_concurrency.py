"""Real PostgreSQL connections: fixture savepoints cannot simulate row-lock races."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from config.settings import get_settings
from core.registrations import lock_registration, lock_registration_tournament
from modules.identity.models import AuditLog
from modules.tournaments.models import TournamentRegistration
from seed import seed_reference_data
from test_catalog_api import make_client
from test_permissions import access
from test_registration_decisions import path, pending, registration_logs

pytestmark = pytest.mark.postgres


@pytest.fixture
def session_factory(request):
    if not request.config.getoption('--postgres'):
        pytest.skip('requires real PostgreSQL connections')
    url = os.environ.get('TEST_DATABASE_URL') or get_settings().DATABASE_URL
    schema = 'w44_race_' + uuid4().hex
    admin = create_engine(url, connect_args={'connect_timeout': 5})
    engine = None
    try:
        with admin.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={
            'connect_timeout': 5, 'options': f'-csearch_path={schema} -clock_timeout=5000',
        })
        with engine.begin() as connection:
            config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
            config.attributes['connection'] = connection
            config.attributes['version_table_schema'] = schema
            command.upgrade(config, 'head')
        factory = sessionmaker(bind=engine, autoflush=False)
        with factory.begin() as db:
            seed_reference_data(db)
        yield factory
    finally:
        if engine is not None:
            engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def test_two_reviewers_cannot_decide_same_registration(access, session_factory, pending):
    _, headers, *_ = access
    def decide(status):
        with make_client(session_factory, logged_in=False) as client:
            return client.post(path(pending), json={'status': status}, headers=headers('organizer')).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(decide, ['APPROVED', 'REJECTED']))
    assert sorted(statuses) == [200, 409]
    assert len(registration_logs(session_factory)) == 1


@pytest.mark.parametrize('operation', ['close', 'cancel'])
def test_waiting_decision_sees_committed_close_or_cancel(access, session_factory, pending, operation):
    _, headers, *_ = access
    tid, rid = pending
    attempted = Event()
    engine = session_factory.kw['bind']
    def notice_lock(connection, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE' in statement and 'FROM tournaments' in statement:
            attempted.set()
    def decide():
        with make_client(session_factory, logged_in=False) as client:
            return client.post(path(pending), json={'status': 'APPROVED'}, headers=headers('organizer')).status_code
    # Hold the shared parent lock before allowing the competing HTTP request.
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with session_factory.begin() as db:
                tournament = lock_registration_tournament(db, tid)
                if operation == 'close':
                    tournament.status = 'ONGOING'
                else:
                    registration = lock_registration(db, tid, rid)
                    registration.status = 'CANCELLED'
                    registration.cancelled_at = datetime.now(timezone.utc)
                event.listen(engine, 'before_cursor_execute', notice_lock)
                future = pool.submit(decide)
                assert attempted.wait(5), 'HTTP request never attempted the parent lock'
                assert not future.done(), 'request did not wait for the parent lock'
            assert future.result(timeout=10) == 409
        finally:
            event.remove(engine, 'before_cursor_execute', notice_lock)
    with session_factory() as db:
        row = db.get(TournamentRegistration, rid)
        assert row.status == ('PENDING' if operation == 'close' else 'CANCELLED')
    assert registration_logs(session_factory) == []


def test_status_endpoint_and_decision_share_parent_lock(access, session_factory, pending):
    _, headers, *_ = access
    tid, rid = pending
    def request(operation):
        with make_client(session_factory, logged_in=False) as client:
            if operation == 'decision':
                return client.post(path(pending), json={'status': 'APPROVED'}, headers=headers('organizer')).status_code
            return client.post(f'/api/v1/tournaments/{tid}/status', json={'status': 'ONGOING'},
                               headers=headers('organizer')).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        decision, close = list(pool.map(request, ['decision', 'close']))
    assert close == 200 and decision in (200, 409)
    with session_factory() as db:
        row = db.get(TournamentRegistration, rid)
        assert row.status == ('APPROVED' if decision == 200 else 'PENDING')
        logs = db.scalars(select(AuditLog).where(AuditLog.action.in_(
            ['TOURNAMENT_STATUS_CHANGED', 'TOURNAMENT_REGISTRATION_APPROVED']
        )).order_by(AuditLog.log_id)).all()
        assert [log.action for log in logs] == (
            ['TOURNAMENT_REGISTRATION_APPROVED', 'TOURNAMENT_STATUS_CHANGED'] if decision == 200
            else ['TOURNAMENT_STATUS_CHANGED']
        )
