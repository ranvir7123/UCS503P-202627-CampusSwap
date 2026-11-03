"""Staff tools: event log download (FR-TRACK-08), email notices (FR-CONF-06),
scheduled rounds (FR-MATCH-10) and the approval form PDF (FR-APPR-03)."""
import csv
import io
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import func, select

from app.deps import get_now
from app.errors import DomainError
from app.main import create_app
from app.models import Admin, Email, MatchRun, Student, SwapCycle
from app.services import cycles, mail, schedule
from app.services.matching import run_matching
from conftest import NOW
from seed import DEMO_PASSWORD, seed


def admin(db):
    return db.scalar(select(Admin))


def saved_round(db, now=NOW):
    return run_matching(db, admin(db), "ttc", dry_run=False, now=now)


def emails(db, kind=None):
    query = select(Email).order_by(Email.id)
    if kind:
        query = query.where(Email.kind == kind)
    return db.scalars(query).all()


def approve_first_cycle(db):
    cycle = db.scalars(select(SwapCycle).order_by(SwapCycle.id)).first()
    for m in cycle.members:
        cycles.accept(db, m.request.student, cycle.id, NOW)
    cycles.approve(db, admin(db), cycle.id, NOW + timedelta(hours=1))
    return cycle


# ---------------------------------------------------------------- FR-CONF-06 emails
def test_saved_round_queues_one_match_email_per_member(seeded):
    saved_round(seeded)
    sent = emails(seeded, "match_found")
    assert len(sent) == 9  # 2 + 3 + 4 members
    first = sent[0]
    assert first.to_address.endswith("@thapar.edu") and first.status == "queued"
    assert "swap" in first.subject.lower()
    assert "confirm" in first.body.lower() and "IST" in first.body


def test_dry_run_sends_no_email(seeded):
    run_matching(seeded, admin(seeded), "ttc", dry_run=True, now=NOW)
    assert emails(seeded) == []


def test_reminder_goes_once_to_members_who_have_not_answered(seeded):
    saved_round(seeded)
    cycle = seeded.scalars(select(SwapCycle).order_by(SwapCycle.id)).first()
    cycles.accept(seeded, cycle.members[0].request.student, cycle.id, NOW)
    assert mail.send_reminders(seeded, NOW + timedelta(hours=30)) == 0  # 18 h left: too early
    late = NOW + timedelta(hours=37)  # 11 h left
    reminded = mail.send_reminders(seeded, late)
    assert reminded == 9 - 1  # everyone pending, not the one who accepted
    assert mail.send_reminders(seeded, late + timedelta(hours=1)) == 0  # only once
    to = {e.to_user_id for e in emails(seeded, "deadline_reminder")}
    assert cycle.members[0].request.student_id not in to


def test_delivery_without_a_mail_server_keeps_mail_queued(seeded):
    saved_round(seeded)
    assert mail.deliver(seeded, NOW, sender=None) == 0
    assert {e.status for e in emails(seeded)} == {"queued"}


def test_delivery_with_a_sender_marks_mail_sent(seeded):
    saved_round(seeded)
    outbox = []
    assert mail.deliver(seeded, NOW, sender=lambda to, subject, body: outbox.append(to)) == 9
    assert len(outbox) == 9 and {e.status for e in emails(seeded)} == {"sent"}
    assert all(e.sent_at == NOW for e in emails(seeded))


def test_a_failing_send_is_recorded_and_retried_later(seeded):
    saved_round(seeded)

    def broken(to, subject, body):
        raise OSError("connection refused")

    assert mail.deliver(seeded, NOW, sender=broken) == 0
    first = emails(seeded)[0]
    assert first.status == "queued" and first.attempts == 1 and "connection refused" in first.error
    assert mail.deliver(seeded, NOW, sender=lambda *a: None) == 9


def test_smtp_sender_is_off_unless_configured(monkeypatch):
    monkeypatch.delenv("CAMPUSSWAP_SMTP_HOST", raising=False)
    assert mail.smtp_sender_from_env() is None
    monkeypatch.setenv("CAMPUSSWAP_SMTP_HOST", "smtp.example.org")
    assert callable(mail.smtp_sender_from_env())


# ---------------------------------------------------------------- FR-MATCH-10 schedule
def test_schedule_starts_switched_off(seeded):
    view = schedule.view(seeded)
    assert view["enabled"] is False and view["next_run_at"] is None


def test_turning_schedule_on_sets_the_next_run(seeded):
    schedule.update(seeded, admin(seeded), enabled=True, every_hours=24, now=NOW)
    view = schedule.view(seeded)
    assert view["enabled"] and view["every_hours"] == 24
    assert view["next_run_at"] == (NOW + timedelta(hours=24)).isoformat(timespec="seconds") + "Z"


def test_bad_interval_is_rejected(seeded):
    with pytest.raises(DomainError) as err:
        schedule.update(seeded, admin(seeded), enabled=True, every_hours=0, now=NOW)
    assert err.value.code == "bad_interval"


def test_due_round_runs_and_moves_the_next_time_forward(seeded):
    schedule.update(seeded, admin(seeded), enabled=True, every_hours=6, now=NOW)
    assert schedule.run_due(seeded, NOW + timedelta(hours=5)) is None
    run = schedule.run_due(seeded, NOW + timedelta(hours=13))  # two intervals missed: run once
    assert run is not None and not run.dry_run and run.matched == 9
    assert schedule.view(seeded)["next_run_at"].startswith((NOW + timedelta(hours=18)).date().isoformat())
    assert schedule.run_due(seeded, NOW + timedelta(hours=13, minutes=1)) is None


def test_switched_off_schedule_never_runs(seeded):
    schedule.update(seeded, admin(seeded), enabled=True, every_hours=1, now=NOW)
    schedule.update(seeded, admin(seeded), enabled=False, every_hours=1, now=NOW)
    assert schedule.run_due(seeded, NOW + timedelta(days=3)) is None


def test_tick_expires_reminds_runs_and_delivers(seeded):
    schedule.update(seeded, admin(seeded), enabled=True, every_hours=1, now=NOW)
    delivered = []
    schedule.tick(seeded, NOW + timedelta(hours=1), sender=lambda to, s, b: delivered.append(s))
    assert seeded.scalar(select(func.count(MatchRun.id))) == 1
    assert len(delivered) == 9


# ---------------------------------------------------------------- FR-APPR-03 approval form
def test_approval_form_lists_every_member_and_the_approver(seeded):
    saved_round(seeded)
    cycle = approve_first_cycle(seeded)
    pdf = cycles.approval_form_pdf(seeded, cycle.id)
    assert pdf.startswith(b"%PDF")
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    for m in cycle.members:
        assert m.request.student.name in text and m.request.student.roll_no in text
        assert m.request.tracking_id in text
    assert "Warden Office" in text and "Signature" in text


def test_approval_form_only_for_approved_swaps(seeded):
    saved_round(seeded)
    cycle = seeded.scalars(select(SwapCycle)).first()
    with pytest.raises(DomainError) as err:
        cycles.approval_form_pdf(seeded, cycle.id)
    assert err.value.code == "not_approved"


def test_approver_is_recorded(seeded):
    saved_round(seeded)
    cycle = approve_first_cycle(seeded)
    assert cycle.approved_by.name == "Warden Office"


# ---------------------------------------------------------------- HTTP: staff routes
@pytest.fixture
def staff(tmp_path):
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    app = create_app("sqlite://", frontend_dir=tmp_path)
    with app.state.session_factory() as db:
        seed(db, now=NOW)
    app.dependency_overrides[get_now] = lambda: NOW
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"email": "warden@thapar.edu", "password": DEMO_PASSWORD, "role": "admin"})
        yield c


def test_event_log_downloads_as_csv(staff):
    staff.post("/api/admin/match-runs", json={"algorithm": "ttc", "dry_run": False})
    r = staff.get("/api/admin/events.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["id", "time_utc", "kind", "message", "student", "roll_no", "cycle_id"]
    kinds = {row[2] for row in rows[1:]}
    assert {"request_submitted", "match_run", "match_found"} <= kinds


def test_schedule_routes(staff):
    assert staff.get("/api/admin/schedule").json()["enabled"] is False
    r = staff.put("/api/admin/schedule", json={"enabled": True, "every_hours": 12})
    assert r.status_code == 200 and r.json()["every_hours"] == 12
    assert staff.put("/api/admin/schedule", json={"enabled": True, "every_hours": 0}).status_code == 422


def test_outbox_route_says_mail_is_not_being_sent(staff, monkeypatch):
    monkeypatch.delenv("CAMPUSSWAP_SMTP_HOST", raising=False)
    staff.post("/api/admin/match-runs", json={"algorithm": "ttc", "dry_run": False})
    body = staff.get("/api/admin/emails").json()
    assert body["delivery"] == "off" and len(body["emails"]) == 9
    assert body["emails"][0]["status"] == "queued"


def test_approval_pdf_route(staff):
    staff.post("/api/admin/match-runs", json={"algorithm": "ttc", "dry_run": False})
    cycle_id = staff.get("/api/admin/requests").json()[-1]["cycle"]["id"]
    assert staff.get(f"/api/admin/cycles/{cycle_id}/approval.pdf").status_code == 409
    r = staff.get("/api/admin/cycles/999/approval.pdf")
    assert r.status_code == 404


def test_students_cannot_use_staff_tools(tmp_path):
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    app = create_app("sqlite://", frontend_dir=tmp_path)
    with app.state.session_factory() as db:
        seed(db, now=NOW)
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"email": "student1@thapar.edu", "password": DEMO_PASSWORD, "role": "student"})
        for path in ("/api/admin/events.csv", "/api/admin/emails", "/api/admin/schedule"):
            assert c.get(path).status_code == 403
