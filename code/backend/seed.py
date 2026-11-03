"""Synthetic demo data for CampusSwap.

Everything here is made up (hostels, names, roll numbers, emails) so it can
never be mistaken for real student records.

Demo logins (password for all: campus123):
  warden@thapar.edu                      admin
  student1@thapar.edu .. student3@thapar.edu   students with no request yet,
      living in single rooms Hostel M A-101, B-101, A-201. For a live 3-way
      swap: student1 ranks B-101, student2 ranks A-201, student3 ranks A-101.

The pre-built pool is designed so TTC finds one 2-way, one 3-way and one
4-way chain, and leaves 3 students unmatched.

Faculty (lecture slot exchange), same password:
  faculty1@thapar.edu .. faculty3@thapar.edu   no request yet. For a live
      2-way slot swap: faculty1 offers UCS503 (Mon 08:00) and ranks UCS301;
      faculty2 offers UCS301 (Tue 10:00) and ranks UCS503.
  The pre-built slot pool gives one 3-way chain and leaves 1 teacher unmatched.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.models import Admin, Faculty, Hostel, LectureSlot, Room, Seat, Student
from app.security import hash_password

DEMO_PASSWORD = "campus123"

HOSTELS = [
    ("J", "Hostel J", "M", "Dr. A. Verma"),
    ("M", "Hostel M", "M", "Dr. R. Singh"),
    ("K", "Hostel K", "F", "Dr. P. Kaur"),
    ("N", "Hostel N", "F", "Dr. S. Mehta"),
]
TAGS = ["Near mess", "Lift nearby", "Corner room", "Balcony", "Quiet wing", "Garden facing"]
FIRST_M = ["Aarav", "Vihaan", "Kabir", "Arjun", "Rohan", "Ishaan", "Dev", "Karan", "Yash", "Aditya"]
FIRST_F = ["Ananya", "Diya", "Isha", "Meera", "Riya", "Saanvi", "Tara", "Kavya", "Nisha", "Pooja"]
SURNAMES = ["Sharma", "Gill", "Mehta", "Bansal", "Kapoor", "Sethi", "Arora", "Malhotra", "Sandhu", "Jain"]
BRANCHES = ["COE", "ECE", "ME", "EE", "CSBS", "BT"]

# (owner's hostel, room, [ranked wanted rooms in the same hostel])
POOL = [
    # 2-way: J A-101 <-> J B-101
    ("J", "A-101", ["B-101", "A-201"]),
    ("J", "B-101", ["A-101"]),
    # 3-way: J A-201 -> J B-201 -> J A-301 -> J A-201
    ("J", "A-201", ["B-201", "B-101"]),
    ("J", "B-201", ["A-301"]),
    ("J", "A-301", ["A-201", "A-101"]),
    # 4-way: K A-101 -> K B-101 -> K A-201 -> K B-201 -> K A-101
    ("K", "A-101", ["B-101"]),
    ("K", "B-101", ["A-201", "A-301"]),
    ("K", "A-201", ["B-201"]),
    ("K", "B-201", ["A-101"]),
    # unmatched: their choices are taken by others first, or nobody offers them
    ("J", "B-301", ["A-101", "B-101"]),
    ("J", "A-102", ["A-101"]),
    ("K", "A-301", ["B-301"]),
]
DEMO_STUDENT_ROOMS = ["A-101", "B-101", "A-201"]  # in Hostel M

FACULTY = [
    ("faculty1@thapar.edu", "Dr. Neha Arora", "CSED"),
    ("faculty2@thapar.edu", "Dr. Vikram Sood", "CSED"),
    ("faculty3@thapar.edu", "Dr. Kiran Walia", "ECED"),
    ("fac004@thapar.edu", "Dr. Amit Chawla", "CSED"),
    ("fac005@thapar.edu", "Dr. Ritu Bhalla", "ECED"),
    ("fac006@thapar.edu", "Dr. Sanjay Grover", "MED"),
    ("fac007@thapar.edu", "Dr. Meenakshi Rao", "CSED"),
    ("fac008@thapar.edu", "Dr. Harpreet Dhillon", "EIED"),
]
# (teacher index, course code, course name, day 0=Mon, start "HH:MM", hall)
LECTURES = [
    (0, "UCS503", "Software Engineering", 0, "08:00", "LT-101"),
    (0, "UCS414", "Computer Networks", 2, "14:00", "LT-102"),
    (1, "UCS301", "Data Structures", 1, "10:00", "LT-103"),
    (1, "UCS310", "Database Management Systems", 3, "11:00", "LT-101"),
    (2, "UEC401", "Analog Circuits", 4, "09:00", "LT-104"),
    (2, "UEC510", "Digital Signal Processing", 0, "15:00", "LT-102"),
    (3, "UCS520", "Machine Learning", 0, "10:00", "LT-101"),
    (3, "UCS615", "Image Processing", 3, "15:00", "LT-103"),
    (4, "UEC612", "VLSI Design", 1, "14:00", "LT-104"),
    (4, "UEC301", "Signals and Systems", 4, "11:00", "LT-101"),
    (5, "UME410", "Thermodynamics", 2, "09:00", "LT-102"),
    (5, "UME513", "Machine Design", 4, "15:00", "LT-103"),
    (6, "UCS701", "Cloud Computing", 1, "09:00", "LT-101"),
    (6, "UCS420", "Cognitive Computing", 3, "09:00", "LT-102"),
    (7, "UEI501", "Control Systems", 2, "11:00", "LT-103"),
    (7, "UEI610", "Robotics", 2, "14:00", "LT-104"),
]
# (course offered, [courses whose slots are wanted, best first])
SLOT_POOL = [
    # 3-way: UCS520 slot -> UCS701 slot -> UEI501 slot -> UCS520 slot
    ("UCS520", ["UCS701"]),
    ("UCS701", ["UEI501"]),
    ("UEI501", ["UCS520"]),
    # unmatched: nobody offers the slot wanted
    ("UEC612", ["UME513"]),
]


def seed(db: Session, now: datetime | None = None) -> None:
    from app.services.requests import submit_request

    now = now or utcnow()
    password_hash = hash_password(DEMO_PASSWORD)  # one hash reused: demo data only
    db.add(Admin(email="warden@thapar.edu", name="Warden Office", password_hash=password_hash))

    counter = itertools.count(1)
    for code, name, gender, warden in HOSTELS:
        hostel = Hostel(code=code, name=name, gender=gender, warden_name=warden)
        db.add(hostel)
        for block, floor, i in itertools.product("AB", (1, 2, 3), (1, 2, 3)):
            seater = i  # room 1 single, room 2 double, room 3 triple on each floor
            n = next(counter)
            room = Room(
                hostel=hostel, block=block, floor=floor, number=f"{block}-{floor}0{i}",
                seater=seater, ac=(n % 3 != 0), washroom="attached" if seater == 1 else "common",
                tags=", ".join(TAGS[(n + k) % len(TAGS)] for k in range(2)),
            )
            db.add(room)
            for label in "ABC"[:seater]:
                db.add(Seat(room=room, label=label))
    db.flush()

    # one student per seat, in a stable order
    seats = db.scalars(select(Seat).join(Room).join(Hostel).order_by(Hostel.id, Room.id, Seat.id)).all()
    demo_emails = {("M", number): f"student{n}@thapar.edu" for n, number in enumerate(DEMO_STUDENT_ROOMS, start=1)}
    for k, seat in enumerate(seats, start=1):
        hostel = seat.room.hostel
        firsts = FIRST_M if hostel.gender == "M" else FIRST_F
        first, last = firsts[k % len(firsts)], SURNAMES[(k // len(firsts)) % len(SURNAMES)]
        email = demo_emails.get((hostel.code, seat.room.number), f"stu{k:03d}@thapar.edu")
        seat.occupant = Student(
            email=email, name=f"{first} {last}", password_hash=password_hash,
            roll_no=f"D24{k:04d}", gender=hostel.gender, year=1 + k % 4, branch=BRANCHES[k % len(BRANCHES)],
        )
    db.flush()

    _seed_faculty(db, password_hash, now)

    def room(code: str, number: str) -> Room:
        return db.scalar(select(Room).join(Hostel).where(Hostel.code == code, Room.number == number))

    for offset, (code, number, wanted) in enumerate(POOL):
        owner = room(code, number).seats[0].occupant
        submit_request(db, owner, [room(code, w).id for w in wanted], now - timedelta(hours=len(POOL) - offset))
    db.commit()



def _seed_faculty(db: Session, password_hash: str, now: datetime) -> None:
    from app.services import slots

    teachers = [Faculty(email=e, name=n, department=d, password_hash=password_hash) for e, n, d in FACULTY]
    db.add_all(teachers)
    by_course = {}
    for who, code, name, day, start, hall in LECTURES:
        hours, minutes = map(int, start.split(":"))
        slot = LectureSlot(owner=teachers[who], course_code=code, course_name=name, day=day,
                           start_min=hours * 60 + minutes, length_min=50, hall=hall)
        db.add(slot)
        by_course[code] = slot
    db.flush()
    for offset, (offered, wanted) in enumerate(SLOT_POOL):
        slot = by_course[offered]
        slots.submit(db, slot.owner, slot.id, [by_course[w].id for w in wanted],
                     now - timedelta(hours=len(SLOT_POOL) - offset))

if __name__ == "__main__":
    from app.db import DEFAULT_DB_PATH, make_engine, make_session_factory
    from app.models import Base

    DEFAULT_DB_PATH.unlink(missing_ok=True)
    engine = make_engine()
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        seed(session)
    print(f"Seeded {DEFAULT_DB_PATH}")
