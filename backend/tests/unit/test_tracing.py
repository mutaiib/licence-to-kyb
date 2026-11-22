"""Tracing: every span is stored, errors are recorded, the trace API never leaks PII."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from licence_kyb.store.db import Database
from licence_kyb.tracing import Tracer


@pytest.fixture
def tracer(tmp_path: Path) -> Tracer:
    db = Database(tmp_path / "app.sqlite3")
    db.migrate()
    db.create_run(run_id="r1", file_sha256="sha", applicant_name="Acme")
    return Tracer(db)


def test_nested_spans_are_stored_with_their_parent(tracer: Tracer) -> None:
    with (
        tracer.span("step", "extract", run_id="r1") as step,
        tracer.span("model_call", "extract_primary", run_id="r1", parent=step) as call,
    ):
        call.requested_model = call.serving_model = "claude-opus-5-5"
        call.input_tokens, call.output_tokens = 10_000, 4_000

    spans = tracer.spans_for("r1")
    assert len(spans) == 2
    by_name = {s["name"]: s for s in spans}
    assert by_name["extract_primary"]["parent_id"] == by_name["extract"]["span_id"]
    assert by_name["extract_primary"]["input_tokens"] == 10_000


def test_a_failing_step_records_its_error_and_still_raises(tracer: Tracer) -> None:
    with (
        pytest.raises(RuntimeError),
        tracer.span("tool_call", "licence_lookup_registry", run_id="r1"),
    ):
        raise RuntimeError("timeout")

    (span,) = tracer.spans_for("r1")
    assert span["error_code"] == "RuntimeError"


def test_the_trace_api_never_returns_raw_tool_payloads(tracer: Tracer) -> None:
    with tracer.span("tool_call", "licence_ocr_region", run_id="r1") as span:
        span.raw_result = {"people": [{"name": "Ahmed Al Mansoori"}]}
        span.model_view = "Ahmed Al Mansoori, owner"

    out = json.dumps(tracer.spans_for("r1"), ensure_ascii=False)
    assert "Ahmed Al Mansoori" not in out


def test_model_call_spans_map_to_opentelemetry_genai_attributes(tracer: Tracer) -> None:
    with tracer.span("model_call", "route", run_id="r1") as span:
        span.requested_model, span.serving_model = "claude-opus-5-5", "claude-opus-5-5"
        span.input_tokens = 3000

    attrs = span.otel_attributes()
    assert attrs["gen_ai.request.model"] == "claude-opus-5-5"
    assert attrs["gen_ai.usage.input_tokens"] == 3000
