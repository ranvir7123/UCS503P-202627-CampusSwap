# P4: Data, diagrams and delivery

You own how data is stored, the UML diagrams, and everything that makes the project
deliverable: demo data, CI, this docs site and the report.

## Your files

| File | What it does |
|---|---|
| `code/backend/app/models.py` | Every database table (SQLAlchemy) |
| `code/backend/app/db.py` | Connects to SQLite; switches foreign keys on |
| `code/backend/seed.py` | Synthetic demo data with a known result |
| `diagrams/*.puml`, `diagrams/render.py` | The four UML diagrams and the script that draws them |
| `.github/workflows/tests.yml` | Runs all tests on every push (CI) |
| `.github/workflows/mkdocs.yml`, `mkdocs.yml`, `docs/` | Publishes this site from `master` |
| `project-report-prototype-stage/` | The TIET LaTeX report |

## The data model in one breath

A **hostel** has **rooms**; a room has 1–3 **seats** (beds); each seat has at most one
**student**. A student makes a **swap request** offering their seat, with 1–5 ranked
**preferences** (rooms). A **match run** finds **swap cycles**; each cycle has 2 or more
**cycle members**, each giving one seat and receiving the next member's seat. **Events**
log what happened; **login sessions** record who is signed in.

Full tables and status changes: [Data model](../data-model.md).

**Why seats, not rooms?** In a double room, only one of the two students moves. Swapping
whole rooms would drag the roommate along.

**Why SQLite?** A real SQL database with transactions, stored in one file, nothing to
install for the lab. SQLAlchemy means switching to PostgreSQL is a one-line change.

## Demo data (`seed.py`)

4 hostels (J, M for men; K, N for women), 72 rooms, a student in every seat, the warden,
and 12 open requests built to give a known answer: one 2-way, one 3-way, one 4-way chain,
3 unmatched (75% Match Yield; 16.7% with 1:1 swaps only). Three demo students with no
request are left for the live 3-way demo. Everything is made up, including roll numbers
(`D24xxxx`), so it can never be confused with real student records.

## The diagrams

See [Diagrams](../diagrams.md) for each image and the reason behind every relationship.
Be ready to explain:

- **«include»** = always happens as part of the other use case (submit always validates).
- **«extend»** = optional variation of another use case (a dry run extends running a round).
- **Composition** (filled diamond) = the part can't exist without the whole (a seat
  without its room). **Association** (plain line) = linked but independent (a student and
  a seat). **Generalisation** (hollow triangle) = "is a kind of" (a Student is a User).
- **Multiplicity** such as `1..5` = "at least 1, at most 5" (preferences per request).
- **Sequence diagram** fragments: **loop** repeats (each member confirms), **alt** chooses
  one branch (all accepted vs. someone declined).
- **Activity diagram swimlanes** show who does each step (Student / System / Warden).

To change a diagram, edit the `.puml` file and run `python diagrams/render.py`. It sends
only the diagram text to the public PlantUML server and saves PNG and SVG files in `docs/diagrams/`.

## Delivery

- **CI:** every push runs 90 tests on GitHub (`tests.yml`). Green tick = all pass.
- **Docs site:** pushing to `master` rebuilds and publishes it through the template's
  `mkdocs.yml` workflow (GitHub Pages must be switched on in the repository settings,
  using the `gh-pages` branch).
- **Branches:** work happens on `prototype` and reaches `master` through a pull request, so
  the tests run before anything is merged.
- **Report:** the TIET LaTeX template goes in `project-report-prototype-stage/`, reusing
  the diagram images from `docs/diagrams/`.

## Questions you may get

**Why did you draw these four diagrams?** Use Case shows *who does what*; Class shows the
*structure*; Sequence shows *one flow in time*; Activity shows the *process with its
branches*. Together they cover structure and behaviour.

**What's the difference between «include» and «extend»?** Include is mandatory and always
happens; extend is optional and only happens in some cases.

**Why is Seat–Student an association and not composition?** Students exist on their own and
move between seats; a seat doesn't own a student.

**How do you know the demo numbers are real?** `test_matching_service.py` asserts the seeded
pool gives exactly one 2-, 3- and 4-way chain, 9 of 12 matched, 75%.

**What does CI stand for, and what does it give us?** Continuous integration: GitHub runs
all tests on every push, so a broken change shows up immediately, before it's merged.

## If the demo breaks

- Wrong or messy data → `python code/backend/run.py --reset`.
- A diagram is out of date → edit its `.puml` and re-render.
