"""The report summary: a failure in processing is counted, never hidden by another metric."""

from __future__ import annotations

from typing import Any

from evals.run import summarise


def graded(reason_codes: list[str], route: str = "needs_review") -> dict[str, Any]:
    return {
        "route": route,
        "route_ok": route == "ready",
        "reason_codes": reason_codes,
        "reasons_ok": True,  # a clean case labels no reasons, so any extra code passes
        "fields": {"licence_number": True},
        "critical_ok": True,
        "safety": [],
        "cost_usd": 0.0,
        "stages_ms": {},
        "split": "test",
        "mix_bucket": "clean",
    }


def test_a_run_that_stopped_in_processing_is_counted() -> None:
    summary = summarise(
        {"a": graded(["processing_failed"]), "b": graded([], route="ready")}, split="test"
    )

    assert summary["processing_failures"] == 1
    assert summary["reason_accuracy"] == 1.0  # why the separate count is needed


def test_no_failures_counts_zero() -> None:
    summary = summarise({"a": graded(["near_expiry"])}, split="test")

    assert summary["processing_failures"] == 0
