"""Minimal case runner (task T033): runs a pipeline headless over labelled cases.

Each case runs in a fresh working directory (clean database and checkpoints) with the fixed
clock. A simulated reviewer answers every pause from the case's ground truth; its answers
count as review work, not as system errors. US6 adds graders and reports on top of this.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


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


class Pipeline(Protocol):
    def start(self, case: Case) -> dict[str, Any]: ...

    def resume(self, case: Case, payload: dict[str, Any]) -> dict[str, Any]: ...


Reviewer = Callable[[dict[str, Any], Case], dict[str, Any]]


@dataclass
class CaseResult:
    case: Case
    final_state: dict[str, Any]
    resumes: int
    error: str | None = None


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


class CaseRunner:
    def __init__(
        self,
        pipeline_factory: Callable[[Path], Pipeline],
        reviewer: Reviewer,
        *,
        workroot: Path | None = None,
        max_resumes: int = 10,
    ) -> None:
        self.pipeline_factory = pipeline_factory
        self.reviewer = reviewer
        self.workroot = workroot
        self.max_resumes = max_resumes

    def run(self, cases: list[Case]) -> list[CaseResult]:
        return [self._run_one(case) for case in cases]

    def _run_one(self, case: Case) -> CaseResult:
        workdir = Path(tempfile.mkdtemp(prefix=f"{case.case_id}-", dir=self.workroot))
        try:
            pipeline = self.pipeline_factory(workdir)
            state = pipeline.start(case)
            resumes = 0
            while "__interrupt__" in state:
                if resumes >= self.max_resumes:
                    return CaseResult(case, state, resumes, error="resume_limit")
                state = pipeline.resume(case, self.reviewer(state["__interrupt__"], case))
                resumes += 1
            return CaseResult(case, state, resumes)
        except Exception as exc:
            return CaseResult(case, {}, 0, error=type(exc).__name__)
        finally:
            if self.workroot is None:
                shutil.rmtree(workdir, ignore_errors=True)
