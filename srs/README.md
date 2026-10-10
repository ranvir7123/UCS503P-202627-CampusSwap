# CampusSwap SRS

The Software Requirements Specification for CampusSwap, in LaTeX.

| File | What it is |
|---|---|
| `main.tex` | The whole document |
| `figures/` | Every image the document uses |
| `main.pdf` | The built document |

## Before you submit

Open `main.tex` and find the block marked `EDIT HERE` near the top. Replace each red
`\FillMe{...}` with the real text (the teacher's name, designation and department), and add
surnames to the team names if you want them. Anything still in red square brackets on the
cover has not been filled in.

## Build it on Overleaf

1. Zip this folder (`main.tex` and `figures/`).
2. In Overleaf: **New Project → Upload Project**, choose the zip.
3. Compile. The default compiler (pdfLaTeX) is fine.

## Where the images come from

- **Diagrams** (`use-case`, `class`, `class-services`, `sequence`, `activity`,
  `state-request`, `state-cycle`, `architecture`, `dfd-context`, `dfd-level1`, `er`):
  drawn from the PlantUML files in `../diagrams/`. After editing one, run
  `python diagrams/render.py` from the repository root; it updates both `docs/diagrams/`
  and this folder.
- **Screenshots** (`ui-*.png`): taken from the running prototype on its made-up demo data,
  after one real matching round, at 1440 × 900 (desktop) and 390 × 844 (phone).
- **TIET logo**: copied from `../assets/tiet-logo.png`.
