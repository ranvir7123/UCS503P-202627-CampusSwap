"""Feature 2: the admin runs a matching round over all open requests."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import Admin, CycleMember, MatchRun, Seat, SwapCycle, SwapRequest
from app.services.cycles import expire_overdue
from app.services.events import log
from engine import MatchResult, Participant, cycle_length_counts, match_yield, pairwise_swaps, top_trading_cycles

CONFIRM_WINDOW = timedelta(hours=48)
ALGORITHMS = {"ttc": top_trading_cycles, "pairwise": pairwise_swaps}
_run_lock = threading.Lock()  # only one matching round at a time


def run_matching(db: Session, admin: Admin, algorithm: str, dry_run: bool, now: datetime) -> MatchRun:
    if algorithm not in ALGORITHMS:
        raise DomainError(400, "unknown_algorithm", "Algorithm must be 'ttc' or 'pairwise'.")
    if algorithm == "pairwise" and not dry_run:
        raise DomainError(400, "pairwise_must_be_dry_run", "The 1:1-only comparison can only be run as a dry run.")
    if not _run_lock.acquire(blocking=False):
        raise DomainError(409, "run_in_progress", "A matching round is already running.")
    try:
        expire_overdue(db, now)
        pool = db.scalars(select(SwapRequest).where(SwapRequest.status == "open").order_by(SwapRequest.id)).all()
        by_id = {r.id: r for r in pool}
        result = ALGORITHMS[algorithm]([Participant(r.id, r.seat_id, _wanted_seats(r)) for r in pool])
        ranks = {pid: _received_rank(db, by_id[pid], seat_id) for pid, seat_id in result.assignment.items()}
        first_choices = sum(1 for rank in ranks.values() if rank == 1)

        run = MatchRun(
            created_at=now, run_by=admin, algorithm=algorithm, dry_run=dry_run,
            pool_size=len(pool), matched=len(result.assignment),
            yield_pct=match_yield(result, len(pool)),
            first_choice_pct=round(100 * first_choices / len(ranks), 1) if ranks else 0.0,
            cycles_by_length={str(k): v for k, v in cycle_length_counts(result).items()},
            trace="",
        )
        run.trace = "\n".join(_trace_lines(result, by_id, run))
        db.add(run)
        db.flush()

        if not dry_run:
            for cycle in result.cycles:
                _save_cycle(db, run, cycle.members, by_id, result, ranks, now)
        mode = "dry run" if dry_run else "saved"
        log(db, now, "match_run",
            f"{algorithm.upper()} round #{run.id} ({mode}): matched {run.matched} of {run.pool_size}.")
        db.flush()
        return run
    finally:
        _run_lock.release()


def compare_algorithms(db: Session, admin: Admin, now: datetime) -> tuple[MatchRun, MatchRun]:
    """Dry-run TTC and 1:1-only on the same pool at the same moment (proposal 6.1)."""
    ttc = run_matching(db, admin, "ttc", dry_run=True, now=now)
    pairwise = run_matching(db, admin, "pairwise", dry_run=True, now=now)
    return ttc, pairwise


def _wanted_seats(request: SwapRequest) -> tuple[int, ...]:
    """Ranked choices -> ranked seats. A room gives its seats in id order; a room
    type gives the seats of every matching room except the student's own."""
    own_room = request.seat.room_id
    seats: list[int] = []
    for pref in request.preferences:
        for room in pref.rooms():
            if room.id != own_room:
                seats.extend(seat.id for seat in room.seats if seat.id not in seats)
    return tuple(seats)


def _received_rank(db: Session, request: SwapRequest, seat_id: int) -> int:
    room = db.get(Seat, seat_id).room
    return next(p.rank for p in request.preferences if p.matches(room))


def _save_cycle(db, run, members, by_id, result: MatchResult, ranks, now) -> None:
    cycle = SwapCycle(match_run=run, status="proposed", deadline=now + CONFIRM_WINDOW, created_at=now)
    db.add(cycle)
    for position, pid in enumerate(members):
        request = by_id[pid]
        cycle.members.append(CycleMember(
            request=request, position=position, gives_seat_id=request.seat_id,
            receives_seat_id=result.assignment[pid], received_rank=ranks[pid], response="pending",
        ))
        request.status = "matched"
        request.updated_at = now
    db.flush()
    for member in cycle.members:
        log(db, now, "match_found",
            f"Match found: a {len(members)}-way swap. You get your choice #{member.received_rank}. "
            f"Please confirm before the deadline.", student_id=member.request.student_id, cycle_id=cycle.id)


def _trace_lines(result: MatchResult, by_id: dict[int, SwapRequest], run: MatchRun) -> list[str]:
    def name(pid: int) -> str:
        return by_id[pid].tracking_id

    title = "Top Trading Cycles" if run.algorithm == "ttc" else "Direct 1:1 swaps only (comparison)"
    lines = [f"Pool: {run.pool_size} open request(s). Algorithm: {title}."]
    if run.algorithm == "ttc":
        for rnd in result.rounds:
            lines.append(f"Round {rnd.number}: {rnd.active} student(s) point at the owner of their best available room.")
            for cycle in rnd.cycles:
                chain = " -> ".join(name(pid) for pid in cycle.members + cycle.members[:1])
                lines.append(f"  Chain found ({len(cycle)}-way): {chain}  (each takes the next one's room)")
            if rnd.kept:
                lines.append(f"  {len(rnd.kept)} student(s) have no available choice left and keep their room.")
    else:
        for cycle in result.cycles:
            a, b = cycle.members
            lines.append(f"  Chain found (2-way): {name(a)} <-> {name(b)}")
    lines.append(f"Matched {run.matched} of {run.pool_size} students (Match Yield {run.yield_pct}%).")
    return lines
