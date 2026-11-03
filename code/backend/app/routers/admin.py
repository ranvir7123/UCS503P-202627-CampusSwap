from fastapi import APIRouter, Response

from app.deps import DB, CurrentAdmin, Now
from app.schemas import MatchRunIn, ScheduleIn, SlotRunIn
from app.services import cycles, mail, schedule, slots
from app.services.matching import compare_algorithms, run_matching
from app.services.views import admin_overview, admin_requests, events_csv, export_csv, run_summary

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(db: DB, admin: CurrentAdmin) -> dict:
    return admin_overview(db)


@router.get("/requests")
def requests(db: DB, admin: CurrentAdmin) -> list[dict]:
    return admin_requests(db)


@router.post("/match-runs")
def match_run(body: MatchRunIn, db: DB, admin: CurrentAdmin, now: Now) -> dict:
    run = run_matching(db, admin, body.algorithm, body.dry_run, now)
    db.commit()
    return {**run_summary(run), "trace": run.trace}


@router.post("/compare")
def compare(db: DB, admin: CurrentAdmin, now: Now) -> dict:
    """Dry-run TTC and 1:1-only on the current pool; nothing is saved except the run records."""
    ttc, pairwise = compare_algorithms(db, admin, now)
    db.commit()
    return {"ttc": {**run_summary(ttc), "trace": ttc.trace},
            "pairwise": {**run_summary(pairwise), "trace": pairwise.trace}}


@router.post("/cycles/{cycle_id}/approve")
def approve(cycle_id: int, db: DB, admin: CurrentAdmin, now: Now) -> dict:
    cycle = cycles.approve(db, admin, cycle_id, now)
    db.commit()
    return {"cycle_id": cycle.id, "status": cycle.status}


@router.get("/export.csv")
def export(db: DB, admin: CurrentAdmin) -> Response:
    return Response(content=export_csv(db), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="campusswap-requests.csv"'})


@router.get("/events.csv")
def events_export(db: DB, admin: CurrentAdmin) -> Response:
    return Response(content=events_csv(db), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="campusswap-event-log.csv"'})


@router.get("/cycles/{cycle_id}/approval.pdf")
def approval_pdf(cycle_id: int, db: DB, admin: CurrentAdmin) -> Response:
    return Response(content=cycles.approval_form_pdf(db, cycle_id), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="swap-{cycle_id}-approval.pdf"'})


@router.get("/emails")
def emails(db: DB, admin: CurrentAdmin) -> dict:
    return mail.outbox_view(db)


@router.get("/schedule")
def get_schedule(db: DB, admin: CurrentAdmin) -> dict:
    view = schedule.view(db)
    db.commit()
    return view


@router.put("/schedule")
def put_schedule(body: ScheduleIn, db: DB, admin: CurrentAdmin, now: Now) -> dict:
    schedule.update(db, admin, body.enabled, body.every_hours, now)
    db.commit()
    return schedule.view(db)


@router.get("/slots")
def slot_board(db: DB, admin: CurrentAdmin) -> dict:
    return slots.admin_board(db)


@router.post("/slot-runs")
def slot_run(body: SlotRunIn, db: DB, admin: CurrentAdmin, now: Now) -> dict:
    run = slots.run_round(db, admin, body.dry_run, now)
    db.commit()
    return {**run_summary(run), "trace": run.trace}


@router.post("/slot-cycles/{cycle_id}/approve")
def approve_slots(cycle_id: int, db: DB, admin: CurrentAdmin, now: Now) -> dict:
    cycle = slots.approve(db, admin, cycle_id, now)
    db.commit()
    return {"cycle_id": cycle.id, "status": cycle.status}
