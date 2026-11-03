# Limitations and Phase 2

What the prototype deliberately does **not** do yet, so nobody claims more than is built.

## Known limits of the prototype

| Limit | Why it's acceptable now | Plan |
|---|---|---|
| All data is synthetic (made-up hostels, names, roll numbers) | No real student data may be used in a class prototype | Pilot with 20–40 volunteer students (proposal §6.3) |
| Email + password login, not Thapar single sign-on | A real institute login needs the university's approval | Connect to the institute's Microsoft login |
| No email or phone notifications | Students see everything on their dashboard | Phase 2: notify when a chain is found |
| No PDF approval form | Approval is recorded in CampusSwap | Phase 2: generate the multi-party form for the hostel office |
| Deadlines are checked only when a round runs or someone answers | Enough to keep the rules correct; no extra process to run | A scheduled job if notifications are added |
| Matching runs inside the web request (no background worker) | 2,000 students take ~0.1 s | A worker queue if pools become very large |
| SQLite: one writer at a time | Fine for one hostel office; matching is protected by a lock | Switch to PostgreSQL (one line in `db.py`) |
| Approval updates CampusSwap's own records only | The proposal keeps the hostel office's master records separate | Export for the office's system |
| Students must rank specific rooms | Keeps the prototype simple | Allow "any room of this type/floor" (proposal §10 risk plan) |
| The 1:1 comparison uses a simple greedy pairing | It is only a baseline for comparison | Could use a maximum matching for a stricter baseline |
| No automated browser tests | Pages are checked by hand; server and engine have 90 tests | Add browser tests (e.g. Playwright) |
| Light theme only | The reference designs are light | Add a dark theme |

## Phase 2 (from the proposal)

- Multi-party confirmation flow: **already built** in the prototype.
- Warden portal and audit log export: **partly built** (approval, CSV export and event log).
- PDF sign-off document generator: not started.
- Faculty slot exchange module, reusing the same TTC engine: not started. The engine only
  needs "who owns what" and "who wants what", so lecture slots fit the same shape as rooms.
