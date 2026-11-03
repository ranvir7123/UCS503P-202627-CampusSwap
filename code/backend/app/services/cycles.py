"""After a match: each member confirms or declines; the warden approves.

- Everyone accepts          -> cycle "confirmed", waiting for the warden.
- Anyone declines           -> cycle "dissolved"; decliner withdrawn, others back to the pool.
- Deadline passes           -> cycle "dissolved"; non-answerers withdrawn, accepters back to the pool.
- Warden approves confirmed -> seats change hands, requests "completed".
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import Admin, CycleMember, Student, SwapCycle
from app.services.events import log
from app.services.pdf import approval_form


def accept(db: Session, student: Student, cycle_id: int, now: datetime) -> SwapCycle:
    cycle, member = _open_membership(db, student, cycle_id, now)
    member.response, member.responded_at = "accepted", now
    log(db, now, "swap_accepted", "You confirmed the swap.", student_id=student.id, cycle_id=cycle.id)
    if all(m.response == "accepted" for m in cycle.members):
        cycle.status = "confirmed"
        for m in cycle.members:
            log(db, now, "cycle_confirmed", "Everyone confirmed. Waiting for warden approval.",
                student_id=m.request.student_id, cycle_id=cycle.id)
    db.flush()
    return cycle


def decline(db: Session, student: Student, cycle_id: int, now: datetime) -> SwapCycle:
    cycle, member = _open_membership(db, student, cycle_id, now)
    member.response, member.responded_at = "declined", now
    _dissolve(db, cycle, now, withdraw={member.id}, reason="a member declined")
    db.flush()
    return cycle


def approve(db: Session, admin: Admin, cycle_id: int, now: datetime) -> SwapCycle:
    cycle = db.get(SwapCycle, cycle_id)
    if cycle is None:
        raise DomainError(404, "no_cycle", "That swap does not exist.")
    if cycle.status != "confirmed":
        raise DomainError(409, "not_confirmed", "Only swaps confirmed by every member can be approved.")
    # Each seat may have only one occupant, so empty all seats first, then refill.
    for m in cycle.members:
        m.gives_seat.occupant = None
    db.flush()
    for m in cycle.members:
        m.receives_seat.occupant = m.request.student
        m.request.status, m.request.updated_at = "completed", now
    cycle.status, cycle.closed_at, cycle.approved_by = "approved", now, admin
    for m in cycle.members:
        log(db, now, "swap_approved", f"Warden approved the swap. Your new room: {m.receives_seat.room.label}.",
            student_id=m.request.student_id, cycle_id=cycle.id)
    db.flush()
    return cycle


def approval_form_pdf(db: Session, cycle_id: int) -> bytes:
    """The signed-off form the hostel office files for an approved swap (FR-APPR-03)."""
    cycle = db.get(SwapCycle, cycle_id)
    if cycle is None:
        raise DomainError(404, "no_cycle", "That swap does not exist.")
    if cycle.status != "approved":
        raise DomainError(409, "not_approved", "The form is ready once the warden has approved the swap.")
    return approval_form(cycle)


def expire_overdue(db: Session, now: datetime) -> int:
    overdue = db.scalars(
        select(SwapCycle).where(SwapCycle.status == "proposed", SwapCycle.deadline <= now)
    ).all()
    for cycle in overdue:
        pending = {m.id for m in cycle.members if m.response == "pending"}
        _dissolve(db, cycle, now, withdraw=pending, reason="the confirmation deadline passed")
    db.flush()
    return len(overdue)


def _open_membership(db: Session, student: Student, cycle_id: int, now: datetime) -> tuple[SwapCycle, CycleMember]:
    expire_overdue(db, now)
    cycle = db.get(SwapCycle, cycle_id)
    if cycle is None:
        raise DomainError(404, "no_cycle", "That swap does not exist.")
    member = next((m for m in cycle.members if m.request.student_id == student.id), None)
    if member is None:
        raise DomainError(403, "not_member", "You are not part of this swap.")
    if cycle.status != "proposed":
        raise DomainError(409, "cycle_closed", "This swap is no longer waiting for answers.")
    if member.response != "pending":
        raise DomainError(409, "already_answered", "You have already answered this swap.")
    return cycle, member


def _dissolve(db: Session, cycle: SwapCycle, now: datetime, withdraw: set[int], reason: str) -> None:
    cycle.status, cycle.closed_at = "dissolved", now
    for m in cycle.members:
        m.request.status = "withdrawn" if m.id in withdraw else "open"
        m.request.updated_at = now
        outcome = "Your request was closed." if m.id in withdraw else "You are back in the pool for the next round."
        log(db, now, "cycle_dissolved", f"The swap was cancelled because {reason}. {outcome}",
            student_id=m.request.student_id, cycle_id=cycle.id)
