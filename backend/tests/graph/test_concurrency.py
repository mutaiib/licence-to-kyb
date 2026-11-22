"""Runs and reviewer actions that overlap in time (concurrency review, round 3).

A gate holds a run inside its extract step, so the tests can act while it is processing."""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from licence_kyb.api.routes_review import retry_in_background
from licence_kyb.api.routes_runs import process_in_background
from licence_kyb.testdata.answers import ScriptedTransport
from licence_kyb.testdata.catalogue import GROUPS, build
from tests.builders import make_pipeline


class Gated(ScriptedTransport):
    """Stops in the first extraction call until ``gate`` is set."""

    def __init__(self, labels: dict[str, Any]) -> None:
        super().__init__(labels)
        self.entered = threading.Event()
        self.gate = threading.Event()

    def send(self, req: Any) -> Any:
        if req.step == "extract_primary":
            self.entered.set()
            assert self.gate.wait(30)
        return super().send(req)


@pytest.fixture(scope="module")
def case(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=1) for g in GROUPS if g.name == "clean")
    return root, build(root, seed=7, groups=groups).cases[0]


def start(tmp_path: Path, case: Any, *, deadline_seconds: float = 600) -> tuple[Any, Gated, str]:
    root, labels = case
    transport = Gated(labels["expected_values"])
    pipeline = make_pipeline(
        tmp_path / "var", transport, registry_path=root / "data" / "registry_mock.json"
    )
    pipeline.ops.deadline_seconds = deadline_seconds
    run_id = pipeline.upload(
        (root / labels["document"]).read_bytes(), applicant_name=labels["applicant_name"]
    ).run_id
    return pipeline, transport, run_id


def test_a_run_still_processing_is_not_swept_and_finishes_normally(
    tmp_path: Path, case: Any
) -> None:
    """The deadline sweep is for runs nobody works on (after a crash). A run a thread still
    processes must not be moved to review behind its back and then overwritten."""
    pipeline, transport, run_id = start(tmp_path, case, deadline_seconds=0)
    worker = threading.Thread(target=process_in_background, args=(pipeline, run_id))
    worker.start()
    assert transport.entered.wait(30)

    pipeline.maintenance(retention_days=30)  # its deadline (0 s) has passed
    assert pipeline.db.get_run(run_id)["status"] == "processing"  # left alone: in flight
    transport.gate.set()
    worker.join(30)

    run = pipeline.db.get_run(run_id)
    assert run["status"] == pipeline.state(run_id)["status"] == "awaiting_submit"
    assert "processing_failed" not in run["reasons_json"]


def test_two_reviewer_actions_at_once_are_applied_one_after_the_other(
    tmp_path: Path, case: Any
) -> None:
    pipeline, transport, run_id = start(tmp_path, case)
    transport.gate.set()
    pipeline.process(run_id)
    version = pipeline.state(run_id)["form"]["version"]
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def reject(reason: str) -> None:
        action = {
            "kind": "review",
            "action_id": str(uuid.uuid4()),
            "reviewer": "r1",
            "form_version": version,
            "decisions": [],
            "reject_case": True,
            "reject_reason": reason,
        }
        barrier.wait()
        try:
            pipeline.act(run_id, action)
            outcomes.append("applied")
        except Exception as exc:
            outcomes.append(type(exc).__name__)

    tabs = [threading.Thread(target=reject, args=(r,)) for r in ("tab one", "tab two")]
    for tab in tabs:
        tab.start()
    for tab in tabs:
        tab.join(30)

    assert sorted(outcomes) == ["ActionRefused", "applied"]
    assert [e["action"] for e in pipeline.db.audit_events(run_id)].count("reject") == 1


def test_a_refused_retry_in_the_background_leaves_the_run_alone(tmp_path: Path, case: Any) -> None:
    """A second retry click is refused; it must not send a run to review as failed."""
    pipeline, transport, run_id = start(tmp_path, case)
    transport.gate.set()
    pipeline.process(run_id)  # ready: nothing to retry

    retry_in_background(
        pipeline, run_id, {"kind": "retry", "action_id": str(uuid.uuid4()), "reviewer": "r1"}
    )

    run = pipeline.db.get_run(run_id)
    assert run["status"] == "awaiting_submit"
    assert "processing_failed" not in run["reasons_json"]


def test_startup_gives_every_unfinished_run_a_new_deadline_before_processing_any(
    tmp_path: Path, case: Any
) -> None:
    pipeline, _transport, run_id = start(tmp_path, case, deadline_seconds=120)
    old = "2026-06-01T08:00:00+00:00"  # a deadline from before the restart
    pipeline.db.update_run(run_id, status="processing", deadline_at=old)
    seen: list[str] = []

    pipeline.ops.resume_on_startup(lambda rid: seen.append(pipeline.db.get_run(rid)["deadline_at"]))

    assert seen
    assert all(d != old for d in seen)
    assert pipeline.ops.late_runs() == []
