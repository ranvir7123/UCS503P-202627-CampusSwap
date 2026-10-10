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
- Open <http://127.0.0.1:8000>. The interactive API reference is at
  <http://127.0.0.1:8000/docs>.
- Stop the server with `Ctrl+C`.

### Demo accounts (password `campus123` for all)

| Email | Role | Room |
|---|---|---|
| `warden@thapar.edu` | Hostel staff | — |
| `student1@thapar.edu` | Student | Hostel M, A-101 |
| `student2@thapar.edu` | Student | Hostel M, B-101 |
| `student3@thapar.edu` | Student | Hostel M, A-201 |

The demo data already has **12 open requests** built so that TTC finds one 2-way,
one 3-way and one 4-way chain and leaves 3 students unmatched (Match Yield 75%).
Direct 1:1 swaps alone match only 2 of those 12 (16.7%).

## The 3-minute lab demo

1. Log in as **student1**, open *Explore Rooms*, filter to Hostel M, rank **B-101**, submit.
   Note the tracking ID.
2. Do the same as **student2** ranking **A-201**, and **student3** ranking **A-101**.
   These three requests form a 3-way loop.
3. Log in as the **warden**. Press **Settings → Dry run**, then *Compare on the current pool*
   to show TTC vs 1:1 on the same students. Then turn dry run off and press
   **Run TTC Matching Round**. Walk through the step-by-step trace.
4. Log in as student1, 2 and 3 in turn and press **Confirm swap** on the dashboard.
5. Back as the warden, press **Approve swap** on the confirmed chain.
   Student1's dashboard now shows room B-101.

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

This rebuilds `code/frontend/public/assets/*.css` (one file per page) and copies the
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
