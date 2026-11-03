from fastapi import APIRouter

from app.deps import DB, CurrentStudent, Now
from app.schemas import RequestIn
from app.services import cycles
from app.services.requests import submit_request, withdraw_request
from app.services.views import rooms_listing, student_dashboard

router = APIRouter(prefix="/api", tags=["student"])


@router.get("/rooms")
def rooms(db: DB, student: CurrentStudent) -> dict:
    return rooms_listing(db, student)


@router.get("/me/dashboard")
def dashboard(db: DB, student: CurrentStudent, now: Now) -> dict:
    return student_dashboard(db, student, now)


@router.post("/requests", status_code=201)
def create_request(body: RequestIn, db: DB, student: CurrentStudent, now: Now) -> dict:
    request = submit_request(db, student, body.as_choices(), now)
    db.commit()
    return {"tracking_id": request.tracking_id, "status": request.status}


@router.delete("/requests/current")
def withdraw(db: DB, student: CurrentStudent, now: Now) -> dict:
    request = withdraw_request(db, student, now)
    db.commit()
    return {"tracking_id": request.tracking_id, "status": request.status}


@router.post("/cycles/{cycle_id}/accept")
def accept(cycle_id: int, db: DB, student: CurrentStudent, now: Now) -> dict:
    cycle = cycles.accept(db, student, cycle_id, now)
    db.commit()
    return {"cycle_id": cycle.id, "status": cycle.status}


@router.post("/cycles/{cycle_id}/decline")
def decline(cycle_id: int, db: DB, student: CurrentStudent, now: Now) -> dict:
    cycle = cycles.decline(db, student, cycle_id, now)
    db.commit()
    return {"cycle_id": cycle.id, "status": cycle.status}
