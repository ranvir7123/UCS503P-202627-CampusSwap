"""Automatic matching rounds (FR-MATCH-10) and the background tick that drives them.

tick() is the one thing the background loop calls, every 30 seconds:
expire overdue swaps, send deadline reminders, run a round if one is due,
and hand queued mail to the mail server.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import Admin, MatchRun, Schedule
from app.services import mail
from app.services.cycles import expire_overdue

MAX_EVERY_HOURS = 24 * 14


def _row(db: Session) -> Schedule:
    row = db.get(Schedule, 1)
    if row is None:
        row = Schedule(id=1, enabled=False, every_hours=24)
        db.add(row)
        db.flush()
    return row


def view(db: Session) -> dict:
    from app.services.views import iso

    row = _row(db)
    return {"enabled": row.enabled, "every_hours": row.every_hours, "next_run_at": iso(row.next_run_at),
            "set_by": row.set_by.name if row.set_by else None, "last_run_id": row.last_run_id}


def update(db: Session, admin: Admin, enabled: bool, every_hours: int, now: datetime) -> Schedule:
    if not 1 <= every_hours <= MAX_EVERY_HOURS:
        raise DomainError(400, "bad_interval", f"Choose between 1 and {MAX_EVERY_HOURS} hours.")
    row = _row(db)
    row.enabled, row.every_hours, row.set_by = enabled, every_hours, admin
    row.next_run_at = now + timedelta(hours=every_hours) if enabled else None
    db.flush()
    return row


def run_due(db: Session, now: datetime) -> MatchRun | None:
    """Run one saved TTC round if it is due. Missed rounds are not run twice."""
    from app.services.matching import run_matching

    row = _row(db)
    if not row.enabled or row.next_run_at is None or row.next_run_at > now:
        return None
    step = timedelta(hours=row.every_hours)
    while row.next_run_at <= now:
        row.next_run_at += step
    try:
        run = run_matching(db, row.set_by, "ttc", dry_run=False, now=now)
    except DomainError:  # a round started by hand is running right now: try again next time
        row.next_run_at = now
        return None
    row.last_run_id = run.id
    db.flush()
    return run


def tick(db: Session, now: datetime, sender: mail.Sender | None) -> None:

    expire_overdue(db, now)
    mail.send_reminders(db, now)
    run_due(db, now)
    mail.deliver(db, now, sender)
    db.commit()
