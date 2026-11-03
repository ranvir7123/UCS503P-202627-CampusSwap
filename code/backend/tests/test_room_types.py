"""FR-ROOM-07: a student may rank a room type ("any single AC room on floor 1") instead of one room."""
import pytest
from sqlalchemy import select

from app.errors import DomainError
from app.models import Admin, Hostel, Room, Student
from app.services.matching import run_matching
from app.services.requests import submit_request
from app.services.views import admin_requests, student_dashboard
from conftest import NOW


def room(db, code, number):
    return db.scalar(select(Room).join(Hostel).where(Hostel.code == code, Room.number == number))


def student(db, n):
    return db.scalar(select(Student).where(Student.email == f"student{n}@thapar.edu"))


def owner(db, code, number):
    return room(db, code, number).seats[0].occupant


def test_type_choice_is_saved_with_a_readable_label(seeded):
    req = submit_request(seeded, student(seeded, 1), [{"hostel": "M", "seater": 1, "ac": True, "floor": 1}], NOW)
    pref = req.preferences[0]
    assert pref.room_id is None and pref.rank == 1
    assert pref.label == "Any 1-seater AC room in Hostel M, floor 1"


def test_type_and_room_choices_can_be_mixed(seeded):
    b101 = room(seeded, "M", "B-101").id
    req = submit_request(seeded, student(seeded, 1), [b101, {"hostel": "M", "seater": 2}], NOW)
    assert [p.rank for p in req.preferences] == [1, 2]
    assert req.preferences[0].room_id == b101
    assert req.preferences[1].label == "Any 2-seater room in Hostel M"


def test_type_with_no_filters_means_any_room_in_that_hostel(seeded):
    req = submit_request(seeded, student(seeded, 1), [{"hostel": "M"}], NOW)
    assert req.preferences[0].label == "Any room in Hostel M"


def test_type_matching_no_room_is_rejected(seeded):
    # pick a seater / AC / floor combination that no room in Hostel M has
    m_rooms = seeded.scalars(select(Room).join(Hostel).where(Hostel.code == "M")).all()
    taken = {(r.seater, r.ac, r.floor) for r in m_rooms}
    combo = next((s, ac, f) for s in (1, 2, 3) for ac in (True, False) for f in (1, 2, 3)
                 if (s, ac, f) not in taken)
    with pytest.raises(DomainError) as err:
        submit_request(seeded, student(seeded, 1), [{"hostel": "M", "seater": combo[0], "ac": combo[1],
                                                     "floor": combo[2]}], NOW)
    assert err.value.code == "empty_type"


def test_type_in_hostel_of_other_gender_is_rejected(seeded):
    with pytest.raises(DomainError) as err:
        submit_request(seeded, student(seeded, 1), [{"hostel": "K"}], NOW)
    assert err.value.code == "wrong_hostel_gender"


def test_unknown_hostel_is_rejected(seeded):
    with pytest.raises(DomainError) as err:
        submit_request(seeded, student(seeded, 1), [{"hostel": "Z"}], NOW)
    assert err.value.code == "unknown_hostel"


def test_same_type_twice_is_rejected(seeded):
    with pytest.raises(DomainError) as err:
        submit_request(seeded, student(seeded, 1), [{"hostel": "M", "seater": 1}, {"hostel": "M", "seater": 1}], NOW)
    assert err.value.code == "duplicate_room"


def test_type_choice_finds_a_swap_chain(seeded):
    # student1 (M A-101) wants any 1-seater on floor 1 -> only B-101 qualifies (A-101 is their own).
    # student2 (M B-101) wants A-101. TTC must find the 2-way swap.
    s1, s2 = student(seeded, 1), student(seeded, 2)
    submit_request(seeded, s1, [{"hostel": "M", "seater": 1, "floor": 1}], NOW)
    submit_request(seeded, s2, [room(seeded, "M", "A-101").id], NOW)
    run = run_matching(seeded, seeded.scalar(select(Admin)), "ttc", dry_run=False, now=NOW)
    assert run.cycles_by_length.get("2", 0) >= 2  # the seeded 2-way plus ours
    dash = student_dashboard(seeded, s1, NOW)
    assert dash["cycle"]["receive_room"]["number"] == "B-101"
    assert dash["cycle"]["received_rank"] == 1


def test_received_rank_is_the_first_choice_that_matches(seeded):
    s1, s2 = student(seeded, 1), student(seeded, 2)
    a201 = room(seeded, "M", "A-201").id  # nobody offers it
    submit_request(seeded, s1, [a201, {"hostel": "M", "seater": 1, "floor": 1}], NOW)
    submit_request(seeded, s2, [room(seeded, "M", "A-101").id], NOW)
    run_matching(seeded, seeded.scalar(select(Admin)), "ttc", dry_run=False, now=NOW)
    assert student_dashboard(seeded, s1, NOW)["cycle"]["received_rank"] == 2


def test_dashboard_and_staff_list_show_type_labels(seeded):
    s1 = student(seeded, 1)
    submit_request(seeded, s1, [{"hostel": "M", "ac": True}], NOW)
    prefs = student_dashboard(seeded, s1, NOW)["request"]["preferences"]
    assert prefs[0]["kind"] == "type" and prefs[0]["label"] == "Any AC room in Hostel M"
    assert prefs[0]["room"] is None
    row = next(r for r in admin_requests(seeded) if r["student"]["name"] == s1.name)
    assert row["preferences"] == ["Any AC room in Hostel M"]


def test_api_accepts_choices_body(seeded_client):
    c, room_id = seeded_client
    r = c.post("/api/requests", json={"choices": [{"room_id": room_id("B-101")},
                                                  {"type": {"hostel": "M", "seater": 2, "ac": None}}]})
    assert r.status_code == 201
    prefs = c.get("/api/me/dashboard").json()["request"]["preferences"]
    assert [p["kind"] for p in prefs] == ["room", "type"]


def test_api_rejects_choice_with_both_room_and_type(seeded_client):
    c, room_id = seeded_client
    r = c.post("/api/requests", json={"choices": [{"room_id": room_id("B-101"), "type": {"hostel": "M"}}]})
    assert r.status_code == 422 and r.json()["error"] == "invalid_input"


@pytest.fixture
def seeded_client(tmp_path):
    from fastapi.testclient import TestClient

    from app.deps import get_now
    from app.main import create_app
    from seed import DEMO_PASSWORD, seed

    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    app = create_app("sqlite://", frontend_dir=tmp_path)
    with app.state.session_factory() as db:
        seed(db, now=NOW)
    app.dependency_overrides[get_now] = lambda: NOW
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"email": "student1@thapar.edu", "password": DEMO_PASSWORD, "role": "student"})
        rooms = c.get("/api/rooms").json()["rooms"]

        def room_id(number):
            return next(r["id"] for r in rooms if r["number"] == number and r["hostel"]["code"] == "M")

        yield c, room_id
