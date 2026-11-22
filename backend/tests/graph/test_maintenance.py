"""Scheduled maintenance (FR-030, FR-036, FR-039, FR-040): late runs go to review in the
database and in the graph, old runs are deleted everywhere, and the daily budget is daily."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from licence_kyb.clock import FixedClock
from licence_kyb.graph import thread_config
from licence_kyb.llm.client import BudgetExhaustedError, DailyBudget
from licence_kyb.testdata.answers import ScriptedTransport
from licence_kyb.testdata.catalogue import GROUPS, build
from tests.builders import first_case, make_pipeline


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=1) for g in GROUPS if g.name == "clean")
    return root, build(root, seed=13, groups=groups).cases


def pipeline_for(tmp_path: Path, catalogue: Any) -> tuple[Any, str]:
    root, cases = catalogue
    case = first_case(cases, "clean")
    pipeline = make_pipeline(
        tmp_path / "var",
        ScriptedTransport(case["expected_values"]),
        registry_path=root / "data" / "registry_mock.json",
    )
    run_id = pipeline.upload(
        (root / case["document"]).read_bytes(), applicant_name=case["applicant_name"]
    ).run_id
    return pipeline, run_id


def test_a_late_run_goes_to_review_and_can_be_retried(tmp_path: Path, catalogue: Any) -> None:
    pipeline, run_id = pipeline_for(tmp_path, catalogue)
    late = (pipeline.ops.clock.now() - timedelta(minutes=1)).isoformat()
    pipeline.db.update_run(run_id, status="processing", deadline_at=late)

    pipeline.maintenance(retention_days=30)

    assert pipeline.db.get_run(run_id)["status"] == "awaiting_review"
    pipeline.check(run_id, {"kind": "retry", "action_id": "a1", "reviewer": "r1"})  # no refusal


def test_a_run_past_retention_is_deleted_with_its_files_and_checkpoints(
    tmp_path: Path, catalogue: Any
) -> None:
    pipeline, run_id = pipeline_for(tmp_path, catalogue)
    pipeline.process(run_id)
    # created_at is the real upload time, so the clock moves 31 days past the real time.
    pipeline.ops.clock = FixedClock(datetime.now(UTC) + timedelta(days=31))

    pipeline.maintenance(retention_days=30)

    assert pipeline.db.get_run(run_id) is None
    assert not (pipeline.deps.data_dir / "files" / run_id).exists()
    assert pipeline.graph.get_state(thread_config(run_id)).values == {}


def test_the_daily_token_budget_starts_again_on_a_new_day() -> None:
    day = [date(2026, 6, 1)]
    budget = DailyBudget(100, today=lambda: day[0])
    budget.charge(100)
    with pytest.raises(BudgetExhaustedError):
        budget.check(1)

    day[0] = date(2026, 6, 2)

    budget.check(1)  # no error
    assert budget.remaining == 100
