"""Database tables (SQLAlchemy 2.0 declarative style).

Times are stored as naive UTC datetimes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- people
class User(Base):
    """Anyone who can log in. Student, Admin and Faculty share this one table."""

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(10))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(200))
    __mapper_args__ = {"polymorphic_on": "role", "polymorphic_identity": "user"}


class Student(User):
    roll_no: Mapped[Optional[str]] = mapped_column(String(12), unique=True, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)  # "M" / "F"
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    seat: Mapped[Optional["Seat"]] = relationship(back_populates="occupant", uselist=False)
    __mapper_args__ = {"polymorphic_identity": "student"}


class Admin(User):
    __mapper_args__ = {"polymorphic_identity": "admin"}


class Faculty(User):
    department: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    slots: Mapped[list["LectureSlot"]] = relationship(back_populates="owner", order_by="LectureSlot.day, LectureSlot.start_min")
    __mapper_args__ = {"polymorphic_identity": "faculty"}


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    user: Mapped[User] = relationship()


class LoginFailure(Base):
    """One failed sign-in, kept for a short while to slow down password guessing.

    key is "email:<address>" or "ip:<address>".
    """

    __tablename__ = "login_failures"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


# ---------------------------------------------------------------- places
class Hostel(Base):
    __tablename__ = "hostels"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(4), unique=True)
    name: Mapped[str] = mapped_column(String(40))
    gender: Mapped[str] = mapped_column(String(1))  # who may live here: "M" / "F"
    warden_name: Mapped[str] = mapped_column(String(80))
    rooms: Mapped[list["Room"]] = relationship(back_populates="hostel", order_by="Room.id")


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("hostel_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    block: Mapped[str] = mapped_column(String(4))
    floor: Mapped[int] = mapped_column(Integer)
    number: Mapped[str] = mapped_column(String(8))
    seater: Mapped[int] = mapped_column(Integer)  # 1, 2 or 3 beds
    ac: Mapped[bool] = mapped_column(Boolean)
    washroom: Mapped[str] = mapped_column(String(10))  # "attached" / "common"
    tags: Mapped[str] = mapped_column(String(200), default="")  # comma separated
    hostel: Mapped[Hostel] = relationship(back_populates="rooms")
    seats: Mapped[list["Seat"]] = relationship(back_populates="room", order_by="Seat.id")

    @property
    def label(self) -> str:
        return f"{self.hostel.name} · {self.number}"


class Seat(Base):
    """One bed. A double room has two seats, each with its own occupant."""

    __tablename__ = "seats"
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    label: Mapped[str] = mapped_column(String(2))  # "A", "B", "C"
    occupant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    room: Mapped[Room] = relationship(back_populates="seats")
    occupant: Mapped[Optional[Student]] = relationship(back_populates="seat")


# ---------------------------------------------------------------- requests
ACTIVE = text("status IN ('open', 'matched')")


def one_active_per(table: str, column: str) -> Index:
    """The database itself allows only one open or matched request per person,
    so two submits at the same moment cannot both get through."""
    return Index(f"one_active_{table}", column, unique=True, sqlite_where=ACTIVE, postgresql_where=ACTIVE)


class SwapRequest(Base):
    __tablename__ = "swap_requests"
    __table_args__ = (one_active_per("swap_requests", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tracking_id: Mapped[Optional[str]] = mapped_column(String(16), unique=True, nullable=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"))  # the seat offered
    status: Mapped[str] = mapped_column(String(10))  # open / matched / completed / withdrawn
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    student: Mapped[Student] = relationship()
    seat: Mapped[Seat] = relationship()
    preferences: Mapped[list["Preference"]] = relationship(
        back_populates="request", order_by="Preference.rank", cascade="all, delete-orphan"
    )


class Preference(Base):
    """One ranked choice: either one exact room, or a room type in one hostel.

    A type is a hostel plus any of seater / AC / floor; an unset filter means "any".
    """

    __tablename__ = "preferences"
    __table_args__ = (UniqueConstraint("request_id", "rank"), UniqueConstraint("request_id", "room_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("swap_requests.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer)  # 1 = most wanted
    room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rooms.id"), nullable=True)
    type_hostel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hostels.id"), nullable=True)
    type_seater: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    type_ac: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    type_floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    request: Mapped[SwapRequest] = relationship(back_populates="preferences")
    room: Mapped[Optional[Room]] = relationship()
    type_hostel: Mapped[Optional[Hostel]] = relationship()

    @property
    def is_type(self) -> bool:
        return self.room_id is None

    def matches(self, room: Room) -> bool:
        if not self.is_type:
            return room.id == self.room_id
        return (room.hostel_id == self.type_hostel_id
                and self.type_seater in (None, room.seater)
                and self.type_ac in (None, room.ac)
                and self.type_floor in (None, room.floor))

    def rooms(self) -> list[Room]:
        """The rooms this choice stands for, in room order."""
        if not self.is_type:
            return [self.room]
        return [r for r in self.type_hostel.rooms if self.matches(r)]

    @property
    def label(self) -> str:
        if not self.is_type:
            return self.room.label
        seater = f"{self.type_seater}-seater " if self.type_seater else ""
        ac = {True: "AC ", False: "non-AC ", None: ""}[self.type_ac]
        floor = f", floor {self.type_floor}" if self.type_floor is not None else ""
        return f"Any {seater}{ac}room in {self.type_hostel.name}{floor}"


# ---------------------------------------------------------------- matching
class MatchRun(Base):
    __tablename__ = "match_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    run_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    algorithm: Mapped[str] = mapped_column(String(10))  # "ttc" / "pairwise"
    dry_run: Mapped[bool] = mapped_column(Boolean)
    pool_size: Mapped[int] = mapped_column(Integer)
    matched: Mapped[int] = mapped_column(Integer)
    yield_pct: Mapped[float] = mapped_column(Float)
    first_choice_pct: Mapped[float] = mapped_column(Float)
    cycles_by_length: Mapped[dict] = mapped_column(JSON)  # {"2": 1, "3": 1}
    trace: Mapped[str] = mapped_column(Text)
    run_by: Mapped[User] = relationship()
    cycles: Mapped[list["SwapCycle"]] = relationship(back_populates="match_run", order_by="SwapCycle.id")


class SwapCycle(Base):
    __tablename__ = "swap_cycles"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id"))
    status: Mapped[str] = mapped_column(String(10))  # proposed / confirmed / approved / dissolved
    deadline: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    match_run: Mapped[MatchRun] = relationship(back_populates="cycles")
    approved_by: Mapped[Optional[User]] = relationship()
    members: Mapped[list["CycleMember"]] = relationship(back_populates="cycle", order_by="CycleMember.position")


class CycleMember(Base):
    """One student in a chain: gives one seat, receives the next member's seat."""

    __tablename__ = "cycle_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("swap_cycles.id"))
    request_id: Mapped[int] = mapped_column(ForeignKey("swap_requests.id"))
    position: Mapped[int] = mapped_column(Integer)
    gives_seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"))
    receives_seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"))
    received_rank: Mapped[int] = mapped_column(Integer)  # which choice they got (1 = first)
    response: Mapped[str] = mapped_column(String(10), default="pending")
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reminded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cycle: Mapped[SwapCycle] = relationship(back_populates="members")
    request: Mapped[SwapRequest] = relationship()
    gives_seat: Mapped[Seat] = relationship(foreign_keys=[gives_seat_id])
    receives_seat: Mapped[Seat] = relationship(foreign_keys=[receives_seat_id])


class Event(Base):
    """Audit log: feeds the student's event stream and the admin log."""

    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    kind: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(300))
    student_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    cycle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("swap_cycles.id"), nullable=True)


# ---------------------------------------------------------------- staff tools
class Email(Base):
    """Outbox. Mail is queued here first; it is "sent" only once a mail server took it."""

    __tablename__ = "emails"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    kind: Mapped[str] = mapped_column(String(30))  # match_found / deadline_reminder / slot_match_found ...
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_address: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="queued")  # queued / sent
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Schedule(Base):
    """One row: when the next automatic matching round runs."""

    __tablename__ = "schedule"
    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    every_hours: Mapped[int] = mapped_column(Integer, default=24)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    set_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("match_runs.id"), nullable=True)
    set_by: Mapped[Optional[User]] = relationship()


# ---------------------------------------------------------------- faculty lecture slots
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


class LectureSlot(Base):
    """One weekly lecture: a time and a hall, taught by its owner.

    A swap moves teachers (with their course) between slots; the time and hall stay.
    """

    __tablename__ = "lecture_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[int] = mapped_column(Integer)  # 0 = Monday
    start_min: Mapped[int] = mapped_column(Integer)  # minutes after midnight
    length_min: Mapped[int] = mapped_column(Integer, default=50)
    hall: Mapped[str] = mapped_column(String(12))
    course_code: Mapped[str] = mapped_column(String(10))
    course_name: Mapped[str] = mapped_column(String(80))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped[Faculty] = relationship(back_populates="slots")

    @property
    def end_min(self) -> int:
        return self.start_min + self.length_min

    @property
    def time_label(self) -> str:
        def hhmm(m: int) -> str:
            return f"{m // 60:02d}:{m % 60:02d}"
        return f"{DAYS[self.day]} {hhmm(self.start_min)}-{hhmm(self.end_min)}"

    @property
    def label(self) -> str:
        return f"{self.time_label} · {self.hall}"

    def clashes_with(self, other: "LectureSlot") -> bool:
        return self.day == other.day and self.start_min < other.end_min and other.start_min < self.end_min


class SlotRequest(Base):
    __tablename__ = "slot_requests"
    __table_args__ = (one_active_per("slot_requests", "faculty_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tracking_id: Mapped[Optional[str]] = mapped_column(String(16), unique=True, nullable=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("lecture_slots.id"))  # the slot offered
    status: Mapped[str] = mapped_column(String(10))  # open / matched / completed / withdrawn
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    faculty: Mapped[Faculty] = relationship()
    slot: Mapped[LectureSlot] = relationship()
    preferences: Mapped[list["SlotPreference"]] = relationship(
        back_populates="request", order_by="SlotPreference.rank", cascade="all, delete-orphan"
    )


class SlotPreference(Base):
    __tablename__ = "slot_preferences"
    __table_args__ = (UniqueConstraint("request_id", "rank"), UniqueConstraint("request_id", "slot_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("slot_requests.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer)
    slot_id: Mapped[int] = mapped_column(ForeignKey("lecture_slots.id"))
    request: Mapped[SlotRequest] = relationship(back_populates="preferences")
    slot: Mapped[LectureSlot] = relationship()


class SlotCycle(Base):
    __tablename__ = "slot_cycles"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id"))
    status: Mapped[str] = mapped_column(String(10))  # proposed / confirmed / approved / dissolved
    deadline: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[Optional[User]] = relationship()
    members: Mapped[list["SlotCycleMember"]] = relationship(back_populates="cycle", order_by="SlotCycleMember.position")


class SlotCycleMember(Base):
    __tablename__ = "slot_cycle_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("slot_cycles.id"))
    request_id: Mapped[int] = mapped_column(ForeignKey("slot_requests.id"))
    position: Mapped[int] = mapped_column(Integer)
    gives_slot_id: Mapped[int] = mapped_column(ForeignKey("lecture_slots.id"))
    receives_slot_id: Mapped[int] = mapped_column(ForeignKey("lecture_slots.id"))
    received_rank: Mapped[int] = mapped_column(Integer)
    response: Mapped[str] = mapped_column(String(10), default="pending")
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cycle: Mapped[SlotCycle] = relationship(back_populates="members")
    request: Mapped[SlotRequest] = relationship()
    gives_slot: Mapped[LectureSlot] = relationship(foreign_keys=[gives_slot_id])
    receives_slot: Mapped[LectureSlot] = relationship(foreign_keys=[receives_slot_id])
