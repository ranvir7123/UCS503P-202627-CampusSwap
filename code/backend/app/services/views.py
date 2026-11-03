"""Read-only data shaped for each page. No rules are enforced here."""
from __future__ import annotations

import csv
import io
from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CycleMember, Event, Hostel, MatchRun, Room, Student, SwapCycle, SwapRequest

MILESTONES = [
    ("submitted", "Request submitted"),
    ("pool", "In the matching pool"),
    ("match", "Match found"),
    ("confirmed", "Everyone confirmed"),
    ("approved", "Warden approved"),
]


# ---------------------------------------------------------------- helpers
def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.isoformat(timespec="seconds") + "Z"


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


def room_dict(room: Room) -> dict:
    return {
        "id": room.id, "hostel": {"code": room.hostel.code, "name": room.hostel.name},
        "block": room.block, "floor": room.floor, "number": room.number, "label": room.label,
        "seater": room.seater, "ac": room.ac, "washroom": room.washroom,
        "tags": [t.strip() for t in room.tags.split(",") if t.strip()],
    }


def pref_dict(pref) -> dict:
    return {"rank": pref.rank, "kind": "type" if pref.is_type else "room", "label": pref.label,
            "room": None if pref.is_type else room_dict(pref.room),
            "type": None if not pref.is_type else {
                "hostel": pref.type_hostel.code, "seater": pref.type_seater, "ac": pref.type_ac,
                "floor": pref.type_floor}}


def run_summary(run: MatchRun | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": run.id, "created_at": iso(run.created_at), "algorithm": run.algorithm, "dry_run": run.dry_run,
        "pool_size": run.pool_size, "matched": run.matched, "yield_pct": run.yield_pct,
        "first_choice_pct": run.first_choice_pct, "cycles_by_length": run.cycles_by_length,
    }


def _latest_saved_run(db: Session) -> MatchRun | None:
    return db.scalar(select(MatchRun).where(MatchRun.algorithm == "ttc", MatchRun.dry_run.is_(False))
                     .order_by(MatchRun.id.desc()).limit(1))


def _latest_membership(db: Session, request: SwapRequest) -> CycleMember | None:
    return db.scalar(select(CycleMember).where(CycleMember.request_id == request.id)
                     .order_by(CycleMember.id.desc()).limit(1))


def _count_status(db: Session, status: str) -> int:
    return db.scalar(select(func.count(SwapRequest.id)).where(SwapRequest.status == status))


# ---------------------------------------------------------------- login page
def public_stats(db: Session, now: datetime) -> dict:
    start = now.date() - timedelta(days=6)
    per_day = [0] * 7
    since = datetime.combine(start, time.min)
    for created in db.scalars(select(SwapRequest.created_at).where(SwapRequest.created_at >= since)):
        per_day[(created.date() - start).days] += 1
    return {
        "open_requests": _count_status(db, "open"),
        "rooms": db.scalar(select(func.count(Room.id))),
        "hostels": db.scalar(select(func.count(Hostel.id))),
        "requests_per_day": per_day,
        "last_run": run_summary(_latest_saved_run(db)),
    }


# ---------------------------------------------------------------- rooms page
def rooms_listing(db: Session, student: Student) -> dict:
    own_room_id = student.seat.room_id if student.seat else None
    open_by_room: dict[int, int] = {}  # room id -> how many occupants there want to swap
    others_open = select(SwapRequest).where(SwapRequest.status == "open", SwapRequest.student_id != student.id)
    for request in db.scalars(others_open):
        room_id = request.seat.room_id
        open_by_room[room_id] = open_by_room.get(room_id, 0) + 1

    hostels = db.scalars(select(Hostel).where(Hostel.gender == student.gender).order_by(Hostel.code)).all()
    rooms = []
    for hostel in hostels:
        for room in hostel.rooms:
            rooms.append({**room_dict(room), "is_own": room.id == own_room_id,
                          "open_to_swap": open_by_room.get(room.id, 0)})
    return {
        "hostels": [{"code": h.code, "name": h.name, "warden": h.warden_name} for h in hostels],
        "rooms": rooms,
        "last_run": run_summary(_latest_saved_run(db)),
    }


# ---------------------------------------------------------------- student dashboard
def student_dashboard(db: Session, student: Student, now: datetime) -> dict:
    request = db.scalar(select(SwapRequest).where(SwapRequest.student_id == student.id)
                        .order_by(SwapRequest.id.desc()).limit(1))
    if request is not None and request.status == "withdrawn":
        request = None

    cycle_view = None
    stage = 0
    if request is not None:
        stage = 1
        membership = _latest_membership(db, request) if request.status in ("matched", "completed") else None
        if membership is not None:
            cycle = membership.cycle
            stage = {"proposed": 3, "confirmed": 4, "approved": 5}.get(cycle.status, 1)
            cycle_view = _cycle_view(cycle, membership)

    seat = student.seat
    events = db.scalars(select(Event).where(Event.student_id == student.id)
                        .order_by(Event.id.desc()).limit(20)).all()
    return {
        "student": {"name": student.name, "email": student.email, "roll_no": student.roll_no,
                    "year": student.year, "branch": student.branch, "initials": initials(student.name)},
        "room": None if seat is None else {**room_dict(seat.room), "seat_label": seat.label,
                                           "warden": seat.room.hostel.warden_name},
        "request": None if request is None else {
            "tracking_id": request.tracking_id, "status": request.status, "created_at": iso(request.created_at),
            "preferences": [pref_dict(p) for p in request.preferences],
        },
        "cycle": cycle_view,
        "milestones": [
            {"key": key, "label": label, "state": "done" if i < stage else "current" if i == stage else "todo"}
            for i, (key, label) in enumerate(MILESTONES)
        ],
        "events": [{"created_at": iso(e.created_at), "kind": e.kind, "message": e.message} for e in events],
        "last_run": run_summary(_latest_saved_run(db)),
    }


def _cycle_view(cycle: SwapCycle, me: CycleMember) -> dict:
    return {
        "id": cycle.id, "status": cycle.status, "length": len(cycle.members),
        "deadline": iso(cycle.deadline), "created_at": iso(cycle.created_at),
        "my_response": me.response, "received_rank": me.received_rank,
        "accepted": sum(1 for m in cycle.members if m.response == "accepted"),
        "receive_room": room_dict(me.receives_seat.room),
        "give_room": room_dict(me.gives_seat.room),
        "members": [
            {"position": m.position, "name": m.request.student.name, "initials": initials(m.request.student.name),
             "tracking_id": m.request.tracking_id, "is_me": m.id == me.id, "response": m.response,
             "gives_room": room_dict(m.gives_seat.room)}
            for m in cycle.members
        ],
    }


# ---------------------------------------------------------------- admin
def admin_overview(db: Session) -> dict:
    latest_any = db.scalar(select(MatchRun).order_by(MatchRun.id.desc()).limit(1))
    latest_pairwise = db.scalar(select(MatchRun).where(MatchRun.algorithm == "pairwise")
                                .order_by(MatchRun.id.desc()).limit(1))
    comparison = None
    if latest_pairwise is not None:
        partner = db.scalar(select(MatchRun).where(
            MatchRun.algorithm == "ttc", MatchRun.dry_run.is_(True),
            MatchRun.created_at == latest_pairwise.created_at).order_by(MatchRun.id.desc()).limit(1))
        if partner is not None:
            comparison = {"ttc": partner.yield_pct, "pairwise": latest_pairwise.yield_pct}
    history = db.scalars(select(MatchRun.yield_pct).where(MatchRun.algorithm == "ttc", MatchRun.dry_run.is_(False))
                         .order_by(MatchRun.id.desc()).limit(10)).all()
    return {
        "open": _count_status(db, "open"),
        "matched": _count_status(db, "matched"),
        "completed": _count_status(db, "completed"),
        "awaiting_approval": db.scalar(select(func.count(SwapCycle.id)).where(SwapCycle.status == "confirmed")),
        "latest": run_summary(_latest_saved_run(db)),
        "comparison": comparison,
        "trace": latest_any.trace if latest_any else "",
        "trace_run": run_summary(latest_any),
        "history": list(reversed(history)),
    }


def admin_requests(db: Session) -> list[dict]:
    rows = []
    for request in db.scalars(select(SwapRequest).order_by(SwapRequest.id.desc())).all():
        membership = _latest_membership(db, request)
        cycle = membership.cycle if membership else None
        active_cycle = cycle is not None and request.status in ("matched", "completed")
        rows.append({
            "id": request.id, "tracking_id": request.tracking_id, "status": request.status,
            "created_at": iso(request.created_at),
            "student": {"name": request.student.name, "roll_no": request.student.roll_no,
                        "year": request.student.year, "initials": initials(request.student.name)},
            "offered_room": request.seat.room.label,
            "preferences": [p.label for p in request.preferences],
            "assigned_room": membership.receives_seat.room.label if active_cycle else None,
            "received_rank": membership.received_rank if active_cycle else None,
            "cycle": None if not active_cycle else {
                "id": cycle.id, "length": len(cycle.members), "status": cycle.status,
                "accepted": sum(1 for m in cycle.members if m.response == "accepted"),
                "chain": [{"tracking_id": m.request.tracking_id, "name": m.request.student.name,
                           "gives": m.gives_seat.room.label, "response": m.response} for m in cycle.members],
                "can_approve": cycle.status == "confirmed",
            },
        })
    return rows


def export_csv(db: Session) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["tracking_id", "student", "roll_no", "status", "offered_room", "assigned_room",
                     "received_rank", "cycle_id", "cycle_length", "cycle_status", "submitted_at"])
    for row in admin_requests(db):
        cycle = row["cycle"] or {}
        writer.writerow([row["tracking_id"], row["student"]["name"], row["student"]["roll_no"], row["status"],
                         row["offered_room"], row["assigned_room"] or "", row["received_rank"] or "",
                         cycle.get("id", ""), cycle.get("length", ""), cycle.get("status", ""), row["created_at"]])
    return out.getvalue()
