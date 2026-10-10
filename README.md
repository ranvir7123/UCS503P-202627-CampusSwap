# CampusSwap: Hostel Room Exchange (UCS503P 2026-27)

CampusSwap finds chains of hostel room swaps (A → B → C → A) using the
**Top Trading Cycles** algorithm, so more students get a room they prefer than
with direct 1:1 swaps alone.

Team: Jahnavi (1024240152), Ronit Saini (1024240102), Ranvir (1024240001),
Krishna Kapoor (1024240010).

## Run it

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r code/backend/requirements-dev.txt
.venv\Scripts\python code/backend/run.py --reset
```

Linux / macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r code/backend/requirements-dev.txt
.venv/bin/python code/backend/run.py --reset
```

Then open <http://127.0.0.1:8000>. Password for every demo account: `campus123`
(`warden@thapar.edu`, `student1@thapar.edu`, `student2@thapar.edu`, `student3@thapar.edu`).

Run the tests with `.venv\Scripts\python -m pytest` (or `.venv/bin/python -m pytest`).

## What is where

| Folder | Contents |
|---|---|
| `code/backend/engine/` | The TTC matching engine (pure Python, no database) |
| `code/backend/app/` | FastAPI server: tables, business rules, HTTP routes |
| `code/backend/tests/` | pytest tests for the engine and the server |
| `code/frontend/` | The four pages, their JavaScript and the Tailwind CSS build |
| `diagrams/` | PlantUML sources for the UML, data flow, architecture and ER diagrams |
| `srs/` | Software Requirements Specification (LaTeX, ready for Overleaf) and its figures |
| `docs/` | Documentation site (MkDocs), including the team study guide |
| `planning/` | Design spec and step-by-step build plans |
| `journals/` | Weekly journal of each team member |
| `project-proposal/`, `project-report-*` | LaTeX reports |

Full documentation: <https://ranvir7123.github.io/UCS503P-202627-CampusSwap/>
(published from `docs/` when `master` is updated).

This repository started from the course template
[tiet-ucs503/ucs503p-202627odd-template](https://github.com/tiet-ucs503/ucs503p-202627odd-template).
