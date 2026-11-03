"""Sign-in rules the server enforces itself (the page checks are only a convenience).

- Only institute addresses (ending in @thapar.edu) may sign in.
- Within 15 minutes, too many failures block further attempts until the oldest
  of them is 15 minutes old:
    5 for one email from one network address (stops one guesser),
    20 from one network address for any emails (stops trying many accounts),
    50 for one email from all addresses together (stops guessing spread out).
  The per-email limit is counted per address, so a stranger typing wrong
  passwords for someone else's email cannot lock the real owner out.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import LoginFailure

INSTITUTE_DOMAIN = "@thapar.edu"
WINDOW = timedelta(minutes=15)
LIMITS = {"email_ip": 5, "ip": 20, "email": 50}


def normalise_email(raw: str) -> str:
    email = raw.strip().lower()
    local, _, _domain = email.partition("@")
    if not local or not email.endswith(INSTITUTE_DOMAIN) or email.count("@") != 1:
        raise DomainError(400, "not_institute_email", "Use your institute email address (ending in @thapar.edu).")
    return email


def _keys(email: str, ip: str | None) -> dict[str, str]:
    ip = ip or "unknown"
    return {"email_ip": f"email_ip:{email}|{ip}", "ip": f"ip:{ip}", "email": f"email:{email}"}


def check_not_blocked(db: Session, email: str, ip: str | None, now: datetime) -> None:
    since = now - WINDOW
    db.execute(delete(LoginFailure).where(LoginFailure.created_at <= since))
    for kind, key in _keys(email, ip).items():
        times = db.scalars(select(LoginFailure.created_at).where(
            LoginFailure.key == key, LoginFailure.created_at > since).order_by(LoginFailure.created_at)).all()
        over = len(times) - LIMITS[kind]
        if over >= 0:
            unblocks_at = times[over] + WINDOW  # when enough old failures have aged out
            minutes = max(1, math.ceil((unblocks_at - now).total_seconds() / 60))
            raise DomainError(429, "too_many_attempts",
                              f"Too many failed sign-ins. Try again in {minutes} minute{'s' if minutes > 1 else ''}.")


def record_failure(db: Session, email: str, ip: str | None, now: datetime) -> None:
    for key in _keys(email, ip).values():
        db.add(LoginFailure(key=key, created_at=now))
    db.commit()  # kept even though the request itself fails


def clear_failures(db: Session, email: str, ip: str | None) -> None:
    keys = _keys(email, ip)
    db.execute(delete(LoginFailure).where(LoginFailure.key.in_([keys["email_ip"], keys["email"]])))
