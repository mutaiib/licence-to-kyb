"""Labelled cases and a runner that gives each case a clean directory (T033, US6).

The eval (``evals/run.py``) grades each case on its state at the first pause.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Case:
    case_id: str
    group: str
    source: str
    document: str
    mime: str
    applicant_name: str
    expected_route: tuple[str, ...]
    expected_reason_codes: tuple[str, ...]
    expected_values: dict[str, Any] | None
    split: str
    mix_bucket: str
    authority: str | None = None
    twin_of: str | None = None
    live_eval_only: bool = False

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Case:
        return cls(
            case_id=data["case_id"],
            group=data["group"],
            source=data["source"],
            document=data["document"],
            mime=data["mime"],
            applicant_name=data["applicant_name"],
            expected_route=tuple(data["expected_route"]),
            expected_reason_codes=tuple(data["expected_reason_codes"]),
            expected_values=data["expected_values"],
            split=data["split"],
            mix_bucket=data["mix_bucket"],
            authority=data.get("authority"),
            twin_of=data.get("twin_of"),
            live_eval_only=bool(data.get("live_eval_only", False)),
        )


def run_each(
    cases: list[Case], run_one: Callable[[Case, Path], dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Run each case in its own new, empty directory (a clean database and checkpoints).
    A case that fails is recorded with its error type; the other cases still run."""
    results: dict[str, dict[str, Any]] = {}
    for case in cases:
        with tempfile.TemporaryDirectory(prefix=f"{case.case_id}-") as workdir:
            try:
                results[case.case_id] = run_one(case, Path(workdir))
            except Exception as exc:
                # Keep the split, so the error counts as a failure in that split's report.
                results[case.case_id] = {"error": type(exc).__name__, "split": case.split}
    return results


def load_cases(
    directory: Path, *, split: str | None = None, groups: set[str] | None = None
) -> list[Case]:
    cases = [
        Case.from_json(json.loads(path.read_text("utf-8")))
        for path in sorted(directory.glob("*.json"))
    ]
    return [
        c
        for c in cases
        if (split is None or c.split == split) and (groups is None or c.group in groups)
    ]
