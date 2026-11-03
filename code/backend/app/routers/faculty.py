from fastapi import APIRouter

from app.deps import DB, CurrentFaculty, Now
from app.schemas import SlotRequestIn
from app.services import slots

router = APIRouter(prefix="/api/faculty", tags=["faculty"])


@router.get("/home")
def home(db: DB, faculty: CurrentFaculty, now: Now) -> dict:
    data = slots.faculty_home(db, faculty, now)
    db.commit()  # may have closed overdue swaps
    return data


@router.post("/requests", status_code=201)
def create_request(body: SlotRequestIn, db: DB, faculty: CurrentFaculty, now: Now) -> dict:
    request = slots.submit(db, faculty, body.slot_id, body.wanted, now)
    db.commit()
    return {"tracking_id": request.tracking_id, "status": request.status}


@router.delete("/requests/current")
def withdraw(db: DB, faculty: CurrentFaculty, now: Now) -> dict:
    request = slots.withdraw(db, faculty, now)
    db.commit()
    return {"tracking_id": request.tracking_id, "status": request.status}


@router.post("/cycles/{cycle_id}/accept")
def accept(cycle_id: int, db: DB, faculty: CurrentFaculty, now: Now) -> dict:
    cycle = slots.accept(db, faculty, cycle_id, now)
    db.commit()
    return {"cycle_id": cycle.id, "status": cycle.status}


@router.post("/cycles/{cycle_id}/decline")
def decline(cycle_id: int, db: DB, faculty: CurrentFaculty, now: Now) -> dict:
    cycle = slots.decline(db, faculty, cycle_id, now)
    db.commit()
    return {"cycle_id": cycle.id, "status": cycle.status}
