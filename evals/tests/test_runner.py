"""The case runner: clean storage per case, simulated reviewer, bounded resumes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.runner import Case, CaseRunner, load_cases

ROOT = Path(__file__).resolve().parents[2]


class FakePipeline:
    """Pauses once for review, then finishes; records the directory it was given."""

    instances: list[FakePipeline] = []

    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        FakePipeline.instances.append(self)

    def start(self, case: Case) -> dict[str, Any]:
        return {"__interrupt__": {"flagged": ["expiry_date"]}, "run_id": case.case_id}

    def resume(self, case: Case, payload: dict[str, Any]) -> dict[str, Any]:
        return {"run_id": case.case_id, "status": "done", "answer": payload}


class LoopingPipeline(FakePipeline):
    def resume(self, case: Case, payload: dict[str, Any]) -> dict[str, Any]:
        return {"__interrupt__": {"flagged": ["x"]}}


def approve_all(payload: dict[str, Any], case: Case) -> dict[str, Any]:
    return {"decisions": [{"field": f, "action": "approve"} for f in payload["flagged"]]}


def test_every_case_runs_in_its_own_clean_directory(tmp_path: Path) -> None:
    FakePipeline.instances.clear()
    cases = load_cases(ROOT / "evals" / "cases" / "synthetic", groups={"clean"})[:3]

    CaseRunner(FakePipeline, approve_all, workroot=tmp_path).run(cases)

    dirs = [p.workdir for p in FakePipeline.instances]
    assert len(set(dirs)) == 3


def test_the_simulated_reviewer_answers_each_pause(tmp_path: Path) -> None:
    case = load_cases(ROOT / "evals" / "cases" / "synthetic", groups={"near_expiry"})[0]

    (result,) = CaseRunner(FakePipeline, approve_all, workroot=tmp_path).run([case])

    assert result.final_state["status"] == "done"
    assert result.resumes == 1
    assert result.error is None


def test_a_run_that_never_finishes_stops_at_the_resume_limit(tmp_path: Path) -> None:
    case = load_cases(ROOT / "evals" / "cases" / "synthetic", groups={"clean"})[0]

    (result,) = CaseRunner(LoopingPipeline, approve_all, workroot=tmp_path, max_resumes=3).run(
        [case]
    )

    assert result.resumes == 3
    assert result.error == "resume_limit"


def test_cases_load_with_filters_on_split_and_group() -> None:
    cases = load_cases(ROOT / "evals" / "cases" / "synthetic", split="test")

    assert cases
    assert {c.split for c in cases} == {"test"}
