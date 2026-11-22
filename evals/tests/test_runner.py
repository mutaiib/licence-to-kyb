"""The case runner: a clean directory per case, and one broken case never stops the rest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.runner import Case, load_cases, run_each

ROOT = Path(__file__).resolve().parents[2]


def cases(n: int) -> list[Case]:
    return load_cases(ROOT / "evals" / "cases" / "synthetic")[:n]


def test_every_case_gets_its_own_new_empty_directory() -> None:
    seen: list[tuple[Path, list[Path]]] = []

    def run_one(case: Case, workdir: Path) -> dict[str, Any]:
        seen.append((workdir, list(workdir.iterdir())))
        (workdir / "app.sqlite3").write_text("state")
        return {"ok": True}

    run_each(cases(3), run_one)

    assert len({w for w, _ in seen}) == 3
    assert all(contents == [] for _, contents in seen)
    assert not any(w.exists() for w, _ in seen)  # removed afterwards


def test_a_failing_case_is_recorded_and_the_others_still_run() -> None:
    def run_one(case: Case, workdir: Path) -> dict[str, Any]:
        if case.case_id == first.case_id:
            raise ValueError("broken document")
        return {"ok": True}

    three = cases(3)
    first = three[0]
    results = run_each(three, run_one)

    assert results[first.case_id] == {"error": "ValueError"}
    assert sum(r.get("ok", False) for r in results.values()) == 2


def test_cases_load_with_filters_on_split_and_group() -> None:
    cases = load_cases(ROOT / "evals" / "cases" / "synthetic", split="test")

    assert cases
    assert {c.split for c in cases} == {"test"}
