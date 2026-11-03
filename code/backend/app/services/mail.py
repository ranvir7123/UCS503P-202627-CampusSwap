"""Email notices (FR-CONF-06): queue, remind, deliver.

Mail is always written to the outbox table first. It leaves only when a mail
server is set up (CAMPUSSWAP_SMTP_HOST and friends); otherwise it stays
"queued" and the staff page says plainly that nothing is being sent.
"""
from __future__ import annotations

import os
import smtplib
from collections.abc import Callable
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import timing
from app.models import CycleMember, Email, SwapCycle, User

IST = timedelta(hours=5, minutes=30)
MAX_ATTEMPTS = 5
Sender = Callable[[str, str, str], None]  # (to, subject, body)


def site_url() -> str:
    return os.environ.get("CAMPUSSWAP_SITE_URL", "http://127.0.0.1:8000").rstrip("/")


def ist(dt: datetime) -> str:
    return (dt + IST).strftime("%d %b %Y, %I:%M %p IST")


def queue(db: Session, now: datetime, user: User, kind: str, subject: str, body: str) -> Email:
    email = Email(created_at=now, kind=kind, to_user_id=user.id, to_address=user.email,
                  subject=subject, body=body, status="queued", attempts=0)
    db.add(email)
    return email


def match_found(db: Session, now: datetime, member: CycleMember) -> None:
    cycle, student = member.cycle, member.request.student
    queue(db, now, student, "match_found", f"CampusSwap: a {len(cycle.members)}-way room swap was found for you",
          f"Hi {student.name},\n\n"
          f"CampusSwap found a {len(cycle.members)}-way swap that includes you.\n"
          f"You would move from {member.gives_seat.room.label} to {member.receives_seat.room.label} "
          f"(your choice #{member.received_rank}).\n\n"
          f"Please confirm or decline before {ist(cycle.deadline)}:\n{site_url()}/dashboard.html\n\n"
          "If you do not answer by then, your request is closed and the others go back to the pool.\n\n"
          "CampusSwap, Thapar Institute hostel office")


def send_reminders(db: Session, now: datetime) -> int:
    """One reminder to each member who has not answered, once 12 hours (demo: 2 minutes) or less are left."""
    pending = db.scalars(
        select(CycleMember).join(SwapCycle).where(
            SwapCycle.status == "proposed", SwapCycle.deadline > now, SwapCycle.deadline <= now + timing.current().remind_before,
            CycleMember.response == "pending", CycleMember.reminded_at.is_(None))
    ).all()
    for member in pending:
        student, cycle = member.request.student, member.cycle
        queue(db, now, student, "deadline_reminder", "CampusSwap: please answer your room swap soon",
              f"Hi {student.name},\n\nYou have not yet answered the {len(cycle.members)}-way swap that moves you "
              f"to {member.receives_seat.room.label}. The deadline is {ist(cycle.deadline)}.\n\n"
              f"{site_url()}/dashboard.html\n\nCampusSwap, Thapar Institute hostel office")
        member.reminded_at = now
    db.flush()
    return len(pending)


def deliver(db: Session, now: datetime, sender: Sender | None) -> int:
    """Hand queued mail to the mail server. Returns how many were sent."""
    if sender is None:
        return 0
    queued = [(e.id, e.to_address, e.subject, e.body) for e in db.scalars(
        select(Email).where(Email.status == "queued", Email.attempts < MAX_ATTEMPTS).order_by(Email.id))]
    # Save everything first: talking to the mail server can take seconds, and
    # nobody else can save anything while this session holds the write lock.
    db.commit()
    sent = 0
    for email_id, to, subject, body in queued:
        try:
            sender(to, subject, body)
            error = None
        except Exception as exc:  # noqa: BLE001 - any failure: keep it queued and record why
            error = f"{type(exc).__name__}: {exc}"[:300]
        email = db.get(Email, email_id)
        email.attempts += 1
        if error:
            email.error = error
        else:
            email.status, email.sent_at, email.error = "sent", now, None
            sent += 1
        db.commit()
    return sent


def smtp_sender_from_env() -> Sender | None:
    """A sender for the mail server named in the environment, or None if none is set up.

    CAMPUSSWAP_SMTP_HOST, _PORT (587), _USER, _PASSWORD, _FROM (defaults to _USER).
    """
    host = os.environ.get("CAMPUSSWAP_SMTP_HOST", "").strip()
    if not host:
        return None
    port = int(os.environ.get("CAMPUSSWAP_SMTP_PORT", "587"))
    user = os.environ.get("CAMPUSSWAP_SMTP_USER", "")
    password = os.environ.get("CAMPUSSWAP_SMTP_PASSWORD", "")
    sender_address = os.environ.get("CAMPUSSWAP_SMTP_FROM", user or "campusswap@thapar.edu")

    def send(to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = sender_address, to, subject
        message.set_content(body)
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(message)

    return send


def outbox_view(db: Session, limit: int = 100) -> dict:
    from app.services.views import iso

    rows = db.scalars(select(Email).order_by(Email.id.desc()).limit(limit)).all()
    return {
        "delivery": "smtp" if os.environ.get("CAMPUSSWAP_SMTP_HOST", "").strip() else "off",
        "emails": [{"id": e.id, "created_at": iso(e.created_at), "kind": e.kind, "to": e.to_address,
                    "subject": e.subject, "body": e.body, "status": e.status, "attempts": e.attempts,
                    "error": e.error, "sent_at": iso(e.sent_at)} for e in rows],
    }
