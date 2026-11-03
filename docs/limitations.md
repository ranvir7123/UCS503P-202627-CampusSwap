# Limitations and Phase 2

What the prototype does **not** do yet, so nobody claims more than is built.

## Known limits of the prototype

| Limit | Why it's acceptable now | Plan |
|---|---|---|
| All data is synthetic (made-up hostels, teachers, names, roll numbers) | No real student data may be used in a class prototype | Pilot with 20–40 volunteer students (proposal §6.3) |
| Email + password login, not Thapar single sign-on (signing in once with the institute's Microsoft account) | Single sign-on needs an app registration inside Thapar's Microsoft tenant (the university's own Microsoft account system), which only the university can create | Register the app with the university and connect to its Microsoft login |
| Sending email by SMTP has only been tested with a stand-in sender in the tests, never against a real mail server | Every email is queued and staff can read it, so nothing is lost when no mail server is set up | Try it with the institute's mail server and check delivery |
| Teachers get a "slot swap found" email but no 12-hour reminder (reminders are for room swaps only) | The "swap found" email already states the deadline | Add slot reminders the same way |
| SQLite: one writer at a time | Fine for one hostel office; matching rounds are protected by a lock, and the database allows only one active request per person | Switch to PostgreSQL (one line in `db.py`) |
| Matching runs inside the web request or the 30-second background check, not in a separate worker | 2,000 students take ~0.1 s | A worker queue if pools become very large |
| The background check runs inside the one server process | Enough for one laptop or one server | A separate scheduler if the app runs on several servers |
| Approval updates CampusSwap's own records only (seats, and lecture slot owners) | The proposal keeps the hostel office's master records separate; the PDF form is what the office files | Export for the office's system |
| The PDF approval form exists for room swaps only, not for lecture slot swaps | Slot approval is recorded in CampusSwap and in the event log | Add a slot version of the form |
| No sign-up page and no password change | Demo accounts are made by `seed.py`; real accounts would come from the institute login | Comes with single sign-on |
| The 1:1 comparison uses a simple greedy pairing | It is only a baseline for comparison | Could use a maximum matching for a stricter baseline |
| No automated browser tests | The server and the engine have 175 automated tests; the five pages are only checked by hand | Add browser tests (e.g. Playwright) |
| The app runs on a laptop, not on a public server | The demo only needs one machine | Deploy behind HTTPS (`CAMPUSSWAP_SECURE=1`) |

## Phase 2 (from the proposal)

- Multi-party confirmation flow: **built**.
- Email notices (match found, reminder 12 hours before the deadline): **built**; sending
  through a real mail server is not yet tested (see above).
- Warden portal and audit log export: **built** (approval, requests CSV, event log CSV,
  automatic rounds).
- PDF sign-off document: **built** for room swaps (one page per approved swap).
- Faculty slot exchange module, reusing the same TTC engine: **built** (server, faculty page and tests).
  The engine only needs "who owns what" and "who wants what", so lecture slots fit the
  same shape as rooms.
- Institute single sign-on: not started (needs the university, see above).
