"""Feature 1: a student submits (or withdraws) a ranked swap request."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import Hostel, Preference, Room, Seat, Student, SwapRequest
from app.services.events import log

MAX_CHOICES = 5
ACTIVE_STATUSES = ("open", "matched")


def active_request(db: Session, student: Student) -> SwapRequest | None:
    return db.scalar(
        select(SwapRequest).where(SwapRequest.student_id == student.id, SwapRequest.status.in_(ACTIVE_STATUSES))
    )


def submit_request(db: Session, student: Student, choices: list[int | dict], now: datetime) -> SwapRequest:
    """choices, best first: a room id, or a room type {"hostel": code, "seater", "ac", "floor"}."""
    if not choices:
        raise DomainError(400, "empty_list", "Pick at least one room.")
    if len(choices) > MAX_CHOICES:
        raise DomainError(400, "too_many", f"You can rank at most {MAX_CHOICES} choices.")
    keys = [c if isinstance(c, int) else tuple(sorted(c.items())) for c in choices]
    if len(set(keys)) != len(keys):
        raise DomainError(400, "duplicate_room", "Each room or room type can appear only once in your list.")
    seat = student.seat
    if seat is None:
        raise DomainError(409, "no_seat", "You have no room allocated, so there is nothing to swap.")
    if active_request(db, student) is not None:
        raise DomainError(409, "already_active", "You already have an active request. Withdraw it first.")

    room_ids = [c for c in choices if isinstance(c, int)]
    rooms = {r.id: r for r in db.scalars(select(Room).where(Room.id.in_(room_ids)))}
    preferences = [
        _room_choice(rooms.get(c), c, rank, seat, student) if isinstance(c, int)
        else _type_choice(db, c, rank, seat, student)
        for rank, c in enumerate(choices, start=1)
    ]

    request = SwapRequest(
        student=student, seat=seat, status="open", created_at=now, updated_at=now, preferences=preferences,
    )
    db.add(request)
    db.flush()  # gives the request its id
    request.tracking_id = f"CS-{now.year}-{request.id:04d}"
    log(db, now, "request_submitted",
        f"Request {request.tracking_id} submitted with {len(choices)} ranked choice(s).", student_id=student.id)
    db.flush()
    return request


def withdraw_request(db: Session, student: Student, now: datetime) -> SwapRequest:
    request = active_request(db, student)
    if request is None:
        raise DomainError(404, "no_request", "You have no active request.")
    if request.status == "matched":
        raise DomainError(409, "in_cycle", "You are in a proposed swap. Decline it instead of withdrawing.")
    request.status = "withdrawn"
    request.updated_at = now
    log(db, now, "request_withdrawn", f"Request {request.tracking_id} withdrawn.", student_id=student.id)
    db.flush()
    return request


def _room_choice(room: Room | None, room_id: int, rank: int, seat: Seat, student: Student) -> Preference:
    if room is None:
        raise DomainError(400, "unknown_room", f"Room {room_id} does not exist.")
    if room.id == seat.room_id:
        raise DomainError(400, "own_room", "You can't rank the room you already live in.")
    if room.hostel.gender != student.gender:
        raise DomainError(400, "wrong_hostel_gender", f"{room.label} is not in a hostel you can live in.")
    return Preference(rank=rank, room_id=room.id)


def _type_choice(db: Session, choice: dict, rank: int, seat: Seat, student: Student) -> Preference:
    code = str(choice.get("hostel", "")).upper()
    hostel = db.scalar(select(Hostel).where(Hostel.code == code))
    if hostel is None:
        raise DomainError(400, "unknown_hostel", f"Hostel {code} does not exist.")
    if hostel.gender != student.gender:
        raise DomainError(400, "wrong_hostel_gender", f"{hostel.name} is not a hostel you can live in.")
    pref = Preference(rank=rank, type_hostel=hostel, type_hostel_id=hostel.id, type_seater=choice.get("seater"),
                      type_ac=choice.get("ac"), type_floor=choice.get("floor"))
    if not any(r.id != seat.room_id for r in pref.rooms()):
        raise DomainError(400, "empty_type", f"No room other than yours matches: {pref.label}.")
    return pref
