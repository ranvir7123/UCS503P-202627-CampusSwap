"""Start CampusSwap on this computer.

    python code/backend/run.py            # keep existing data (loads demo data the first time)
    python code/backend/run.py --reset    # wipe the database and reload fresh demo data
    python code/backend/run.py --reset --demo   # live demo: hours become minutes, nothing to wait for
    python code/backend/run.py --cert cert.pem --key key.pem   # serve over HTTPS (Secure cookie)

Then open http://127.0.0.1:8000 (API docs at /docs).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

from app.db import DEFAULT_DB_PATH  # noqa: E402
from app.main import create_app  # noqa: E402
from seed import seed  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CampusSwap prototype locally.")
    parser.add_argument("--reset", action="store_true", help="delete the database and load fresh demo data")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cert", help="HTTPS certificate file (PEM); turns on HTTPS-only mode")
    parser.add_argument("--key", help="private key file (PEM) for --cert")
    parser.add_argument("--demo", action="store_true",
                        help="live demo: 3 minutes to confirm, reminders 2 minutes before, rounds every N minutes")
    args = parser.parse_args()
    if bool(args.cert) != bool(args.key):
        parser.error("--cert and --key must be given together")

    if args.reset:
        DEFAULT_DB_PATH.unlink(missing_ok=True)
    fresh = not DEFAULT_DB_PATH.exists()
    if not fresh and not schema_is_current(DEFAULT_DB_PATH):
        sys.exit(f"{DEFAULT_DB_PATH.name} was made by an older version of CampusSwap. "
                 "Run again with --reset to rebuild it with fresh demo data.")
    https = bool(args.cert)
    app = create_app(secure=True if https else None, background=True, demo=args.demo)
    if fresh:
        with app.state.session_factory() as db:
            seed(db)
        print(f"Loaded demo data into {DEFAULT_DB_PATH.name} (password for every demo account: campus123)")
    scheme = "https" if https else "http"
    if args.demo:
        print("Demo mode: 3 minutes to confirm a swap, reminder emails 2 minutes before, "
              "automatic rounds counted in minutes, checks every 5 seconds")
    print(f"CampusSwap running at {scheme}://{args.host}:{args.port}   API docs: {scheme}://{args.host}:{args.port}/docs")
    uvicorn.run(app, host=args.host, port=args.port, ssl_certfile=args.cert, ssl_keyfile=args.key)


def schema_is_current(path: Path) -> bool:
    """True if every table and column the code expects exists in the database file."""
    from sqlalchemy import create_engine, inspect

    from app.models import Base

    engine = create_engine(f"sqlite:///{path}")
    try:
        found = inspect(engine)
        tables = set(found.get_table_names())
        return all(
            table.name in tables and {c.name for c in table.columns} <= {c["name"] for c in found.get_columns(table.name)}
            for table in Base.metadata.sorted_tables
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
