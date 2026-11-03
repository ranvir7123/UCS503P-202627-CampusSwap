"""Shared building blocks for routes: DB session, current time, who is logged in."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.errors import DomainError
from app.models import Admin, Faculty, LoginSession, Student, User
from app.security import token_digest

SESSION_COOKIE = "cs_session"
SESSION_HOURS = 12


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as db:
        yield db


def get_now() -> datetime:
    """Replaced by a fixed time in tests."""
    return utcnow()


DB = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]


def current_user(db: DB, now: Now, cs_session: Annotated[str | None, Cookie()] = None) -> User:
    if not cs_session:
        raise DomainError(401, "not_logged_in", "Please log in.")
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_digest(cs_session)))
    if session is None or session.expires_at <= now:
        raise DomainError(401, "not_logged_in", "Your session has expired. Please log in again.")
    return session.user


def current_student(user: Annotated[User, Depends(current_user)]) -> Student:
    if not isinstance(user, Student):
        raise DomainError(403, "forbidden", "Only students can do this.")
    return user


def current_admin(user: Annotated[User, Depends(current_user)]) -> Admin:
    if not isinstance(user, Admin):
        raise DomainError(403, "forbidden", "Only hostel staff can do this.")
    return user


def current_faculty(user: Annotated[User, Depends(current_user)]) -> Faculty:
    if not isinstance(user, Faculty):
        raise DomainError(403, "forbidden", "Only faculty can do this.")
    return user


CurrentStudent = Annotated[Student, Depends(current_student)]
CurrentFaculty = Annotated[Faculty, Depends(current_faculty)]
CurrentAdmin = Annotated[Admin, Depends(current_admin)]
CurrentUser = Annotated[User, Depends(current_user)]
