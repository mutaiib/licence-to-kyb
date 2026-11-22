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


def test_an_errored_case_counts_as_a_failure_not_as_a_missing_case() -> None:
    good = {**graded([], route="ready"), "route_ok": True}
    error = {"error": "RuntimeError", "split": "test"}

    summary = summarise({"a": good, "b": error, "c": dict(error)}, split="test")

    assert summary["errors"] == 2
    assert summary["route_accuracy"] == 1 / 3


def test_errors_from_the_other_split_are_not_counted() -> None:
    summary = summarise(
        {"a": graded([]), "b": {"error": "RuntimeError", "split": "calibration"}}, split="test"
    )

    assert summary["errors"] == 0


def test_a_missing_mix_bucket_is_named() -> None:
    summary = summarise({"a": graded([])}, split="test")

    assert set(summary["missing_mix_buckets"]) == {"scans_and_photos", "problem"}


def test_a_bad_document_routed_ready_is_counted() -> None:
    bad = {**graded([], route="ready"), "expected_route": ["reject"]}

    assert summarise({"a": bad}, split="test")["bad_documents_ready"] == 1
