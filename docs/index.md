![Tiet Logo](assets/tiet-logo.svg){ .tiet-logo }

**UCS503: Software Engineering (Project)**  
**TIET Patiala**

# CampusSwap: Hostel Room and Lecture Slot Exchange

CampusSwap helps hostel students move to a room they like better, by finding
**chains of swaps** where everyone involved ends up somewhere they prefer.
It uses the **Top Trading Cycles (TTC)** algorithm, which can find 3-way and
4-way chains (A takes B's room, B takes C's, C takes A's) that are almost
impossible to spot by hand in WhatsApp groups. Faculty can swap weekly lecture
slots the same way, with the same engine.

| Team member | Roll number |
|---|---|
| Jahnavi | 1024240152 |
| Ronit Saini | 1024240102 |
| Ranvir | 1024240001 |
| Krishna Kapoor | 1024240010 |

Submitted to: Dr. Raghav B. Venkataramaiyer.

## What the prototype does

The proposal defines Phase 1 success as *accepting a request, saving it to the
database, running a match, and showing the result*. The prototype does all four,
with real data, plus the confirmation step planned for Phase 2.

1. **Sign in** as a student, as hostel staff (the warden) or as a teacher, with a
   `@thapar.edu` email. Too many wrong passwords block further tries for up to 15 minutes.
2. **Feature 1: submit a ranked request.** A student browses rooms in the
   hostels they are allowed to live in, ranks up to 5 choices (exact rooms, or "any
   room like this" by hostel, beds, AC and floor), and gets a tracking ID.
3. **Feature 2: run a matching round.** The warden runs TTC over every open
   request, sees each chain it found and the **Match Yield** (the share of
   students matched), and can compare it with direct 1:1 swaps on the same pool.
4. **Confirm and approve.** Every student in a chain confirms or declines within
   48 hours; once all confirm, the warden approves and the rooms change hands. The
   warden can download a one-page PDF approval form for each approved swap.

Added after the first prototype:

- **Emails** when a swap is found, and a reminder 12 hours before the deadline. They are
  sent only if a mail server is set up; otherwise they wait in a queue that staff can read.
- **Automatic rounds** every N hours, chosen by staff, and a background check every 30
  seconds that closes overdue swaps and sends reminders.
- **An event log** download (every recorded action, as a spreadsheet file).
- **Faculty lecture slot exchange:** a teacher offers one of their lectures and ranks up to
  5 other slots that don't clash with their timetable; staff run slot rounds and approve.
  The teacher and course move; the time and hall stay.

## Try it in two minutes

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r code/backend/requirements-dev.txt
.venv\Scripts\python code/backend/run.py --reset
```

Open <http://127.0.0.1:8000>. Every demo account uses the password `campus123`:

| Account | Who |
|---|---|
| `warden@thapar.edu` | Hostel staff (admin) |
| `student1@thapar.edu`, `student2@...`, `student3@...` | Students with no request yet, in Hostel M rooms A-101, B-101 and A-201 |
| `faculty1@thapar.edu`, `faculty2@...`, `faculty3@...` | Teachers with no slot request yet |

All names, roll numbers and emails in the demo data are made up.
See [Demo accounts](demo-accounts.md) for every account, and
[Getting started](getting-started.md) for Linux/macOS commands, settings, tests and the
full demo scripts.

## Where to read next

- [Architecture](architecture.md): how the pieces fit together.
- [Matching engine](matching-engine.md): TTC explained with a worked example.
- [Diagrams](diagrams.md): Use Case, Class, Sequence and Activity diagrams.
- [Limitations](limitations.md): what is not built yet.
- [Study guide](study/index.md): what each team member must know for the viva.

## Built with

Python 3.12 and FastAPI for the server, SQLite (through SQLAlchemy) for the
database, fpdf2 for the PDF approval form, plain HTML and JavaScript with Tailwind
CSS for the pages, pytest (with pypdf to read the generated PDF in tests) and GitHub
Actions for testing, PlantUML for diagrams and MkDocs for this site.
