"""Compare two eval reports (US6, T094): list exactly the cases whose route, reason codes,
field results or read values changed. Also shows the resolver on/off difference.

    uv --project backend run python -m evals.compare [BEFORE.json AFTER.json]

With no arguments, it compares ``evals/reports/baseline.json`` with the newest report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPORTS = Path(__file__).parent / "reports"


def changed_cases(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    old, new = before["cases"], after["cases"]
    for case_id in sorted(set(old) | set(new)):
        a, b = old.get(case_id), new.get(case_id)
        if a is None or b is None:
            changes[case_id] = {"only_in": "after" if a is None else "before"}
            continue
        change: dict[str, Any] = {}
        if a["route"] != b["route"]:
            change["route"] = (a["route"], b["route"])
        if sorted(a["reason_codes"]) != sorted(b["reason_codes"]):
            change["reason_codes"] = (sorted(a["reason_codes"]), sorted(b["reason_codes"]))
        fields = {
            f: (a["fields"].get(f), b["fields"].get(f))
            for f in set(a["fields"]) | set(b["fields"])
            if a["fields"].get(f) != b["fields"].get(f)
        }
        if fields:
            change["fields"] = fields
        # A value can change while staying wrong: the reading itself changed.
        old_values, new_values = a.get("values", {}), b.get("values", {})
        values = {
            f: (old_values.get(f), new_values.get(f))
            for f in sorted(set(old_values) | set(new_values))
            if old_values.get(f) != new_values.get(f)
        }
        if values:
            change["values"] = values
        if change:
            changes[case_id] = change
    return changes


def newest_report(reports: Path) -> Path:
    """The report with the latest date in its metadata. Names do not sort by time: a
    timestamped name sorts before a word such as ``scripted-baseline``."""
    paths = list(reports.glob("*/report.json"))
    if not paths:
        sys.exit(f"no reports in {reports}: run make eval first")
    return max(paths, key=lambda p: json.loads(p.read_text("utf-8"))["meta"]["date"])


def main() -> None:
    """Print the cases that changed. Exits 1 when any changed, so CI can stop on it."""
    two_paths_given = len(sys.argv) == 3  # noqa: PLR2004 - the program name and two paths
    if two_paths_given:
        before_path, after_path = Path(sys.argv[1]), Path(sys.argv[2])
    else:
        before_path, after_path = REPORTS / "baseline.json", newest_report(REPORTS)
    before = json.loads(before_path.read_text("utf-8"))
    after = json.loads(after_path.read_text("utf-8"))
    changes = changed_cases(before, after)
    print(f"{len(changes)} cases changed ({before_path} → {after_path})")
    for case_id, change in changes.items():
        print(f"- {case_id}: {json.dumps(change, ensure_ascii=False)}")
    if changes:
        sys.exit(1)


if __name__ == "__main__":
    main()
