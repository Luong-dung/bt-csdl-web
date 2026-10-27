"""Lifecycle rules shared by permission hints and tournament mutations."""


def registrations_open(status: str, roster_locked_at=None) -> bool:
    return status == 'UPCOMING' and roster_locked_at is None


def registration_resolution_open(status: str) -> bool:
    """Rejecting/cancelling PENDING does not change the frozen APPROVED teams."""
    return status == 'UPCOMING'


def roster_editable(tournament) -> bool:
    return registrations_open(tournament.status, tournament.roster_locked_at)


def stages_editable(status: str) -> bool:
    return status == 'UPCOMING'
