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

import ipaddress
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


def _network(ip: str) -> str:
    """One IPv6 user can hold a whole /64 block, so count those as one address.

    IPv4 visitors can arrive written as IPv6 (::ffff:1.2.3.4, or 6to4 / Teredo
    forms); those are turned back into the IPv4 address so they are not pooled.
    """
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 6:
        embedded = address.ipv4_mapped or address.sixtofour or (address.teredo[1] if address.teredo else None)
        if embedded is not None:
            return str(embedded)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def _keys(email: str, ip: str | None) -> dict[str, str]:
    keys = {"email": f"email:{email}"}
    if ip:  # without an address, only the overall per-email limit applies (no shared bucket)
        net = _network(ip)
        keys |= {"email_ip": f"email_ip:{email}|{net}", "ip": f"ip:{net}"}
    return keys


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
    """After a good sign-in, forget this email's failures (the per-address count stays)."""
    keys = _keys(email, ip)
    mine = [keys["email"]] + ([keys["email_ip"]] if "email_ip" in keys else [])
    db.execute(delete(LoginFailure).where(LoginFailure.key.in_(mine)))
