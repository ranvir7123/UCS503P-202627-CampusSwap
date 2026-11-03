# Testing and CI

Run everything from the repository root:

```powershell
.venv\Scripts\python -m pytest
```

There are **165 tests**. They live in `code/backend/tests/`. The last run, from the
repository root with `.venv/Scripts/python -m pytest -q`, ended with:

```
165 passed, 1 warning in 32.50s
```

The one warning comes from the test client library (Starlette suggests a newer HTTP
client package), not from CampusSwap's code.

| File | Tests | What it proves |
|---|---|---|
| `test_structures.py` | 6 | Engine data types; duplicate IDs and shared seats are rejected |
| `test_ttc.py` | 14 | 2-, 3-, 4-way cycles; fall-back to second choices; unmatched students; double rooms; same answer in any input order; 50 random pools obey the guarantees; 2,000 students in under 2 s |
| `test_pairwise.py` | 5 | The 1:1-only comparison, including a 3-way chain it cannot find |
| `test_metrics.py` | 3 | Match Yield and chain-length counts |
| `test_security.py` | 5 | Password hashing and session tokens |
| `test_seed.py` | 4 | Demo data: every seat filled, genders match hostels, demo logins work |
| `test_requests_service.py` | 12 | Every rule for submitting and withdrawing a request |
| `test_room_types.py` | 12 | "Any room like this" choices: saved with a readable label, mixed with exact rooms, rejected when no room matches or the hostel is wrong, used by TTC to find a chain, accepted by the API |
| `test_matching_service.py` | 9 | Matching rounds: the seeded pool gives one 2-, 3- and 4-way chain; dry runs change nothing; only one run at a time |
| `test_cycles_service.py` | 8 | Confirm, decline, deadline expiry, approval moving students |
| `test_views_service.py` | 10 | The data each page receives, in every state |
| `test_api.py` | 15 | Over real HTTP: login, permissions, readable errors, a full 3-way swap from request to approval, and pages telling browsers to check for updates |
| `test_auth_security.py` | 18 | Only `@thapar.edu` emails; the failed sign-in limits (per email + address, per address, per email), the lock lifting after 15 minutes, IPv6 /64 grouping, IPv4 seen as IPv6 kept apart; HTTPS mode marks the cookie Secure, sends HSTS and redirects plain HTTP |
| `test_operations.py` | 21 | Emails (queued per member, none for dry runs, one reminder, kept queued without a mail server, retried after a failure), automatic rounds (off at first, run when due, bad interval refused), the background tick, the PDF approval form, the event log CSV, and staff-only access |
| `test_slots.py` | 20 | Lecture slots: offering and ranking, clash and ownership rules, one active request, the seeded 3-way chain, the faculty1/faculty2 2-way swap end to end, decline and deadline expiry, faculty routes and permissions, the database refusing a second active request, approval re-checking slot owners |
| `test_run.py` | 3 | `run.py`'s check that an existing database has every table and column (so an old file asks for `--reset`) |

## How the tests are set up

- Each test gets a fresh **in-memory** SQLite database (`conftest.py`), so tests never
  touch `campusswap.db` and never affect each other.
- Time is fixed (`NOW = 14 Sep 2026, 10:00`), so deadline tests give the same answer every day.
- Engine tests use made-up participants only, as the proposal planned.

## Continuous integration (CI)

`.github/workflows/tests.yml` runs the whole suite on GitHub for **every push and every
pull request**. A red cross on a commit means a test failed. To make GitHub *block*
merging a pull request whose tests fail, turn on branch protection for `master` in the
repository settings (Settings → Branches → require the `tests` check).

The template's `.github/workflows/mkdocs.yml` publishes this documentation site whenever
`master` changes.

## What is not tested automatically

- The five pages. There are no automated browser tests yet.
- Sending email through a real mail server: the tests use a stand-in sender function, so
  the SMTP code path (`smtp_sender_from_env()` in `services/mail.py`) is only checked to
  switch on when `CAMPUSSWAP_SMTP_HOST` is set.
- `run.py` itself (starting the server, the `--cert` / `--key` HTTPS start-up and the
  30-second background loop). The tests call `create_app()` and `tick()` directly instead.
- The strategy-proof and core-stable properties of TTC are proven results about the
  algorithm; the tests check the properties that can be checked directly (nobody worse
  off, seats never given twice, every cycle really closes).
