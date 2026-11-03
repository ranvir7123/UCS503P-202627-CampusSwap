# CampusSwap: Hostel Room and Lecture Slot Exchange (UCS503P 2026-27)

CampusSwap finds chains of hostel room swaps (A → B → C → A) using the
**Top Trading Cycles** algorithm, so more students get a room they prefer than
with direct 1:1 swaps alone. Faculty can swap weekly lecture slots the same way,
with the same matching engine.

Team: Jahnavi (1024240152), Ronit Saini (1024240102), Ranvir (1024240001),
Krishna Kapoor (1024240010).

## Run it

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r code/backend/requirements-dev.txt
.venv\Scripts\python code/backend/run.py --reset
```

Linux / macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r code/backend/requirements-dev.txt
.venv/bin/python code/backend/run.py --reset
```

Then open <http://127.0.0.1:8000>. Password for every demo account: `campus123`
(`warden@thapar.edu` on the Hostel staff tab; `student1@thapar.edu` to `student3@thapar.edu`
on the Student tab; `faculty1@thapar.edu` to `faculty3@thapar.edu` on the Faculty tab).
All accounts are listed in [docs/demo-accounts.md](docs/demo-accounts.md).

Showing it live? Add `--demo` (`run.py --reset --demo`): every wait becomes minutes instead
of hours (3 minutes to confirm a swap), so a whole swap, its reminder email and an
automatic round fit into a 5-minute demo. See [docs/showcase.md](docs/showcase.md).

If you already have a `campusswap.db` from an older version, `run.py` stops and asks you
to run it again with `--reset`, which rebuilds the database with fresh demo data.

Run the tests with `.venv\Scripts\python -m pytest` (or `.venv/bin/python -m pytest`).

## Settings (environment variables)

All are optional. Without any of them the app runs locally over plain HTTP and keeps
emails in a queue instead of sending them.

| Variable | What it does |
|---|---|
| `CAMPUSSWAP_SECURE=1` | HTTPS mode: the login cookie is marked *Secure* (only sent over HTTPS), plain HTTP requests are redirected to HTTPS, and every reply carries an HSTS header (tells the browser to use HTTPS for this site for a year). Use it when the app sits behind an HTTPS server. `run.py --cert cert.pem --key key.pem` turns the same mode on and serves HTTPS directly. |
| `CAMPUSSWAP_SMTP_HOST` | The mail server (SMTP = the standard way programs send email). If it is not set, no email leaves CampusSwap: messages stay queued and hostel staff can read them. |
| `CAMPUSSWAP_SMTP_PORT` | Mail server port. Default `587`. |
| `CAMPUSSWAP_SMTP_USER`, `CAMPUSSWAP_SMTP_PASSWORD` | Login for the mail server, if it needs one. |
| `CAMPUSSWAP_SMTP_FROM` | The "From" address. Defaults to the user name, or `campusswap@thapar.edu`. |
| `CAMPUSSWAP_SITE_URL` | The address put in links inside emails. Default `http://127.0.0.1:8000`. |

## What is where

| Folder | Contents |
|---|---|
| `code/backend/engine/` | The TTC matching engine (pure Python, no database) |
| `code/backend/app/` | FastAPI server: tables, business rules, HTTP routes |
| `code/backend/tests/` | pytest tests for the engine and the server |
| `code/frontend/` | The five pages (sign in, rooms, student dashboard, faculty slots, staff), their JavaScript and the Tailwind CSS build |
| `diagrams/` | PlantUML sources for the UML, data flow, architecture and ER diagrams |
| `srs/` | Software Requirements Specification (LaTeX, ready for Overleaf) and its figures |
| `docs/` | Documentation site (MkDocs), including the team study guide |
| `planning/` | Design spec and step-by-step build plans |
| `journals/` | Weekly journal of each team member |
| `project-proposal/`, `project-report-*` | LaTeX reports |

Full documentation: <https://ranvir7123.github.io/UCS503P-202627-CampusSwap/>
(published from `docs/` when `master` is updated).

This repository started from the course template
[tiet-ucs503/ucs503p-202627odd-template](https://github.com/tiet-ucs503/ucs503p-202627odd-template).
