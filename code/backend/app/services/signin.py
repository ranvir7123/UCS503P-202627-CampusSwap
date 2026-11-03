"""Sign-in rules the server enforces itself (the page checks are only a convenience).

- Only institute addresses (ending in @thapar.edu) may sign in.
- 5 failed attempts for one email, or 20 from one network address, within
  15 minutes block further attempts until the oldest of them is 15 minutes old.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import LoginFailure

INSTITUTE_DOMAIN = "@thapar.edu"
WINDOW = timedelta(minutes=15)
LIMITS = {"email": 5, "ip": 20}


def normalise_email(raw: str) -> str:
    email = raw.strip().lower()
    local, _, _domain = email.partition("@")
    if not local or not email.endswith(INSTITUTE_DOMAIN) or email.count("@") != 1:
        raise DomainError(400, "not_institute_email", "Use your institute email address (ending in @thapar.edu).")
    return email


def _keys(email: str, ip: str | None) -> dict[str, str]:
    keys = {"email": f"email:{email}"}
    if ip:
        keys["ip"] = f"ip:{ip}"
    return keys


def check_not_blocked(db: Session, email: str, ip: str | None, now: datetime) -> None:
    since = now - WINDOW
    db.execute(delete(LoginFailure).where(LoginFailure.created_at <= since))
    for kind, key in _keys(email, ip).items():
        recent = select(LoginFailure.created_at).where(LoginFailure.key == key, LoginFailure.created_at > since)
        if db.scalar(select(func.count()).select_from(recent.subquery())) >= LIMITS[kind]:
            oldest = db.scalar(select(func.min(LoginFailure.created_at)).where(
                LoginFailure.key == key, LoginFailure.created_at > since))
            minutes = max(1, math.ceil((oldest + WINDOW - now).total_seconds() / 60))
            raise DomainError(429, "too_many_attempts",
                              f"Too many failed sign-ins. Try again in {minutes} minute{'s' if minutes > 1 else ''}.")


def record_failure(db: Session, email: str, ip: str | None, now: datetime) -> None:
    for key in _keys(email, ip).values():
        db.add(LoginFailure(key=key, created_at=now))
    db.commit()  # kept even though the request itself fails


def clear_failures(db: Session, email: str) -> None:
    db.execute(delete(LoginFailure).where(LoginFailure.key == f"email:{email}"))
