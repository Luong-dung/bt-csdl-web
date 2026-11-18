"""Single audit writer (W47-02). Callers own the transaction; an audit failure rolls back the mutation.

Every row keeps the original ``action``/``resource``/``details`` shape used since W43. W47-02 adds two
indexed columns derived from ``details`` so logs can be filtered without JSON queries:
``tournament_id`` (scope for tournament managers) and ``resource_id`` (the row the action touched).
"""

from sqlalchemy.orm import Session

from modules.identity.models import AuditLog

# Which details key identifies the touched row for each resource.
RESOURCE_ID_KEYS = {
    'tournament': 'tournament_id',
    'tournament_registration': 'registration_id',
    'tournament_stage': 'stage_id',
    'tournament_roster': 'team_id',
    'match': 'match_id',
    'bracket': 'bracket_id',
    'team_membership': 'membership_id',
    'role_assignment': 'assignment_id',
    'publisher': 'publisher_id',
    'game': 'game_id',
    'area': 'area_id',
}


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def derive_ids(resource: str, details: dict) -> tuple[int | None, int | None]:
    """(tournament_id, resource_id) from details; also used to backfill legacy rows in the migration."""
    details = details if isinstance(details, dict) else {}
    key = RESOURCE_ID_KEYS.get(resource)
    resource_id = None
    if key:
        resource_id = _int(details.get(key))
        for side in ('after', 'before'):
            snapshot = details.get(side)
            if resource_id is None and isinstance(snapshot, dict):
                resource_id = _int(snapshot.get(key))
    return _int(details.get('tournament_id')), resource_id


def record_audit(db: Session, user_id: int | None, action: str, resource: str, details: dict) -> None:
    """Queue an audit entry in the caller's transaction; never commit separately."""
    tournament_id, resource_id = derive_ids(resource, details)
    db.add(AuditLog(user_id=user_id, action=action, resource=resource, details=details,
                    tournament_id=tournament_id, resource_id=resource_id))
