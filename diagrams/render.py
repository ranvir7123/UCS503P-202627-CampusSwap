"""Render diagrams/*.puml to PNG and SVG using the public PlantUML server.

    python diagrams/render.py              # every diagram
    python diagrams/render.py er dfd-level1  # only these (file names without .puml)

Only the diagram text is sent (hex-encoded in the URL). No Java needed.
PNG and SVG go to docs/diagrams/ for the docs site. The PNG is also copied to
srs/figures/ so the SRS folder can be zipped and built on Overleaf on its own.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

SERVER = "https://www.plantuml.com/plantuml"
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "docs" / "diagrams"
SRS_FIGURES = HERE.parent / "srs" / "figures"


def fetch(kind: str, source: str) -> bytes:
    url = f"{SERVER}/{kind}/~h{source.encode('utf-8').hex()}"
    request = urllib.request.Request(url, headers={"User-Agent": "campusswap-diagrams"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main(names: list[str]) -> int:
    OUT.mkdir(exist_ok=True)
    SRS_FIGURES.mkdir(parents=True, exist_ok=True)
    pumls = sorted(HERE.glob("*.puml"))
    if names:
        missing = set(names) - {p.stem for p in pumls}
        if missing:
            print(f"No such diagram: {', '.join(sorted(missing))}")
            return 1
        pumls = [p for p in pumls if p.stem in names]
    failed = False
    for puml in pumls:
        source = puml.read_text(encoding="utf-8")
        for kind in ("png", "svg"):
            data = fetch(kind, source)
            targets = [OUT / f"{puml.stem}.{kind}"]
            if kind == "png":
                targets.append(SRS_FIGURES / f"{puml.stem}.png")
            for target in targets:
                target.write_bytes(data)
                print(f"{target.relative_to(HERE.parent)}  {len(data):,} bytes")
            # The server still returns an image when the diagram has a syntax error; flag it.
            if kind == "svg" and b"Syntax Error" in data:
                failed = True
                print(f"SYNTAX ERROR in {puml.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
