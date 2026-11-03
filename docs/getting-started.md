# Getting started

## What you need

- **Python 3.12** (to run the server and tests).
- **Node.js 20 or newer**: only if you change page styling and need to rebuild
  the CSS. The built CSS is already in the repository, so the app runs without Node.
- No internet is needed to run the app: fonts and styles are stored in the repo.

## Set up once

=== "Windows (PowerShell)"

    ```powershell
    python -m venv .venv
    .venv\Scripts\python -m pip install -r code/backend/requirements-dev.txt
    ```

=== "Linux / macOS"

    ```bash
    python3 -m venv .venv
    .venv/bin/python -m pip install -r code/backend/requirements-dev.txt
    ```

A *virtual environment* (`.venv`) is a private folder of Python libraries for this
project, so it doesn't clash with anything else on your laptop.

## Run the app

```powershell
.venv\Scripts\python code/backend/run.py --reset
```

- `--reset` deletes the database file (`code/backend/campusswap.db`) and loads fresh
  demo data. Leave it off to keep what you did last time.
- If `campusswap.db` was made by an older version of CampusSwap (it is missing a table or
  a column the code now needs), `run.py` stops with a message asking you to run it again
  with `--reset`. That rebuilds the database and loses the old data.
- Open <http://127.0.0.1:8000>. The interactive API reference is at
  <http://127.0.0.1:8000/docs>.
- Stop the server with `Ctrl+C`.
- While it runs, a **background check every 30 seconds** closes swaps whose 48-hour
  deadline has passed, queues reminder emails, runs an automatic matching round if one is
  due, and hands queued emails to the mail server (if one is set up).
- Add `--demo` for a live demo: 3 minutes to confirm instead of 48 hours, reminders 2
  minutes before the deadline, automatic rounds counted in minutes, a check every 5
  seconds. The pages say *Demo mode* while it is on.

### HTTPS (optional)

HTTPS encrypts the traffic between the browser and the server. For a local demo plain
HTTP is fine. To serve HTTPS directly you need a certificate file and its private key
(both in PEM, a common text format for certificates):

```powershell
.venv\Scripts\python code/backend/run.py --cert cert.pem --key key.pem
```

`--cert` and `--key` must be given together. In this mode the login cookie is marked
*Secure* (the browser only sends it over HTTPS), requests that reach the app over plain HTTP are redirected to
HTTPS, and replies carry an HSTS header (tells the browser to use only HTTPS for this site
for a year). If another server already handles HTTPS in front of CampusSwap, set
`CAMPUSSWAP_SECURE=1` instead to get the same behaviour without `--cert`.

### Settings (environment variables)

All optional. Set them before starting, for example `$env:CAMPUSSWAP_SMTP_HOST = "smtp.example.org"`
in PowerShell or `export CAMPUSSWAP_SMTP_HOST=smtp.example.org` on Linux / macOS.

| Variable | What it does |
|---|---|
| `CAMPUSSWAP_SECURE=1` | HTTPS mode, as above. |
| `CAMPUSSWAP_SMTP_HOST` | The mail server (SMTP is the standard way programs send email). Without it, no email leaves CampusSwap: every email stays *queued*, and hostel staff can read it through `GET /api/admin/emails`. |
| `CAMPUSSWAP_SMTP_PORT` | Mail server port. Default `587`. The connection is upgraded to an encrypted one (STARTTLS) before sending. |
| `CAMPUSSWAP_SMTP_USER`, `CAMPUSSWAP_SMTP_PASSWORD` | Login for the mail server, if it needs one. |
| `CAMPUSSWAP_SMTP_FROM` | The "From" address. Defaults to the user name, or `campusswap@thapar.edu`. |
| `CAMPUSSWAP_SITE_URL` | The address used in links inside emails. Default `http://127.0.0.1:8000`. |

Which emails exist: a "swap found" email to every member of a new room chain or lecture
slot chain, and one reminder to each student who has not answered a room swap once 12 hours
or less are left before the deadline. A failed send is kept and tried again on the next
check, up to 5 times.

### Signing in

- Only addresses ending in `@thapar.edu` are accepted; the server checks this, not only the page.
- Use the tab that matches the account (Student, Hostel staff or Faculty). On the wrong
  tab the server says which tab to use.
- Too many wrong passwords within 15 minutes block further tries for a while: 5 for one
  email from one network address, 20 from one network address for any emails, 50 for one
  email from all addresses together. IPv6 addresses in the same /64 block (one home or
  phone connection usually gets a whole block) count as one address. The message says how
  many minutes to wait.

### Demo accounts (password `campus123` for all)

| Email | Tab | Who |
|---|---|---|
| `warden@thapar.edu` | Hostel staff | The warden |
| `student1@thapar.edu` | Student | Hostel M, A-101 |
| `student2@thapar.edu` | Student | Hostel M, B-101 |
| `student3@thapar.edu` | Student | Hostel M, A-201 |
| `faculty1@thapar.edu` | Faculty | Dr. Neha Arora: UCS503 (Mon 08:00), UCS414 (Wed 14:00) |
| `faculty2@thapar.edu` | Faculty | Dr. Vikram Sood: UCS301 (Tue 10:00), UCS310 (Thu 11:00) |
| `faculty3@thapar.edu` | Faculty | Dr. Kiran Walia: UEC401 (Fri 09:00), UEC510 (Mon 15:00) |

Every other account is in [Demo accounts](demo-accounts.md).

The demo data already has **12 open room requests** built so that TTC finds one 2-way,
one 3-way and one 4-way chain and leaves 3 students unmatched (Match Yield 75%).
Direct 1:1 swaps alone match only 2 of those 12 (16.7%). It also has **4 open lecture slot
requests** (`fac004` to `fac008`) that give one 3-way slot chain and leave 1 teacher unmatched.

## The 3-minute lab demo (room swap)

1. Sign in as **student1**, open *Find rooms*, filter to Hostel M, rank **B-101**, submit.
   Note the tracking ID.
2. Do the same as **student2** ranking **A-201**, and **student3** ranking **A-101**.
   These three requests form a 3-way loop.
3. Sign in as the **warden**. Use the dry run and *Compare* to show TTC vs 1:1 on the same
   students. Then run a saved TTC matching round and walk through the step-by-step trace.
4. Sign in as student1, 2 and 3 in turn and press **Confirm swap** on the dashboard.
5. Back as the warden, press **Approve swap** on the confirmed chain.
   Student1's dashboard now shows room B-101. The approved swap's one-page PDF approval
   form can now be downloaded from the staff page.

## Faculty demo (lecture slot swap)

A slot swap moves a teacher and their course to another slot. The time and the hall of
each slot stay the same.

1. Sign in as **faculty1** on the *Faculty* tab. Offer **UCS503** (Mon 08:00) and rank the
   **UCS301** slot (Tue 10:00). You can rank up to 5 slots, and the server refuses a slot
   that clashes with your other lecture.
2. Sign in as **faculty2**. Offer **UCS301** (Tue 10:00) and rank the **UCS503** slot (Mon 08:00).
3. Sign in as the **warden**, open the *Lecture slots* view and run a saved slot round. It finds the new 2-way
   swap and the pre-built 3-way chain (`fac004`, `fac007`, `fac008`).
4. Sign in as faculty1 and faculty2 in turn and confirm the swap.
5. As the warden, approve it. faculty1 now teaches UCS503 on Tue 10:00 in LT-103, and
   faculty2 teaches UCS301 on Mon 08:00 in LT-101.

The test `test_live_two_way_swap_between_demo_faculty_end_to_end` in
`code/backend/tests/test_slots.py` runs exactly this swap on the server.

## Run the tests

```powershell
.venv\Scripts\python -m pytest
```

The same tests run on GitHub for every push (see [Testing and CI](testing.md)).

## Change page styles (optional)

```powershell
cd code/frontend
npm install
npm run build
```

This rebuilds `code/frontend/public/assets/*.css` (one file per page, five pages) and copies the
fonts into `public/fonts/`. Commit the rebuilt CSS.

## Re-draw the diagrams (optional)

```powershell
.venv\Scripts\python diagrams/render.py
```

This sends the text of each `diagrams/*.puml` file to the public PlantUML server and
saves PNG and SVG images in `docs/diagrams/`. The PNG is also copied into `srs/figures/` for
the SRS. To redraw only some diagrams, name them: `diagrams/render.py er state-cycle`.

## Preview this documentation site (optional)

The site is published automatically from `master`. To preview locally, install the
tools listed in `.github/workflows/mkdocs.yml`, then run `mkdocs serve`.
On Windows, `docs/assets` and `docs/journals` are git *symlinks* (shortcuts to other
folders); they only work if Windows Developer Mode is on and you run
`git config core.symlinks true` before cloning. Otherwise rely on the published site.

## If something goes wrong

| What you see | What to do |
|---|---|
| `Can't reach the CampusSwap server` on a page | The server isn't running. Start it with the run command above. |
| `address already in use` / port 8000 busy | Another copy is running. Stop it, or use `run.py --port 8001`. |
| `ModuleNotFoundError` | Run commands from the repository root, using the `.venv` Python. |
| Pages look unstyled | Rebuild the CSS (see above) and hard-refresh the browser (`Ctrl+F5`). |
