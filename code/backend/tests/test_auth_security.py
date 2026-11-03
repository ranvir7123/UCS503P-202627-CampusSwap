"""Server-side sign-in rules: institute email only, attempt limit, HTTPS mode."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.deps import get_now
from app.main import create_app
from conftest import NOW
from seed import DEMO_PASSWORD, seed


def make_client(tmp_path, clock, **app_options):
    (tmp_path / "index.html").write_text("<title>CampusSwap</title>", encoding="utf-8")
    app = create_app("sqlite://", frontend_dir=tmp_path, **app_options)
    with app.state.session_factory() as db:
        seed(db, now=NOW)
    app.dependency_overrides[get_now] = lambda: clock["now"]
    return TestClient(app, **({"base_url": "https://testserver"} if app_options.get("secure") else {}))


@pytest.fixture
def clock():
    return {"now": NOW}


@pytest.fixture
def client(tmp_path, clock):
    with make_client(tmp_path, clock) as c:
        yield c


def login(client, email, password=DEMO_PASSWORD, role="student"):
    return client.post("/api/auth/login", json={"email": email, "password": password, "role": role})


# ---------------------------------------------------------------- FR-AUTH-09
def test_server_refuses_non_institute_email(client):
    r = login(client, "someone@gmail.com")
    assert r.status_code == 400 and r.json()["error"] == "not_institute_email"


def test_lookalike_domain_is_refused(client):
    r = login(client, "student1@thapar.edu.evil.com")
    assert r.status_code == 400 and r.json()["error"] == "not_institute_email"


def test_institute_email_in_capitals_is_accepted(client):
    assert login(client, "  Student1@THAPAR.EDU ").status_code == 200


# ---------------------------------------------------------------- FR-AUTH-10
def test_five_wrong_passwords_lock_that_email(client):
    for _ in range(5):
        assert login(client, "student1@thapar.edu", password="wrong").status_code == 401
    r = login(client, "student1@thapar.edu")  # even the right password is refused now
    assert r.status_code == 429 and r.json()["error"] == "too_many_attempts"
    assert "minute" in r.json()["message"]


def test_lock_lifts_after_fifteen_minutes(client, clock):
    for _ in range(5):
        login(client, "student1@thapar.edu", password="wrong")
    clock["now"] = NOW + timedelta(minutes=15, seconds=1)
    assert login(client, "student1@thapar.edu").status_code == 200


def test_lock_on_one_email_does_not_block_another(client):
    for _ in range(5):
        login(client, "student1@thapar.edu", password="wrong")
    assert login(client, "student2@thapar.edu").status_code == 200


def test_successful_sign_in_clears_earlier_failures(client):
    for _ in range(4):
        login(client, "student1@thapar.edu", password="wrong")
    assert login(client, "student1@thapar.edu").status_code == 200
    for _ in range(4):
        login(client, "student1@thapar.edu", password="wrong")
    assert login(client, "student1@thapar.edu").status_code == 200


def test_unknown_emails_are_limited_too(client):
    for _ in range(5):
        assert login(client, "ghost@thapar.edu").status_code == 401
    assert login(client, "ghost@thapar.edu").status_code == 429


def test_many_failures_from_one_address_block_that_address(client):
    for n in range(20):
        login(client, f"nobody{n}@thapar.edu", password="wrong")
    r = login(client, "student1@thapar.edu")
    assert r.status_code == 429 and r.json()["error"] == "too_many_attempts"


# ---------------------------------------------------------------- NFR-SEC-07
def test_local_mode_cookie_is_not_secure(client):
    r = login(client, "student1@thapar.edu")
    assert "secure" not in r.headers["set-cookie"].lower()


def test_secure_mode_marks_cookie_secure_and_sends_hsts(tmp_path, clock):
    with make_client(tmp_path, clock, secure=True) as c:
        r = login(c, "student1@thapar.edu")
        assert r.status_code == 200
        assert "secure" in r.headers["set-cookie"].lower()
        assert "max-age" in r.headers["strict-transport-security"]


def test_secure_mode_redirects_plain_http_to_https(tmp_path, clock):
    with make_client(tmp_path, clock, secure=True) as c:
        r = c.get("http://testserver/api/public/stats", follow_redirects=False)
        assert r.status_code in (307, 308) and r.headers["location"].startswith("https://")


# ---------------------------------------------------------------- lockout cannot be used against someone else
def test_failures_from_another_address_do_not_lock_the_owner(seeded):
    from app.errors import DomainError
    from app.services import signin

    for _ in range(5):
        signin.record_failure(seeded, "student1@thapar.edu", "6.6.6.6", NOW)
    with pytest.raises(DomainError):
        signin.check_not_blocked(seeded, "student1@thapar.edu", "6.6.6.6", NOW)
    signin.check_not_blocked(seeded, "student1@thapar.edu", "10.0.0.7", NOW)  # the real owner is not blocked


def test_guessing_spread_over_many_addresses_is_still_capped(seeded):
    from app.errors import DomainError
    from app.services import signin

    for n in range(50):
        signin.record_failure(seeded, "student1@thapar.edu", f"10.1.{n}.1", NOW)
    with pytest.raises(DomainError) as err:
        signin.check_not_blocked(seeded, "student1@thapar.edu", "10.9.9.9", NOW)
    assert err.value.code == "too_many_attempts"


def test_unknown_address_does_not_share_one_bucket(seeded):
    from app.services import signin

    for n in range(20):
        signin.record_failure(seeded, f"nobody{n}@thapar.edu", None, NOW)
    signin.check_not_blocked(seeded, "student1@thapar.edu", None, NOW)  # other emails are not blocked


def test_ipv6_addresses_in_one_block_count_together(seeded):
    from app.errors import DomainError
    from app.services import signin

    for n in range(5):
        signin.record_failure(seeded, "student1@thapar.edu", f"2a01:4f8:1:2::{n + 1}", NOW)
    with pytest.raises(DomainError):
        signin.check_not_blocked(seeded, "student1@thapar.edu", "2a01:4f8:1:2::ffff", NOW)
    signin.check_not_blocked(seeded, "student1@thapar.edu", "2a01:4f8:9:9::1", NOW)


def test_ipv4_clients_seen_as_mapped_ipv6_stay_separate(seeded):
    from app.services import signin

    for n in range(20):
        signin.record_failure(seeded, f"nobody{n}@thapar.edu", "::ffff:203.0.113.9", NOW)
    signin.check_not_blocked(seeded, "student1@thapar.edu", "::ffff:198.51.100.4", NOW)  # a different person
