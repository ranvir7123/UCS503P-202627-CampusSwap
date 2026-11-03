"""FR-SLOT-01: faculty swap lecture slots using the same Top Trading Cycles engine."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.deps import get_now
from app.errors import DomainError
from app.main import create_app
from app.models import Admin, Email, Faculty, LectureSlot, SlotCycle, SlotRequest
from app.services import schedule, slots
from conftest import NOW
from seed import DEMO_PASSWORD, SLOT_POOL, seed


def admin(db):
    return db.scalar(select(Admin))


def faculty(db, email):
    return db.scalar(select(Faculty).where(Faculty.email == email))


def slot_of(db, course):
    return db.scalar(select(LectureSlot).where(LectureSlot.course_code == course))


def demo(db, n):
    return faculty(db, f"faculty{n}@thapar.edu")


def rejects(code, fn, *args):
    with pytest.raises(DomainError) as err:
        fn(*args)
    assert err.value.code == code


# ---------------------------------------------------------------- seed
def test_seed_has_faculty_with_slots_and_an_open_pool(seeded):
    f1 = demo(seeded, 1)
    assert f1 is not None and f1.role == "faculty" and len(f1.slots) == 2
    open_requests = seeded.scalars(select(SlotRequest).where(SlotRequest.status == "open")).all()
    assert len(open_requests) == len(SLOT_POOL)


def test_slot_label_reads_like_a_timetable(seeded):
    assert slot_of(seeded, "UCS503").label == "Mon 08:00-08:50 · LT-101"


# ---------------------------------------------------------------- submitting
def test_faculty_offers_a_slot_and_ranks_others(seeded):
    f1 = demo(seeded, 1)
    req = slots.submit(seeded, f1, slot_of(seeded, "UCS503").id, [slot_of(seeded, "UCS301").id], NOW)
    assert req.status == "open" and req.tracking_id.startswith("SL-2026-")
    assert [p.slot.course_code for p in req.preferences] == ["UCS301"]


def test_cannot_offer_someone_elses_slot(seeded):
    rejects("not_your_slot", slots.submit, seeded, demo(seeded, 1), slot_of(seeded, "UCS301").id,
            [slot_of(seeded, "UEC401").id], NOW)


def test_cannot_rank_your_own_slot(seeded):
    rejects("own_slot", slots.submit, seeded, demo(seeded, 1), slot_of(seeded, "UCS503").id,
            [slot_of(seeded, "UCS414").id], NOW)


def test_cannot_rank_a_slot_that_clashes_with_your_other_lecture(seeded):
    # faculty1 also teaches UCS414 on Wed 14:00; UME410 is Wed 09:00 (fine); add a clash on purpose:
    clash = slot_of(seeded, "UCS414")
    other = seeded.scalar(select(LectureSlot).where(LectureSlot.day == clash.day,
                                                    LectureSlot.start_min == clash.start_min,
                                                    LectureSlot.id != clash.id))
    assert other is not None, "seed should have a second Wed 14:00 slot to test clashes"
    rejects("slot_clash", slots.submit, seeded, demo(seeded, 1), slot_of(seeded, "UCS503").id, [other.id], NOW)


def test_empty_duplicate_unknown_and_too_many_are_rejected(seeded):
    f1, mine = demo(seeded, 1), slot_of(seeded, "UCS503").id
    rejects("empty_list", slots.submit, seeded, f1, mine, [], NOW)
    rejects("duplicate_slot", slots.submit, seeded, f1, mine, [slot_of(seeded, "UCS301").id] * 2, NOW)
    rejects("unknown_slot", slots.submit, seeded, f1, mine, [99999], NOW)
    many = seeded.scalars(select(LectureSlot.id).where(LectureSlot.owner_id != f1.id)).all()[:6]
    rejects("too_many", slots.submit, seeded, f1, mine, many, NOW)


def test_one_active_request_at_a_time_and_withdraw(seeded):
    f1 = demo(seeded, 1)
    slots.submit(seeded, f1, slot_of(seeded, "UCS503").id, [slot_of(seeded, "UCS301").id], NOW)
    rejects("already_active", slots.submit, seeded, f1, slot_of(seeded, "UCS414").id,
            [slot_of(seeded, "UCS301").id], NOW)
    assert slots.withdraw(seeded, f1, NOW).status == "withdrawn"
    rejects("no_request", slots.withdraw, seeded, f1, NOW)


# ---------------------------------------------------------------- matching
def test_seeded_slot_pool_gives_a_three_way_chain(seeded):
    run = slots.run_round(seeded, admin(seeded), dry_run=False, now=NOW)
    assert run.algorithm == "slot_ttc" and run.cycles_by_length == {"3": 1}
    assert (run.pool_size, run.matched) == (len(SLOT_POOL), 3)
    cycle = seeded.scalar(select(SlotCycle))
    for i, m in enumerate(cycle.members):
        assert m.receives_slot_id == cycle.members[(i + 1) % 3].gives_slot_id
    assert len(seeded.scalars(select(Email).where(Email.kind == "slot_match_found")).all()) == 3


def test_dry_run_changes_nothing(seeded):
    run = slots.run_round(seeded, admin(seeded), dry_run=True, now=NOW)
    assert run.matched == 3 and seeded.scalar(select(SlotCycle)) is None


def test_live_two_way_swap_between_demo_faculty_end_to_end(seeded):
    f1, f2 = demo(seeded, 1), demo(seeded, 2)
    se, ds = slot_of(seeded, "UCS503"), slot_of(seeded, "UCS301")
    slots.submit(seeded, f1, se.id, [ds.id], NOW)
    slots.submit(seeded, f2, ds.id, [se.id], NOW)
    slots.run_round(seeded, admin(seeded), dry_run=False, now=NOW)
    cycle = next(c for c in seeded.scalars(select(SlotCycle)) if len(c.members) == 2)
    slots.accept(seeded, f1, cycle.id, NOW)
    rejects("not_confirmed", slots.approve, seeded, admin(seeded), cycle.id, NOW)
    slots.accept(seeded, f2, cycle.id, NOW)
    assert cycle.status == "confirmed"
    slots.approve(seeded, admin(seeded), cycle.id, NOW)
    # the time and room stay; owner and course move with the teacher
    assert (se.owner_id, se.course_code) == (f2.id, "UCS301")
    assert (ds.owner_id, ds.course_code) == (f1.id, "UCS503")
    assert cycle.status == "approved" and cycle.approved_by.name == "Warden Office"


def test_decline_dissolves_and_others_go_back_to_the_pool(seeded):
    slots.run_round(seeded, admin(seeded), dry_run=False, now=NOW)
    cycle = seeded.scalar(select(SlotCycle))
    first, second = cycle.members[0], cycle.members[1]
    slots.decline(seeded, first.request.faculty, cycle.id, NOW)
    assert cycle.status == "dissolved"
    assert first.request.status == "withdrawn" and second.request.status == "open"


def test_non_member_cannot_answer(seeded):
    slots.run_round(seeded, admin(seeded), dry_run=False, now=NOW)
    cycle = seeded.scalar(select(SlotCycle))
    rejects("not_member", slots.accept, seeded, demo(seeded, 1), cycle.id, NOW)


def test_overdue_slot_chain_expires_in_the_tick(seeded):
    slots.run_round(seeded, admin(seeded), dry_run=False, now=NOW)
    schedule.tick(seeded, NOW + timedelta(hours=49), sender=None)
    assert seeded.scalar(select(SlotCycle)).status == "dissolved"


# ---------------------------------------------------------------- HTTP
@pytest.fixture
def app(tmp_path):
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    app = create_app("sqlite://", frontend_dir=tmp_path)
    with app.state.session_factory() as db:
        seed(db, now=NOW)
    app.dependency_overrides[get_now] = lambda: NOW
    return app


def signed_in(app, email, role):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD, "role": role})
    assert r.status_code == 200, r.text
    return c


def test_faculty_sign_in_and_home(app):
    with signed_in(app, "faculty1@thapar.edu", "faculty") as c:
        home = c.get("/api/faculty/home").json()
        assert home["me"]["name"] == "Dr. Neha Arora"
        assert len(home["my_slots"]) == 2 and home["request"] is None
        assert any(s["clashes"] for s in home["slots"])  # another Wed 14:00 lecture clashes
        assert all(not s["is_mine"] or not s["clashes"] for s in home["slots"])


def test_faculty_api_round_trip(app):
    with signed_in(app, "faculty1@thapar.edu", "faculty") as f1, \
            signed_in(app, "faculty2@thapar.edu", "faculty") as f2, \
            signed_in(app, "warden@thapar.edu", "admin") as staff:
        ids = {s["course_code"]: s["id"] for s in f1.get("/api/faculty/home").json()["slots"]}
        assert f1.post("/api/faculty/requests", json={"slot_id": ids["UCS503"], "wanted": [ids["UCS301"]]}).status_code == 201
        assert f2.post("/api/faculty/requests", json={"slot_id": ids["UCS301"], "wanted": [ids["UCS503"]]}).status_code == 201
        run = staff.post("/api/admin/slot-runs", json={"dry_run": False}).json()
        assert run["matched"] == 5 and "Chain found" in run["trace"]
        cycle_id = f1.get("/api/faculty/home").json()["cycle"]["id"]
        assert f1.post(f"/api/faculty/cycles/{cycle_id}/accept").status_code == 200
        assert f2.post(f"/api/faculty/cycles/{cycle_id}/accept").status_code == 200
        board = staff.get("/api/admin/slots").json()
        row = next(r for r in board["requests"] if r["cycle"] and r["cycle"]["id"] == cycle_id)
        assert row["cycle"]["can_approve"]
        assert staff.post(f"/api/admin/slot-cycles/{cycle_id}/approve").status_code == 200
        mine = {s["course_code"] for s in f1.get("/api/faculty/home").json()["my_slots"]}
        assert "UCS503" in mine  # still teaches the same course, now in the old UCS301 slot
        moved = next(s for s in f1.get("/api/faculty/home").json()["my_slots"] if s["course_code"] == "UCS503")
        assert moved["label"].startswith("Tue 10:00")


def test_students_cannot_reach_faculty_pages(app):
    with signed_in(app, "student1@thapar.edu", "student") as c:
        assert c.get("/api/faculty/home").status_code == 403
        assert c.post("/api/admin/slot-runs", json={"dry_run": True}).status_code == 403


def test_faculty_on_the_student_tab_is_told_to_switch(app):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "faculty1@thapar.edu", "password": DEMO_PASSWORD, "role": "student"})
    assert r.status_code == 403 and "Faculty" in r.json()["message"]
