import csv
import io

from sqlalchemy import select

from app.models import Admin, Hostel, Room, Student, SwapCycle, SwapRequest
from app.services.cycles import accept, approve
from app.services.matching import compare_algorithms, run_matching
from app.services.requests import submit_request
from app.services.views import admin_overview, admin_requests, export_csv, public_stats, rooms_listing, student_dashboard
from conftest import NOW


def student(db, email):
    return db.scalar(select(Student).where(Student.email == email))


def owner_of(db, code, number):
    room = db.scalar(select(Room).join(Hostel).where(Hostel.code == code, Room.number == number))
    return room.seats[0].occupant


def run(db):
    return run_matching(db, db.scalar(select(Admin)), "ttc", dry_run=False, now=NOW)


def test_public_stats_show_real_counts(seeded):
    stats = public_stats(seeded, NOW)
    assert stats["open_requests"] == 12
    assert stats["hostels"] == 4
    assert len(stats["requests_per_day"]) == 7 and sum(stats["requests_per_day"]) == 12
    assert stats["last_run"] is None


def test_rooms_listing_only_shows_own_gender_hostels(seeded):
    listing = rooms_listing(seeded, student(seeded, "student1@thapar.edu"))
    assert {h["code"] for h in listing["hostels"]} == {"J", "M"}
    rooms = {(r["hostel"]["code"], r["number"]): r for r in listing["rooms"]}
    assert rooms[("M", "A-101")]["is_own"] is True
    assert rooms[("J", "A-101")]["open_to_swap"] == 1
    assert rooms[("M", "B-101")]["open_to_swap"] == 0
    assert rooms[("J", "A-102")]["seater"] == 2


def test_dashboard_without_request(seeded):
    d = student_dashboard(seeded, student(seeded, "student1@thapar.edu"), NOW)
    assert d["request"] is None and d["cycle"] is None
    assert d["room"]["number"] == "A-101"
    assert [m["state"] for m in d["milestones"]][:2] == ["current", "todo"]


def test_dashboard_with_open_request(seeded):
    s1 = student(seeded, "student1@thapar.edu")
    b101 = seeded.scalar(select(Room).join(Hostel).where(Hostel.code == "M", Room.number == "B-101"))
    submit_request(seeded, s1, [b101.id], NOW)
    d = student_dashboard(seeded, s1, NOW)
    assert d["request"]["status"] == "open"
    assert d["request"]["preferences"][0]["room"]["number"] == "B-101"
    assert [m["state"] for m in d["milestones"]][:3] == ["done", "current", "todo"]


def test_dashboard_shows_the_swap_chain_after_matching(seeded):
    run(seeded)
    me = owner_of(seeded, "J", "A-101")
    d = student_dashboard(seeded, me, NOW)
    cycle = d["cycle"]
    assert cycle["length"] == 2 and cycle["status"] == "proposed"
    assert sum(1 for m in cycle["members"] if m["is_me"]) == 1
    assert cycle["receive_room"]["number"] == "B-101"
    assert cycle["deadline"].endswith("Z")
    assert d["events"][0]["kind"] == "match_found"


def test_dashboard_after_approval_shows_new_room(seeded):
    run(seeded)
    me = owner_of(seeded, "J", "A-101")
    cycle = next(c for c in seeded.scalars(select(SwapCycle)).all() if len(c.members) == 2)
    for m in cycle.members:
        accept(seeded, m.request.student, cycle.id, NOW)
    approve(seeded, seeded.scalar(select(Admin)), cycle.id, NOW)
    d = student_dashboard(seeded, me, NOW)
    assert d["room"]["number"] == "B-101"
    assert d["request"]["status"] == "completed"
    assert all(m["state"] == "done" for m in d["milestones"])


def test_admin_overview_reflects_latest_run(seeded):
    compare_algorithms(seeded, seeded.scalar(select(Admin)), NOW)  # both on the full pool of 12
    run(seeded)
    o = admin_overview(seeded)
    assert o["open"] == 3 and o["matched"] == 9
    assert o["latest"]["yield_pct"] == 75.0
    assert o["latest"]["cycles_by_length"] == {"2": 1, "3": 1, "4": 1}
    assert o["comparison"] == {"ttc": 75.0, "pairwise": 16.7}
    assert "Chain found" in o["trace"]



def test_room_trace_ignores_a_later_lecture_slot_round(seeded):
    from app.services import slots
    room_run = run(seeded)
    slots.run_round(seeded, seeded.scalar(select(Admin)), dry_run=True, now=NOW)
    o = admin_overview(seeded)
    assert o["trace_run"]["id"] == room_run.id
    assert o["trace"] == room_run.trace

def test_admin_requests_rows(seeded):
    run(seeded)
    rows = admin_requests(seeded)
    assert len(rows) == 12
    matched = [r for r in rows if r["status"] == "matched"]
    assert len(matched) == 9
    assert all(r["assigned_room"] and r["cycle"]["length"] in (2, 3, 4) for r in matched)


def test_export_csv_has_header_and_one_row_per_request(seeded):
    run(seeded)
    rows = list(csv.reader(io.StringIO(export_csv(seeded))))
    assert rows[0][:3] == ["tracking_id", "student", "roll_no"]
    assert len(rows) == 1 + seeded.query(SwapRequest).count()
