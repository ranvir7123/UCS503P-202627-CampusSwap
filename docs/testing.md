# Testing and CI

Run everything from the repository root:

```powershell
.venv\Scripts\python -m pytest
```

There are **90 tests**, and they take about 10 to 15 seconds. They live in `code/backend/tests/`.

| File | Tests | What it proves |
|---|---|---|
| `test_structures.py` | 6 | Engine data types; duplicate IDs and shared seats are rejected |
| `test_ttc.py` | 14 | 2-, 3-, 4-way cycles; fall-back to second choices; unmatched students; double rooms; same answer in any input order; 50 random pools obey the guarantees; 2,000 students in under 2 s |
| `test_pairwise.py` | 5 | The 1:1-only comparison, including a 3-way chain it cannot find |
| `test_metrics.py` | 3 | Match Yield and chain-length counts |
| `test_security.py` | 5 | Password hashing and session tokens |
| `test_seed.py` | 4 | Demo data: every seat filled, genders match hostels, demo logins work |
| `test_requests_service.py` | 12 | Every rule for submitting and withdrawing a request |
| `test_matching_service.py` | 9 | Matching rounds: the seeded pool gives one 2-, 3- and 4-way chain; dry runs change nothing; only one run at a time |
| `test_cycles_service.py` | 8 | Confirm, decline, deadline expiry, approval moving students |
| `test_views_service.py` | 9 | The data each page receives, in every state |
| `test_api.py` | 15 | Over real HTTP: login, permissions, readable errors, a full 3-way swap from request to approval, and pages telling browsers to check for updates |

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

- The four pages are checked by hand in a browser (and their JavaScript is checked for
  syntax errors with `node --check`). There are no automated browser tests yet.
- The strategy-proof and core-stable properties of TTC are proven results about the
  algorithm; the tests check the properties that can be checked directly (nobody worse
  off, seats never given twice, every cycle really closes).
