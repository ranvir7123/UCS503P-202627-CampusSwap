import pytest
from fastapi.testclient import TestClient

from app.deps import get_now
from app.main import create_app
from conftest import NOW
from seed import DEMO_PASSWORD, seed


@pytest.fixture
def client(tmp_path):
    (tmp_path / "index.html").write_text("<title>CampusSwap</title>", encoding="utf-8")
    app = create_app("sqlite://", frontend_dir=tmp_path)
    with app.state.session_factory() as db:
        seed(db, now=NOW)
    app.dependency_overrides[get_now] = lambda: NOW
    with TestClient(app) as c:
        yield c


def login(client, email, role="student", password=DEMO_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password, "role": role})


def room_id(client, number, hostel="M"):
    rooms = client.get("/api/rooms").json()["rooms"]
    return next(r["id"] for r in rooms if r["number"] == number and r["hostel"]["code"] == hostel)


def test_login_sets_session_cookie_and_me_works(client):
    r = login(client, "student1@thapar.edu")
    assert r.status_code == 200 and "cs_session" in r.cookies
    me = client.get("/api/auth/me").json()
    assert me["role"] == "student" and me["email"] == "student1@thapar.edu"


def test_status_answers_without_error_when_logged_out(client):
    assert client.get("/api/auth/status").json() == {"user": None}
    login(client, "student1@thapar.edu")
    assert client.get("/api/auth/status").json()["user"]["role"] == "student"


def test_wrong_password_is_rejected(client):
    r = login(client, "student1@thapar.edu", password="nope")
    assert r.status_code == 401 and r.json()["error"] == "bad_credentials"


def test_unknown_email_gets_the_same_answer(client):
    r = login(client, "ghost@thapar.edu")
    assert r.status_code == 401 and r.json()["error"] == "bad_credentials"


def test_student_using_staff_tab_is_told_to_switch(client):
    r = login(client, "student1@thapar.edu", role="admin")
    assert r.status_code == 403 and r.json()["error"] == "wrong_role"


def test_pages_need_login(client):
    r = client.get("/api/me/dashboard")
    assert r.status_code == 401 and r.json()["error"] == "not_logged_in"


def test_student_cannot_use_admin_routes(client):
    login(client, "student1@thapar.edu")
    r = client.get("/api/admin/overview")
    assert r.status_code == 403 and r.json()["error"] == "forbidden"


def test_logout_ends_the_session(client):
    login(client, "student1@thapar.edu")
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_bad_input_gets_a_readable_error(client):
    login(client, "student1@thapar.edu")
    r = client.post("/api/requests", json={"room_ids": "not a list"})
    assert r.status_code == 422 and r.json()["error"] == "invalid_input"


def test_rule_errors_come_back_as_json(client):
    login(client, "student1@thapar.edu")
    r = client.post("/api/requests", json={"room_ids": []})
    assert r.status_code == 400 and r.json() == {"error": "empty_list", "message": "Pick at least one room."}


def test_full_swap_story_over_http(client):
    # three demo students form a 3-way chain in Hostel M
    wants = {1: "B-101", 2: "A-201", 3: "A-101"}
    for n, number in wants.items():
        login(client, f"student{n}@thapar.edu")
        r = client.post("/api/requests", json={"room_ids": [room_id(client, number)]})
        assert r.status_code == 201, r.text

    login(client, "warden@thapar.edu", role="admin")
    compare = client.post("/api/admin/compare").json()
    assert compare["ttc"]["matched"] == 12 and compare["pairwise"]["matched"] == 2
    run = client.post("/api/admin/match-runs", json={"algorithm": "ttc", "dry_run": False}).json()
    assert run["pool_size"] == 15 and run["matched"] == 12

    cycle_id = None
    for n in wants:
        login(client, f"student{n}@thapar.edu")
        dash = client.get("/api/me/dashboard").json()
        cycle_id = dash["cycle"]["id"]
        assert client.post(f"/api/cycles/{cycle_id}/accept").status_code == 200

    login(client, "warden@thapar.edu", role="admin")
    assert client.post(f"/api/admin/cycles/{cycle_id}/approve").status_code == 200
    csv_response = client.get("/api/admin/export.csv")
    assert csv_response.headers["content-type"].startswith("text/csv")

    login(client, "student1@thapar.edu")
    dash = client.get("/api/me/dashboard").json()
    assert dash["request"]["status"] == "completed"
    assert dash["room"]["number"] == "B-101"


def test_withdraw_over_http(client):
    login(client, "student1@thapar.edu")
    client.post("/api/requests", json={"room_ids": [room_id(client, "B-101")]})
    assert client.delete("/api/requests/current").json()["status"] == "withdrawn"


def test_public_stats_need_no_login(client):
    assert client.get("/api/public/stats").json()["open_requests"] == 12


def test_home_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "CampusSwap" in r.text


def test_pages_tell_browsers_to_check_for_updates(client):
    assert client.get("/").headers["cache-control"] == "no-cache"
