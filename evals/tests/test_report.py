"""The report summary: a failure in processing is counted, never hidden by another metric."""

from __future__ import annotations

from typing import Any

import pytest

from evals.graders import wilson_interval
from evals.run import CountingTransport, summarise
from licence_kyb.llm.client import ModelRequest, ModelResponse, Usage


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


def test_the_headline_numbers_on_a_known_set() -> None:
    """Review rate weighted by the realistic mix (clean 70%, scans 20%, problem 10%), the
    Wilson interval of ready precision, and the mean cost per document."""

    def case(route: str, bucket: str, cost: float, critical_ok: bool = True) -> dict[str, Any]:
        return {
            **graded([], route=route),
            "mix_bucket": bucket,
            "cost_usd": cost,
            "critical_ok": critical_ok,
        }

    summary = summarise(
        {
            "a": case("ready", "clean", 0.10),
            "b": case("needs_review", "clean", 0.20),
            "c": case("needs_review", "scans_and_photos", 0.30),
            "d": case("ready", "problem", 0.40, critical_ok=False),
        },
        split="test",
    )

    # clean: 1 of 2 to review; scans: 1 of 1; problem: 0 of 1.
    assert summary["review_rate_mixed"] == pytest.approx(0.7 * 0.5 + 0.2 * 1.0 + 0.1 * 0.0)
    assert summary["ready_precision"]["ready"] == 2
    assert summary["ready_precision"]["correct"] == 1
    low, high = wilson_interval(1, 2)
    assert summary["ready_precision"]["wilson_95"] == [round(low, 4), round(high, 4)]
    assert summary["cost_per_document_usd"] == pytest.approx(0.25)


def test_the_report_names_the_models_that_served_each_step() -> None:
    """A server-side fallback can serve a different model than the one asked for."""

    class Inner:
        def send(self, req: ModelRequest) -> ModelResponse:
            served = "claude-sonnet-5-5" if req.step == "extract_primary" else req.model
            return ModelResponse(
                content=[], parsed=None, stop_reason="end_turn", serving_model=served, usage=Usage()
            )

    counting = CountingTransport(Inner())
    for step in ("route", "extract_primary"):
        counting.send(
            ModelRequest(
                step=step,
                model="claude-opus-5-5",
                effort="low",
                max_tokens=10,
                system="s",
                messages=[],
            )
        )

    assert counting.served() == {
        "route": "claude-opus-5-5",
        "extract_primary": "claude-sonnet-5-5",
    }
