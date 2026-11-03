# API

The pages talk to the server only through these JSON endpoints (an *endpoint* is one
method + path the server answers). With the server running,
<http://127.0.0.1:8000/docs> shows the same list as an interactive page where you can try
each call (FastAPI generates it automatically). The routes are in
`code/backend/app/routers/`.

"Who" says which signed-in account may call it. A call from the wrong kind of account gets
`403 forbidden`; a call with no valid login gets `401 not_logged_in`.

## Sign in (`routers/auth.py`, `routers/public.py`)

Signing in sets a cookie called `cs_session` (HttpOnly, so page scripts can't read it). The
browser sends it back automatically on every later request. A sign-in lasts 12 hours. In
HTTPS mode (see [Getting started](getting-started.md#https-optional)) the cookie is also
marked *Secure*.

| Method | Path | Who | What it does |
|---|---|---|---|
| POST | `/api/auth/login` | anyone | Body `{email, password, role}`, where `role` is `student`, `admin` or `faculty`. Only `@thapar.edu` emails are accepted. Checks the failed sign-in limits, then sets the cookie and returns the user. |
| POST | `/api/auth/logout` | anyone | Deletes the session and the cookie. |
| GET | `/api/auth/me` | signed in | The current user (students also get roll number, year, branch and room; faculty get department). |
| GET | `/api/auth/status` | anyone | `{user: ...}` or `{user: null}`; never an error. Used by the sign-in page. |
| GET | `/api/public/stats` | anyone | Numbers for the sign-in page: open requests, rooms, hostels, requests per day, last round. No personal data. |

Failed sign-in limits, all within 15 minutes: 5 failures for one email from one network
address, 20 from one network address for any emails, 50 for one email from all addresses
together. IPv6 addresses in the same /64 block count as one address. Once a limit is
reached, the server answers `429 too_many_attempts` and says how many minutes to wait. A
correct sign-in clears that email's failures.

## Student (`routers/student.py`)

| Method | Path | Who | What it does |
|---|---|---|---|
| GET | `/api/rooms` | student | Rooms in hostels the student may live in, each with `is_own` and `open_to_swap` (how many occupants there want to swap). |
| GET | `/api/me/dashboard` | student | Current room, active request, swap chain (if any), progress steps and activity. |
| POST | `/api/requests` | student | Submit a ranked request (1–5 choices, best first). Returns `201 {tracking_id, status}`. See the body shapes below. |
| DELETE | `/api/requests/current` | student | Withdraw the active request (only while it is `open`). |
| POST | `/api/cycles/{id}/accept` | student | Confirm your place in a proposed chain. |
| POST | `/api/cycles/{id}/decline` | student | Decline: the chain is cancelled; you are withdrawn and the others go back to the pool. |

`POST /api/requests` accepts either shape:

```json
{"room_ids": [12, 7]}
```

```json
{"choices": [
  {"room_id": 12},
  {"type": {"hostel": "M", "seater": 1, "ac": true, "floor": 2}}
]}
```

A `type` choice means "any room like this": a hostel code plus any of `seater` (1, 2 or 3
beds), `ac` (true / false) and `floor`. A filter left out means "any". Each choice gives
either `room_id` or `type`, never both.

## Faculty (`routers/faculty.py`)

| Method | Path | Who | What it does |
|---|---|---|---|
| GET | `/api/faculty/home` | faculty | Your lectures, every slot in the timetable (with whether it is yours, open to swap, or clashes with your lectures), your request, your swap chain (if any), activity and the last slot round. |
| POST | `/api/faculty/requests` | faculty | Body `{slot_id, wanted: [best, second, ...]}`: offer one of your slots and rank 1–5 others. A wanted slot may not clash with your other lectures. Returns `201 {tracking_id, status}` (tracking IDs look like `SL-2026-0005`). |
| DELETE | `/api/faculty/requests/current` | faculty | Withdraw your active slot request (only while it is `open`). |
| POST | `/api/faculty/cycles/{id}/accept` | faculty | Confirm your place in a proposed slot chain. |
| POST | `/api/faculty/cycles/{id}/decline` | faculty | Decline: the slot chain is cancelled for everyone in it. |

## Hostel staff (`routers/admin.py`)

All of these are for hostel staff (the `admin` role) only.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/admin/overview` | Counts, the latest saved round, the latest TTC-vs-1:1 comparison, the latest trace. |
| GET | `/api/admin/requests` | Every room request with its chain, if any. |
| POST | `/api/admin/match-runs` | Body `{algorithm: "ttc", dry_run: false}`. Runs a room round and returns the summary and trace. `algorithm: "pairwise"` (1:1 only) is allowed only with `dry_run: true`. |
| POST | `/api/admin/compare` | Dry-runs TTC and 1:1-only on the current room pool at the same moment. |
| POST | `/api/admin/cycles/{id}/approve` | Approve a room chain everyone confirmed; beds change hands. |
| GET | `/api/admin/cycles/{id}/approval.pdf` | Download the one-page PDF approval form for an approved room chain (members, rooms, confirmation times, approver, signature lines). |
| GET | `/api/admin/export.csv` | Download all room requests as a spreadsheet file. |
| GET | `/api/admin/events.csv` | Download the whole event log (every recorded action) as a spreadsheet file. |
| GET | `/api/admin/emails` | The latest 100 emails in the outbox, and whether sending is on (`smtp`) or off. |
| GET | `/api/admin/schedule` | The automatic round setting: on or off, every how many hours, when the next round runs, who set it. |
| PUT | `/api/admin/schedule` | Body `{enabled, every_hours}` (1 to 336 hours, which is 14 days). Turns automatic room rounds on or off; the first one runs `every_hours` from now. |
| GET | `/api/admin/slots` | Every lecture slot request with its chain, the latest slot round and its trace. |
| POST | `/api/admin/slot-runs` | Body `{dry_run: false}`. Runs a lecture slot round (TTC). |
| POST | `/api/admin/slot-cycles/{id}/approve` | Approve a slot chain everyone confirmed: each teacher and their course move to the slot they receive; times and halls stay. First re-checks that every teacher still teaches the slot they are giving; if not, the chain is cancelled (`409 stale_swap`) and everyone in it goes back to the pool. |

## Errors

Every error has the same shape, so the pages can show a clear message:

```json
{"error": "own_room", "message": "You can't rank the room you already live in."}
```

| Status | Meaning | Codes |
|---|---|---|
| 400 | The request breaks a rule | `not_institute_email`, `empty_list`, `too_many`, `duplicate_room`, `own_room`, `unknown_room`, `unknown_hostel`, `wrong_hostel_gender`, `empty_type`, `duplicate_slot`, `not_your_slot`, `unknown_slot`, `own_slot`, `slot_clash`, `unknown_algorithm`, `pairwise_must_be_dry_run`, `bad_interval` |
| 401 | Not signed in, or wrong password | `not_logged_in`, `bad_credentials` |
| 403 | Signed in, but not allowed | `forbidden`, `wrong_role`, `not_member` |
| 404 | Doesn't exist | `no_request`, `no_cycle` |
| 409 | Not possible right now | `already_active`, `in_cycle`, `no_seat`, `cycle_closed`, `already_answered`, `not_confirmed`, `not_approved`, `run_in_progress`, `stale_swap` |
| 422 | The body has the wrong shape | `invalid_input` |
| 429 | Too many failed sign-ins | `too_many_attempts` |
