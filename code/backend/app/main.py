"""Builds the web app: API routes under /api, the four pages at /."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import make_engine, make_session_factory
from app.errors import DomainError
from app.models import Base
from app.routers import admin, auth, public, student

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


def create_app(database_url: str | None = None, frontend_dir: Path | None = FRONTEND_DIR) -> FastAPI:
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(
        title="CampusSwap API",
        version="0.1.0",
        description="Hostel room exchange using Top Trading Cycles (UCS503P prototype).",
        lifespan=lifespan,
        exception_handlers={DomainError: _domain_error, RequestValidationError: _invalid_input},
    )
    app.state.session_factory = make_session_factory(engine)
    for module in (auth, public, student, admin):
        app.include_router(module.router)
    # Pages last, so /api/... is always matched first.
    if frontend_dir is not None and Path(frontend_dir).is_dir():
        app.mount("/", _RevalidatingStaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app
