"""Builds the web app: API routes under /api, the four pages at /."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import make_engine, make_session_factory
from app.errors import DomainError
from app.clock import utcnow
from app.models import Base
from app.routers import admin, auth, faculty, public, student

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public"


class _RevalidatingStaticFiles(StaticFiles):
    """Serve the pages, but make browsers check for a newer copy every time.

    Without this, a browser can keep using an old CSS or JS file after an update.
    Checking is cheap: an unchanged file gets a short "304 Not Modified" reply.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": exc.code, "message": exc.message})


async def _invalid_input(_request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in first.get("loc", ())[1:])
    message = first.get("msg", "Invalid input.")
    return JSONResponse(status_code=422, content={"error": "invalid_input",
                                                  "message": f"{field}: {message}" if field else message})


TICK_SECONDS = 30
_log = logging.getLogger("campusswap")


def _tick_once(app: FastAPI) -> None:
    from app.services import mail, schedule

    with app.state.session_factory() as db:
        schedule.tick(db, utcnow(), mail.smtp_sender_from_env())


async def _ticker(app: FastAPI) -> None:
    while True:
        try:
            await asyncio.to_thread(_tick_once, app)
        except Exception:  # keep the loop alive; the next tick tries again
            _log.exception("background tick failed")
        await asyncio.sleep(TICK_SECONDS)


def secure_from_env() -> bool:
    """CAMPUSSWAP_SECURE=1 when the site is served over HTTPS (any deployment)."""
    return os.environ.get("CAMPUSSWAP_SECURE", "").strip().lower() in ("1", "true", "yes")


def create_app(database_url: str | None = None, frontend_dir: Path | None = FRONTEND_DIR,
               secure: bool | None = None, background: bool = False) -> FastAPI:
    """secure=True: HTTPS only (plain HTTP is redirected) and the login cookie is marked Secure.
    background=True: run the scheduler tick every 30 s (rounds, reminders, mail). Off in tests."""
    secure = secure_from_env() if secure is None else secure
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)

    @asynccontextmanager
    async def lifespan(app_: FastAPI):
        task = asyncio.create_task(_ticker(app_)) if background else None
        yield
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        engine.dispose()

    app = FastAPI(
        title="CampusSwap API",
        version="0.1.0",
        description="Hostel room exchange using Top Trading Cycles (UCS503P prototype).",
        lifespan=lifespan,
        exception_handlers={DomainError: _domain_error, RequestValidationError: _invalid_input},
    )
    app.state.session_factory = make_session_factory(engine)
    app.state.secure = secure
    if secure:
        app.add_middleware(HTTPSRedirectMiddleware)

        @app.middleware("http")
        async def _hsts(request: Request, call_next):
            response = await call_next(request)
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
            return response
    for module in (auth, public, student, faculty, admin):
        app.include_router(module.router)
    # Pages last, so /api/... is always matched first.
    if frontend_dir is not None and Path(frontend_dir).is_dir():
        app.mount("/", _RevalidatingStaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app
