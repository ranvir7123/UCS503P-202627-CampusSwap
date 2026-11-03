"""Database connection. SQLite file by default; tests use an in-memory copy."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "campusswap.db"


def make_engine(url: str | None = None) -> Engine:
    url = url or f"sqlite:///{DEFAULT_DB_PATH}"
    options: dict = {"connect_args": {"check_same_thread": False}}
    if url == "sqlite://":  # in-memory: one shared connection for the whole test
        options["poolclass"] = StaticPool
    engine = create_engine(url, **options)

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        dbapi_connection.isolation_level = None  # SQLAlchemy starts each transaction itself (below)

    # Every transaction takes the write lock first. Two requests at once (a round and
    # a staff click, a confirm and the deadline) then run one after the other, and the
    # second always reads what the first saved, never an older copy.
    @event.listens_for(engine, "begin")
    def _begin_immediate(connection):
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
