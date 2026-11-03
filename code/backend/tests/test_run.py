"""run.py refuses a database file made by an older version of the code."""
import sqlite3

from sqlalchemy import create_engine

from app.models import Base
from run import schema_is_current


def test_fresh_schema_is_current(tmp_path):
    path = tmp_path / "new.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    assert schema_is_current(path)


def test_database_missing_a_column_is_not_current(tmp_path):
    path = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(path) as con:
        con.execute("ALTER TABLE rooms DROP COLUMN tags")
    assert not schema_is_current(path)


def test_database_missing_a_table_is_not_current(tmp_path):
    path = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(path) as con:
        con.execute("DROP TABLE login_failures")
    assert not schema_is_current(path)
