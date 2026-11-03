# Architecture

CampusSwap is a **three-layer web application** with a separate **matching engine**.
Each layer has one job and only talks to the layer next to it.

```
Browser pages (HTML + JavaScript)          code/frontend/public/
        │  JSON over HTTP (/api/...)
FastAPI routes: read input, shape output   code/backend/app/routers/
        │  plain function calls
Services: every business rule              code/backend/app/services/
        │                     │
SQLite through SQLAlchemy     TTC engine (pure Python)
code/backend/app/models.py    code/backend/engine/
```

## The pieces

| Piece | Job | Key files |
|---|---|---|
| **Pages** | What students, teachers and the warden see and click. No rules live here; they only call the API and draw the answer. | `index.html` (sign in), `rooms.html`, `dashboard.html`, `slots.html` (faculty), `admin.html`, `js/*.js` |
| **Routes** | Turn an HTTP request into a function call, then turn the result into JSON. Also check who is signed in. | `routers/auth.py`, `student.py`, `faculty.py`, `admin.py`, `public.py`, `deps.py` |
| **Services** | All the rules: who may submit what, how a round runs, what happens on confirm/decline/approve/deadline, sign-in limits, emails, automatic rounds, the PDF form. | `services/requests.py`, `matching.py`, `cycles.py`, `slots.py`, `signin.py`, `mail.py`, `schedule.py`, `pdf.py`, `events.py`, `views.py` |
| **Background check** | Every 30 seconds while the server runs: close overdue chains, queue reminders, run a due automatic round, send queued emails. | `_ticker()` in `main.py`, `tick()` in `services/schedule.py` |
| **Models** | The database tables and how they link. | `models.py`, `db.py` |
| **Engine** | Top Trading Cycles, the 1:1-only comparison, and the metrics. Knows nothing about databases or the web. | `engine/ttc.py`, `pairwise.py`, `metrics.py`, `structures.py` |

## What happens when a student submits a request

1. `rooms.js` sends `POST /api/requests` with the ranked choices (exact rooms, or "any room
   like this" room types).
2. `routers/student.py` checks the login cookie (through `deps.current_student`) and calls
   `services.requests.submit_request(...)`.
3. The service checks every rule (at most 5 choices, no duplicates, not your own room, the
   room or hostel exists, the hostel matches your gender, a room type matches at least one
   room other than yours, you have a room, no other active request).
   Breaking a rule raises a `DomainError` with a short code such as `own_room`.
4. If all is well it saves the request and its preferences, gives it a tracking ID and
   writes an event. If a second submit from the same student slipped in at the same moment,
   the database's one-active-request rule refuses it and the student gets `already_active`.
   The route then commits the database transaction.
5. The route returns `201 {"tracking_id": "CS-2026-0013", "status": "open"}`, and the page
   moves to the dashboard.

A `DomainError` anywhere becomes JSON like `{"error": "own_room", "message": "..."}`,
which the page shows in a toast.

## Design decisions (and why)

| Decision | Why | What would go wrong otherwise |
|---|---|---|
| The engine is pure Python with no database code | It can be unit-tested with made-up data, as the proposal promised, and it is reused unchanged for faculty lecture slot swaps | Tests would need a database; the algorithm would be tangled with storage code |
| Rules live only in services, never in routes or pages | One place to read and test each rule | The same rule would be copied (and drift) between the page and the server |
| Every change happens inside one database transaction | A matching round saves either everything or nothing (the "ACID" guarantee from the proposal) | A crash half-way could leave some students "matched" with no cycle |
| SQLite database file | Nothing to install for the lab; SQLAlchemy lets us switch to PostgreSQL by changing one line | Setting up a database server could fail during the demo |
| Server-side sessions: random token in an HttpOnly cookie, only its SHA-256 stored | JavaScript can't read the cookie, and a leaked database can't be used to log in | Tokens in `localStorage` can be stolen by injected scripts |
| Passwords hashed with `scrypt` (Python standard library) | Slow, salted hashing is the accepted way to store passwords | Plain or fast-hashed passwords are easy to recover if leaked |
| One Tailwind CSS file per page, built locally, sharing one set of colour names (`tailwind/theme.cjs`) | Works without internet; every page looks the same | Loading Tailwind from a CDN breaks the demo if the Wi-Fi drops |
| Matching runs inside the web request or the background check, no separate worker | TTC on a whole hostel takes milliseconds (2,000 students ≈ 0.1 s in our tests) | A job queue adds moving parts with no benefit at this size |
| A background check every 30 s inside the server process (an *asyncio* task: a loop that runs alongside the web requests) | Overdue chains close and reminders go out even when nobody uses the site; nothing extra to start | A separate scheduler program would be one more thing to keep running |
| Deadlines are also checked when something happens | Any round, confirm or decline first dissolves overdue chains, so the rules hold between two checks | Someone could answer a chain whose deadline passed a few seconds ago |
| Emails are written to an outbox table first, then sent | A mail server that is down or not set up loses nothing; staff can read every email | Emails sent straight from a request would be lost on any mail error |
| Sign-in limits are stored in the database (`login_failures`), counted per email + address, per address and per email | A stranger typing wrong passwords for your email can't lock you out from your own network address | Counting only per email lets anyone block anyone |
| The database itself allows one active request per person | Two quick submits can't both get through, even at the same instant | A check in code alone has a gap between "check" and "save" |

The proposal mentions a separate background worker; at prototype scale one loop inside the
server does the same job. See [Limitations](limitations.md).

## Folder map

```
code/backend/
  app/            server: main.py, db.py, models.py, security.py, deps.py, schemas.py
    routers/      HTTP routes (auth, public, student, faculty, admin)
    services/     business rules
  engine/         Top Trading Cycles + 1:1 comparison + metrics
  tests/          pytest tests (engine, services, HTTP)
  seed.py         synthetic demo data (students, rooms, teachers, lecture slots)
  run.py          one-command start (--reset, --cert/--key for HTTPS)
code/frontend/
  public/         the pages, js/, built assets/ and fonts/
  tailwind/       one Tailwind config per page, plus theme.cjs (the shared colours)
  src/            shared CSS entry (fonts, base styles, shared classes)
diagrams/         PlantUML sources + render.py
docs/             this site
```
