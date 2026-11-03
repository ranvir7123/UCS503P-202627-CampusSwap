"""Two things happening at the same moment, on a real database file (the in-memory one has a single connection)."""
import threading
import time
from collections import Counter
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import make_engine, make_session_factory
from app.errors import DomainError
from app.models import Admin, CycleMember, SwapCycle, SwapRequest, Student
from app.services import cycles, schedule, signin
from app.services.matching import run_matching
from conftest import NOW


@pytest.fixture
def factory(tmp_path):
    from app.models import Base
    from seed import seed

    engine = make_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    with sessions() as db:
        seed(db, now=NOW)
        db.commit()
    yield sessions
    engine.dispose()


def in_thread(work):
    """Start work() in another thread; returns a join() that re-raises its error."""
    box = {}

    def run():
        try:
            work()
        except BaseException as exc:  # noqa: BLE001 - handed back to the test
            box["error"] = exc

    thread = threading.Thread(target=run)
    thread.start()

    def join():
        thread.join(10)
        if "error" in box:
            raise box["error"]
    return join


def test_two_rounds_at_once_never_put_a_request_in_two_swaps(factory):
    first = factory()
    run_matching(first, first.scalar(select(Admin)), "ttc", dry_run=False, now=NOW)  # done, not saved yet

    def second_round():
        with factory() as db:
            try:
                run_matching(db, db.scalar(select(Admin)), "ttc", dry_run=False, now=NOW)
                db.commit()
            except DomainError:
                pass

    join = in_thread(second_round)
    time.sleep(0.5)
    first.commit()
    first.close()
    join()
    with factory() as db:
        per_request = Counter(m.request_id for m in db.scalars(select(CycleMember)))
    assert per_request and max(per_request.values()) == 1


def test_a_confirm_racing_the_deadline_never_confirms_a_closed_swap(factory):
    with factory() as db:
        run_matching(db, db.scalar(select(Admin)), "ttc", dry_run=False, now=NOW)
        db.commit()
        pair = next(c for c in db.scalars(select(SwapCycle)) if len(c.members) == 2)
        cycle_id, deadline = pair.id, pair.deadline
        first_id, last_id = (m.request.student_id for m in pair.members)
        cycles.accept(db, db.get(Student, first_id), cycle_id, NOW)
        db.commit()

    closer = factory()
    assert cycles.expire_overdue(closer, deadline + timedelta(seconds=1)) >= 1  # closed, not saved yet

    def last_confirm():
        with factory() as db:
            try:
                cycles.accept(db, db.get(Student, last_id), cycle_id, deadline - timedelta(seconds=1))
                db.commit()
            except DomainError:
                pass

    join = in_thread(last_confirm)
    time.sleep(0.5)
    closer.commit()
    closer.close()
    join()
    with factory() as db:
        cycle = db.get(SwapCycle, cycle_id)
        statuses = {m.request.status for m in cycle.members}
        assert not (cycle.status == "confirmed" and "open" in statuses), (cycle.status, statuses)


def test_a_slow_mail_server_does_not_hold_up_other_requests(factory):
    with factory() as db:
        admin = db.scalar(select(Admin))
        schedule.update(db, admin, True, 1, NOW)
        db.commit()

    def slow_sender(_to, _subject, _body):
        time.sleep(0.5)

    join = in_thread(lambda: _tick(factory, NOW + timedelta(hours=1), slow_sender))
    time.sleep(0.3)  # the tick has written its round and is now sending mail
    start = time.monotonic()
    with factory() as db:
        signin.record_failure(db, "stu001@thapar.edu", "10.0.0.1", NOW)
        db.commit()
    waited = time.monotonic() - start
    join()
    assert waited < 0.4, f"a sign-in had to wait {waited:.1f}s for the mail server"


def _tick(factory, now, sender):
    with factory() as db:
        schedule.tick(db, now, sender)


def test_a_database_still_busy_after_waiting_gets_a_plain_try_again():
    import sqlite3

    from fastapi.testclient import TestClient
    from sqlalchemy.exc import OperationalError

    from app.deps import get_db
    from app.main import create_app

    app = create_app("sqlite://", frontend_dir=None)

    def locked():
        raise OperationalError("BEGIN IMMEDIATE", {}, sqlite3.OperationalError("database is locked"))
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = locked
    reply = TestClient(app).get("/api/public/stats")
    assert reply.status_code == 503
    assert reply.json()["error"] == "busy"
