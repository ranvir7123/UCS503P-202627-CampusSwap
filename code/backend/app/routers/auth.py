from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response
from sqlalchemy import delete, select

from app.deps import DB, SESSION_COOKIE, SESSION_HOURS, CurrentUser, Now, current_user
from app.errors import DomainError
from app.models import LoginSession, Student, User
from app.schemas import LoginIn
from app.security import hash_password, new_session_token, token_digest, verify_password
from app.services import signin
from app.services.views import initials

router = APIRouter(prefix="/api/auth", tags=["auth"])
ROLE_TABS = {"student": "Student", "admin": "Hostel Staff"}
_DUMMY_HASH = hash_password("timing-equaliser")  # so unknown emails take as long as wrong passwords


def me_payload(user: User) -> dict:
    data = {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "initials": initials(user.name)}
    if isinstance(user, Student):
        data |= {"roll_no": user.roll_no, "year": user.year, "branch": user.branch,
                 "room": user.seat.room.label if user.seat else None}
    return data


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DB, now: Now) -> dict:
    email = signin.normalise_email(body.email)
    ip = request.client.host if request.client else None
    signin.check_not_blocked(db, email, ip, now)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
    if user is None or not verify_password(body.password, user.password_hash):
        signin.record_failure(db, email, ip, now)
        raise DomainError(401, "bad_credentials", "Wrong email or password.")
    if user.role != body.role:
        raise DomainError(403, "wrong_role", f"This account belongs on the {ROLE_TABS[user.role]} tab. "
                                             "Switch tabs and try again.")
    signin.clear_failures(db, email)
    token = new_session_token()
    db.add(LoginSession(token_hash=token_digest(token), user=user, expires_at=now + timedelta(hours=SESSION_HOURS)))
    db.commit()
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=request.app.state.secure,
                        max_age=SESSION_HOURS * 3600, path="/")
    return me_payload(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: DB, cs_session: Annotated[str | None, Cookie()] = None) -> dict:
    if cs_session:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_digest(cs_session)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax",
                           secure=request.app.state.secure)
    return {"ok": True}


@router.get("/me")
def me(user: CurrentUser) -> dict:
    return me_payload(user)


@router.get("/status")
def status(db: DB, now: Now, cs_session: Annotated[str | None, Cookie()] = None) -> dict:
    """Who is signed in, answering calmly when nobody is (used by the login page)."""
    try:
        user = current_user(db, now, cs_session)
    except DomainError:
        return {"user": None}
    return {"user": me_payload(user)}
