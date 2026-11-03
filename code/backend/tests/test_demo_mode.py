"""Demo mode (run.py --demo): the same rules, with hours shortened to minutes."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import timing
from app.errors import DomainError
from app.main import create_app
from app.models import Admin, SlotCycle, SwapCycle
from app.services import mail, schedule, signin, slots
from app.services.matching import run_matching
from conftest import NOW


def run_both_rounds(db):
    admin = db.scalar(select(Admin))
    run_matching(db, admin, "ttc", dry_run=False, now=NOW)
    slots.run_round(db, admin, dry_run=False, now=NOW)


def test_normal_mode_gives_48_hours_to_confirm(seeded):
    run_both_rounds(seeded)
    assert {c.deadline for c in seeded.scalars(select(SwapCycle))} == {NOW + timedelta(hours=48)}
    assert {c.deadline for c in seeded.scalars(select(SlotCycle))} == {NOW + timedelta(hours=48)}


def test_demo_mode_gives_3_minutes_to_confirm(seeded):
    timing.use(timing.DEMO)
    run_both_rounds(seeded)
    assert {c.deadline for c in seeded.scalars(select(SwapCycle))} == {NOW + timedelta(minutes=3)}
    assert {c.deadline for c in seeded.scalars(select(SlotCycle))} == {NOW + timedelta(minutes=3)}


def test_demo_reminder_comes_1_minute_after_the_round(seeded):
    timing.use(timing.DEMO)  # 2 minutes before a 3-minute deadline: the whole story fits in a 5-minute demo
    run_both_rounds(seeded)
    assert mail.send_reminders(seeded, NOW + timedelta(seconds=59)) == 0
    assert mail.send_reminders(seeded, NOW + timedelta(minutes=1)) > 0


def test_demo_automatic_rounds_count_in_minutes(seeded):
    timing.use(timing.DEMO)
    row = schedule.update(seeded, seeded.scalar(select(Admin)), True, 3, NOW)
    assert row.next_run_at == NOW + timedelta(minutes=3)
    assert schedule.view(seeded)["unit"] == "minute"
    assert schedule.run_due(seeded, NOW + timedelta(minutes=2)) is None
    assert schedule.run_due(seeded, NOW + timedelta(minutes=3)) is not None


def test_demo_sign_in_lock_lasts_one_minute(db):
    timing.use(timing.DEMO)
    for _ in range(signin.LIMITS["email_ip"]):
        signin.record_failure(db, "stu001@thapar.edu", "10.0.0.1", NOW)
    with pytest.raises(DomainError):
        signin.check_not_blocked(db, "stu001@thapar.edu", "10.0.0.1", NOW + timedelta(seconds=30))
    signin.check_not_blocked(db, "stu001@thapar.edu", "10.0.0.1", NOW + timedelta(seconds=61))


def test_pages_are_told_the_times_in_use():
    demo = TestClient(create_app("sqlite://", frontend_dir=None, demo=True))
    assert demo.get("/api/public/stats").json()["timing"] == {
        "demo": True, "confirm": "3 minutes", "reminder": "2 minutes", "unit": "minute"}
    normal = TestClient(create_app("sqlite://", frontend_dir=None))
    assert normal.get("/api/public/stats").json()["timing"] == {
        "demo": False, "confirm": "48 hours", "reminder": "12 hours", "unit": "hour"}
