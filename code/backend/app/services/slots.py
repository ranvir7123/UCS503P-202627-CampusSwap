"""Faculty lecture-slot exchange (FR-SLOT-01): same flow as rooms, same TTC engine.

A teacher offers one of their slots and ranks up to 5 others that do not clash
with their other lectures. Staff run a slot round; every member of a chain
confirms; staff approve; each teacher (with their course) moves to the slot
they receive. The time and hall of each slot never change.
"""
from __future__ import annotations

import threading
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import timing
from app.errors import DomainError
from app.models import (Admin, Faculty, LectureSlot, MatchRun, SlotCycle, SlotCycleMember, SlotPreference,
                        SlotRequest)
from app.services import mail
from app.services.events import log
from engine import Participant, cycle_length_counts, match_yield, top_trading_cycles

MAX_CHOICES = 5
ACTIVE_STATUSES = ("open", "matched")
_run_lock = threading.Lock()


# ---------------------------------------------------------------- requests
def active_request(db: Session, faculty: Faculty) -> SlotRequest | None:
    return db.scalar(select(SlotRequest).where(SlotRequest.faculty_id == faculty.id,
                                               SlotRequest.status.in_(ACTIVE_STATUSES)))


def submit(db: Session, faculty: Faculty, slot_id: int, wanted: list[int], now: datetime) -> SlotRequest:
    if not wanted:
        raise DomainError(400, "empty_list", "Pick at least one slot you would prefer.")
    if len(wanted) > MAX_CHOICES:
        raise DomainError(400, "too_many", f"You can rank at most {MAX_CHOICES} slots.")
    if len(set(wanted)) != len(wanted):
        raise DomainError(400, "duplicate_slot", "Each slot can appear only once in your list.")
    offered = db.get(LectureSlot, slot_id)
    if offered is None or offered.owner_id != faculty.id:
        raise DomainError(400, "not_your_slot", "You can only offer a slot you teach.")
    if active_request(db, faculty) is not None:
        raise DomainError(409, "already_active", "You already have an active request. Withdraw it first.")
    kept = [s for s in faculty.slots if s.id != offered.id]  # lectures that stay where they are
    by_id = {s.id: s for s in db.scalars(select(LectureSlot).where(LectureSlot.id.in_(wanted)))}
    for wanted_id in wanted:
        slot = by_id.get(wanted_id)
        if slot is None:
            raise DomainError(400, "unknown_slot", f"Slot {wanted_id} does not exist.")
        if slot.owner_id == faculty.id:
            raise DomainError(400, "own_slot", "You already teach in that slot.")
        clash = next((k for k in kept if k.clashes_with(slot)), None)
        if clash is not None:
            raise DomainError(400, "slot_clash",
                              f"{slot.time_label} clashes with your {clash.course_code} lecture ({clash.time_label}).")

    request = SlotRequest(faculty=faculty, slot=offered, status="open", created_at=now, updated_at=now,
                          preferences=[SlotPreference(rank=r, slot_id=i) for r, i in enumerate(wanted, start=1)])
    try:
        with db.begin_nested():  # another submit may have landed a moment ago
            db.add(request)
            db.flush()
    except IntegrityError:
        raise DomainError(409, "already_active", "You already have an active request. Withdraw it first.") from None
    request.tracking_id = f"SL-{now.year}-{request.id:04d}"
    log(db, now, "slot_request_submitted",
        f"Slot request {request.tracking_id} submitted: offering {offered.course_code} on {offered.label}, "
        f"{len(wanted)} ranked slot(s).", student_id=faculty.id)
    db.flush()
    return request


def withdraw(db: Session, faculty: Faculty, now: datetime) -> SlotRequest:
    request = active_request(db, faculty)
    if request is None:
        raise DomainError(404, "no_request", "You have no active slot request.")
    if request.status == "matched":
        raise DomainError(409, "in_cycle", "You are in a proposed slot swap. Decline it instead of withdrawing.")
    request.status, request.updated_at = "withdrawn", now
    log(db, now, "slot_request_withdrawn", f"Slot request {request.tracking_id} withdrawn.", student_id=faculty.id)
    db.flush()
    return request


# ---------------------------------------------------------------- matching
def run_round(db: Session, admin: Admin, dry_run: bool, now: datetime) -> MatchRun:
    if not _run_lock.acquire(blocking=False):
        raise DomainError(409, "run_in_progress", "A slot round is already running.")
    try:
        expire_overdue_slots(db, now)
        pool = db.scalars(select(SlotRequest).where(SlotRequest.status == "open").order_by(SlotRequest.id)).all()
        by_id = {r.id: r for r in pool}
        result = top_trading_cycles(
            [Participant(r.id, r.slot_id, tuple(p.slot_id for p in r.preferences)) for r in pool])
        ranks = {pid: next(p.rank for p in by_id[pid].preferences if p.slot_id == slot_id)
                 for pid, slot_id in result.assignment.items()}
        run = MatchRun(
            created_at=now, run_by=admin, algorithm="slot_ttc", dry_run=dry_run,
            pool_size=len(pool), matched=len(result.assignment), yield_pct=match_yield(result, len(pool)),
            first_choice_pct=round(100 * sum(r == 1 for r in ranks.values()) / len(ranks), 1) if ranks else 0.0,
            cycles_by_length={str(k): v for k, v in cycle_length_counts(result).items()}, trace="",
        )
        lines = [f"Pool: {len(pool)} open slot request(s). Algorithm: Top Trading Cycles."]
        for rnd in result.rounds:
            lines.append(f"Round {rnd.number}: {rnd.active} teacher(s) point at the owner of their best slot.")
            for cycle in rnd.cycles:
                chain = " -> ".join(by_id[p].tracking_id for p in cycle.members + cycle.members[:1])
                lines.append(f"  Chain found ({len(cycle)}-way): {chain}  (each takes the next one's slot)")
            if rnd.kept:
                lines.append(f"  {len(rnd.kept)} teacher(s) have no available choice left and keep their slot.")
        lines.append(f"Matched {run.matched} of {run.pool_size} teachers (Match Yield {run.yield_pct}%).")
        run.trace = "\n".join(lines)
        db.add(run)
        db.flush()
        if not dry_run:
            for cycle in result.cycles:
                _save_cycle(db, run, cycle.members, by_id, result.assignment, ranks, now)
        log(db, now, "slot_match_run",
            f"Slot round #{run.id} ({'dry run' if dry_run else 'saved'}): matched {run.matched} of {run.pool_size}.")
        db.flush()
        return run
    finally:
        _run_lock.release()


def _save_cycle(db, run, members, by_id, assignment, ranks, now) -> None:
    cycle = SlotCycle(match_run_id=run.id, status="proposed", deadline=now + timing.current().confirm_window, created_at=now)
    db.add(cycle)
    for position, pid in enumerate(members):
        request = by_id[pid]
        cycle.members.append(SlotCycleMember(
            request=request, position=position, gives_slot_id=request.slot_id, receives_slot_id=assignment[pid],
            received_rank=ranks[pid], response="pending"))
        request.status, request.updated_at = "matched", now
    db.flush()
    for m in cycle.members:
        teacher = m.request.faculty
        log(db, now, "slot_match_found",
            f"Slot swap found ({len(members)}-way): you would teach {m.gives_slot.course_code} on "
            f"{m.receives_slot.label}. Please confirm before the deadline.", student_id=teacher.id, cycle_id=None)
        mail.queue(db, now, teacher, "slot_match_found",
                   f"CampusSwap: a {len(members)}-way lecture slot swap was found for you",
                   f"Dear {teacher.name},\n\nCampusSwap found a {len(members)}-way lecture slot swap that includes "
                   f"you.\nYour {m.gives_slot.course_code} lecture would move from {m.gives_slot.label} to "
                   f"{m.receives_slot.label} (your choice #{m.received_rank}).\n\nPlease confirm or decline "
                   f"before {mail.ist(cycle.deadline)}:\n{mail.site_url()}/slots.html\n\nCampusSwap")


# ---------------------------------------------------------------- confirm / approve
def accept(db: Session, faculty: Faculty, cycle_id: int, now: datetime) -> SlotCycle:
    cycle, member = _open_membership(db, faculty, cycle_id, now)
    member.response, member.responded_at = "accepted", now
    log(db, now, "slot_swap_accepted", "You confirmed the slot swap.", student_id=faculty.id)
    if all(m.response == "accepted" for m in cycle.members):
        cycle.status = "confirmed"
        for m in cycle.members:
            log(db, now, "slot_cycle_confirmed", "Everyone confirmed the slot swap. Waiting for staff approval.",
                student_id=m.request.faculty_id)
    db.flush()
    return cycle


def decline(db: Session, faculty: Faculty, cycle_id: int, now: datetime) -> SlotCycle:
    cycle, member = _open_membership(db, faculty, cycle_id, now)
    member.response, member.responded_at = "declined", now
    _dissolve(db, cycle, now, withdraw={member.id}, reason="a member declined")
    db.flush()
    return cycle


def approve(db: Session, admin: Admin, cycle_id: int, now: datetime) -> SlotCycle:
    cycle = db.get(SlotCycle, cycle_id)
    if cycle is None:
        raise DomainError(404, "no_cycle", "That slot swap does not exist.")
    if cycle.status != "confirmed":
        raise DomainError(409, "not_confirmed", "Only slot swaps confirmed by every member can be approved.")
    stale = next((m for m in cycle.members if m.gives_slot.owner_id != m.request.faculty_id), None)
    if stale is not None:  # the timetable changed after everyone confirmed
        _dissolve(db, cycle, now, withdraw=set(), reason="the timetable changed after it was confirmed")
        db.commit()  # kept even though the request itself fails
        raise DomainError(409, "stale_swap",
                          f"{stale.request.faculty.name} no longer teaches in {stale.gives_slot.label}, so this swap "
                          "was cancelled. Everyone in it is back in the pool.")
    # Read every move first, then apply, so no slot is overwritten before it is read.
    moves = [(m.receives_slot, m.request.faculty, m.gives_slot.course_code, m.gives_slot.course_name)
             for m in cycle.members]
    for slot, teacher, code, name in moves:
        slot.owner, slot.course_code, slot.course_name = teacher, code, name
    for m in cycle.members:
        m.request.status, m.request.updated_at = "completed", now
        log(db, now, "slot_swap_approved",
            f"Staff approved the slot swap. You now teach {m.receives_slot.course_code} on {m.receives_slot.label}.",
            student_id=m.request.faculty_id)
    cycle.status, cycle.closed_at, cycle.approved_by = "approved", now, admin
    db.flush()
    return cycle


def expire_overdue_slots(db: Session, now: datetime) -> int:
    overdue = db.scalars(select(SlotCycle).where(SlotCycle.status == "proposed", SlotCycle.deadline <= now)).all()
    for cycle in overdue:
        pending = {m.id for m in cycle.members if m.response == "pending"}
        _dissolve(db, cycle, now, withdraw=pending, reason="the confirmation deadline passed")
    db.flush()
    return len(overdue)


def _open_membership(db: Session, faculty: Faculty, cycle_id: int, now: datetime):
    expire_overdue_slots(db, now)
    cycle = db.get(SlotCycle, cycle_id)
    if cycle is None:
        raise DomainError(404, "no_cycle", "That slot swap does not exist.")
    member = next((m for m in cycle.members if m.request.faculty_id == faculty.id), None)
    if member is None:
        raise DomainError(403, "not_member", "You are not part of this slot swap.")
    if cycle.status != "proposed":
        raise DomainError(409, "cycle_closed", "This slot swap is no longer waiting for answers.")
    if member.response != "pending":
        raise DomainError(409, "already_answered", "You have already answered this slot swap.")
    return cycle, member


def _dissolve(db: Session, cycle: SlotCycle, now: datetime, withdraw: set[int], reason: str) -> None:
    cycle.status, cycle.closed_at = "dissolved", now
    for m in cycle.members:
        m.request.status = "withdrawn" if m.id in withdraw else "open"
        m.request.updated_at = now
        outcome = "Your request was closed." if m.id in withdraw else "You are back in the pool for the next round."
        log(db, now, "slot_cycle_dissolved", f"The slot swap was cancelled because {reason}. {outcome}",
            student_id=m.request.faculty_id)


# ---------------------------------------------------------------- page data
def slot_dict(slot: LectureSlot) -> dict:
    return {"id": slot.id, "day": slot.day, "start_min": slot.start_min, "end_min": slot.end_min,
            "time_label": slot.time_label, "label": slot.label, "hall": slot.hall,
            "course_code": slot.course_code, "course_name": slot.course_name,
            "owner": {"id": slot.owner_id, "name": slot.owner.name, "department": slot.owner.department}}


def faculty_home(db: Session, faculty: Faculty, now: datetime) -> dict:
    from app.models import Event
    from app.services.views import initials, iso, run_summary

    expire_overdue_slots(db, now)
    request = db.scalar(select(SlotRequest).where(SlotRequest.faculty_id == faculty.id)
                        .order_by(SlotRequest.id.desc()).limit(1))
    if request is not None and request.status == "withdrawn":
        request = None
    offered_id = request.slot_id if request else None
    open_slots = {r.slot_id for r in db.scalars(select(SlotRequest).where(
        SlotRequest.status == "open", SlotRequest.faculty_id != faculty.id))}

    cycle_view = None
    if request is not None and request.status in ("matched", "completed"):
        membership = db.scalar(select(SlotCycleMember).where(SlotCycleMember.request_id == request.id)
                               .order_by(SlotCycleMember.id.desc()).limit(1))
        if membership is not None:
            cycle = membership.cycle
            cycle_view = {
                "id": cycle.id, "status": cycle.status, "length": len(cycle.members),
                "deadline": iso(cycle.deadline), "my_response": membership.response,
                "received_rank": membership.received_rank, "gives": slot_dict(membership.gives_slot),
                "receives": slot_dict(membership.receives_slot),
                "accepted": sum(m.response == "accepted" for m in cycle.members),
                "members": [{"name": m.request.faculty.name, "initials": initials(m.request.faculty.name),
                             "is_me": m.id == membership.id, "response": m.response,
                             "gives": m.gives_slot.label} for m in cycle.members],
            }

    def overlaps(slot: LectureSlot) -> list[int]:
        """Your lectures this slot overlaps. Offering one of them frees that time."""
        if slot.owner_id == faculty.id:
            return []
        return [k.id for k in faculty.slots if k.clashes_with(slot)]

    slots = db.scalars(select(LectureSlot).order_by(LectureSlot.day, LectureSlot.start_min, LectureSlot.hall)).all()
    events = db.scalars(select(Event).where(Event.student_id == faculty.id).order_by(Event.id.desc()).limit(20)).all()
    latest = db.scalar(select(MatchRun).where(MatchRun.algorithm == "slot_ttc", MatchRun.dry_run.is_(False))
                       .order_by(MatchRun.id.desc()).limit(1))
    return {
        "me": {"name": faculty.name, "email": faculty.email, "department": faculty.department,
               "initials": initials(faculty.name)},
        "my_slots": [slot_dict(s) for s in faculty.slots],
        "slots": [{**slot_dict(s), "is_mine": s.owner_id == faculty.id, "open_to_swap": s.id in open_slots,
                   "clashes_with": overlaps(s),
                   "clashes": any(i != offered_id for i in overlaps(s))}
                  for s in slots],
        "request": None if request is None else {
            "tracking_id": request.tracking_id, "status": request.status, "created_at": iso(request.created_at),
            "offered": slot_dict(request.slot),
            "preferences": [{"rank": p.rank, "slot": slot_dict(p.slot)} for p in request.preferences],
        },
        "cycle": cycle_view,
        "events": [{"created_at": iso(e.created_at), "kind": e.kind, "message": e.message} for e in events],
        "last_run": run_summary(latest),
    }


def admin_board(db: Session) -> dict:
    from app.services.views import initials, iso, run_summary

    rows = []
    for request in db.scalars(select(SlotRequest).order_by(SlotRequest.id.desc())).all():
        membership = db.scalar(select(SlotCycleMember).where(SlotCycleMember.request_id == request.id)
                               .order_by(SlotCycleMember.id.desc()).limit(1))
        live = membership is not None and request.status in ("matched", "completed")
        cycle = membership.cycle if live else None
        rows.append({
            "id": request.id, "tracking_id": request.tracking_id, "status": request.status,
            "created_at": iso(request.created_at),
            "faculty": {"name": request.faculty.name, "department": request.faculty.department,
                        "initials": initials(request.faculty.name)},
            "offered": slot_dict(request.slot) | {"course_code": request.slot.course_code},
            "preferences": [p.slot.label for p in request.preferences],
            "assigned": membership.receives_slot.label if live else None,
            "cycle": None if cycle is None else {
                "id": cycle.id, "length": len(cycle.members), "status": cycle.status,
                "accepted": sum(m.response == "accepted" for m in cycle.members),
                "can_approve": cycle.status == "confirmed",
                "chain": [{"tracking_id": m.request.tracking_id, "name": m.request.faculty.name,
                           "gives": m.gives_slot.label, "response": m.response} for m in cycle.members],
            },
        })
    latest = db.scalar(select(MatchRun).where(MatchRun.algorithm == "slot_ttc").order_by(MatchRun.id.desc()).limit(1))
    return {"requests": rows, "latest": run_summary(latest), "trace": latest.trace if latest else "",
            "open": sum(r["status"] == "open" for r in rows),
            "awaiting_approval": sum(1 for r in rows if r["cycle"] and r["cycle"]["can_approve"]) }
