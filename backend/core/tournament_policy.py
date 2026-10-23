"""Lifecycle rules shared by permission hints and tournament mutations."""


def registrations_open(status: str) -> bool:
    return status == 'UPCOMING'
