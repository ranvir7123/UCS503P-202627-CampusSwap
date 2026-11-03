"""Run the whole test suite and write the report's test tables from the real result.

    python project-report-final/tools/make_test_tables.py

Writes (inside project-report-final/generated/):
  testcases.tex  the test-case table (TC-01 ...), actual and result from this run
  alltests.tex   every automated test, grouped by file, with its result
  summary.tex    \\newcommand values: total, passed, failed, seconds, date
  junit.xml      pytest's own record of the run
Stops with an error if a case names a test that does not exist.
"""
from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE.parent / "generated"
sys.path.insert(0, str(HERE))
from cases import CASES  # noqa: E402


def tex(text: str) -> str:
    out = str(text)
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                 ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}"),
                 ("<->", r"$\leftrightarrow$"), ("->", r"$\rightarrow$"), ("<", r"\textless{}"), (">", r"\textgreater{}")]:
        out = out.replace(a, b) if a != "\\" else out.replace(a, "\x00")
    return out.replace("\x00", r"\textbackslash{}")


def run_tests() -> Path:
    OUT.mkdir(exist_ok=True)
    xml = OUT / "junit.xml"
    python = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run([str(python), "-m", "pytest", "-q", f"--junitxml={xml}"], cwd=ROOT, check=False)
    return xml


def read_results(xml: Path) -> tuple[dict[str, dict], float]:
    root = ET.parse(xml).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    results = {}
    for case in suite.iter("testcase"):
        module = case.get("classname", "").split(".")[-1]
        problem = case.find("failure") if case.find("failure") is not None else case.find("error")
        skipped = case.find("skipped") is not None
        results[f"{module}::{case.get('name')}"] = {
            "passed": problem is None and not skipped, "skipped": skipped,
            "message": (problem.get("message") or "").splitlines()[0][:120] if problem is not None else "",
            "time": float(case.get("time", 0)),
        }
    return results, float(suite.get("time", 0))


def main() -> None:
    results, seconds = read_results(run_tests())
    missing = [t for c in CASES for t in c[5] if t not in results]
    if missing:
        sys.exit("These tests are named in cases.py but did not run:\n  " + "\n  ".join(missing))

    rows = []
    for cid, reqs, steps, given, expected, tests in CASES:
        bad = [t for t in tests if not results[t]["passed"]]
        actual = "As expected" if not bad else "Failed: " + results[bad[0]]["message"]
        verdict = r"\textbf{Pass}" if not bad else r"\textbf{Fail}"
        names = r"\newline ".join(r"\texttt{" + tex(t.split("::")[1]) + "}" for t in tests)
        rows.append(f"{cid} & {tex(reqs)} & {tex(steps)} & {tex(given)} & {tex(expected)} & "
                    f"{tex(actual)} & {verdict} \\\\\n\\multicolumn{{7}}{{@{{}}l}}{{\\scriptsize\\itshape Automated by: "
                    f"{names.replace(chr(92) + 'newline ', ', ')}}} \\\\ \\midrule")
    (OUT / "testcases.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")

    by_file = defaultdict(list)
    for name, r in sorted(results.items()):
        module, test = name.split("::", 1)
        by_file[module].append((test, r))
    lines = []
    for module, tests in by_file.items():
        lines.append(r"\multicolumn{3}{@{}l}{\textbf{\texttt{" + tex(module) + ".py}}} \\\\ \\midrule")
        for test, r in tests:
            state = "Pass" if r["passed"] else ("Skipped" if r["skipped"] else "Fail")
            lines.append(r"\texttt{" + tex(test) + "} & " + f"{r['time']:.3f} & {state} \\\\")
        lines.append(r"\midrule")
    (OUT / "alltests.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    total = len(results)
    passed = sum(r["passed"] for r in results.values())
    (OUT / "summary.tex").write_text(
        f"\\newcommand{{\\TestsTotal}}{{{total}}}\n\\newcommand{{\\TestsPassed}}{{{passed}}}\n"
        f"\\newcommand{{\\TestsFailed}}{{{total - passed}}}\n\\newcommand{{\\TestsSeconds}}{{{seconds:.1f}}}\n"
        f"\\newcommand{{\\TestsDate}}{{{datetime.now():%d %B %Y}}}\n"
        f"\\newcommand{{\\CasesTotal}}{{{len(CASES)}}}\n", encoding="utf-8")
    print(f"{passed} of {total} tests passed in {seconds:.1f} s; {len(CASES)} test cases written to {OUT}")


if __name__ == "__main__":
    main()
