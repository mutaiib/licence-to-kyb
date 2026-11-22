"""How a run reached its result, and today's rates (US5; FR-032; contracts/http-api.md).

Both answers hold no personal data: the trace reads only non-personal span columns
(``Tracer.spans_for``), and the summary holds only counts and money.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from licence_kyb.api.schemas import ErrorOut, SpanView, SummaryOut, TraceOut
from licence_kyb.pipeline import Pipeline

router = APIRouter(prefix="/api", tags=["trace"])


def _pipeline(request: Request) -> Pipeline:
    pipeline: Pipeline = request.app.state.pipeline
    return pipeline


@router.get("/runs/{run_id}/trace", response_model=TraceOut, responses={404: {"model": ErrorOut}})
def get_trace(run_id: str, request: Request) -> TraceOut | JSONResponse:
    pipeline = _pipeline(request)
    if pipeline.db.get_run(run_id) is None:
        return JSONResponse({"code": "not_found"}, status_code=404)
    spans = [
        SpanView(
            span_id=s["span_id"],
            parent_id=s["parent_id"],
            kind=s["kind"],
            name=s["name"],
            latency_ms=s["latency_ms"],
            input_tokens=s["input_tokens"],
            output_tokens=s["output_tokens"],
            cache_read_tokens=s["cache_read_tokens"],
            cost_usd=s["cost_usd"],
            model=s["serving_model"],
            summary=s["error_code"] or "ok",
        )
        for s in pipeline.tracer.spans_for(run_id)
    ]
    return TraceOut(spans=spans)


@router.get("/metrics/summary", response_model=SummaryOut)
def get_summary(request: Request) -> SummaryOut:
    pipeline = _pipeline(request)
    today = datetime.now(UTC).date().isoformat()  # created_at is stored in UTC
    counts = pipeline.db.day_summary(today)
    runs = counts["runs"]

    def rate(n: int) -> float:
        return n / runs if runs else 0.0

    return SummaryOut(
        runs=runs,
        refusal_rate=rate(counts["refused"]),
        fallback_rate=rate(counts["fallbacks"]),
        review_rate=rate(counts["reviewed"]),
        cost_usd=round(counts["cost_usd"], 4),
        budget_tokens_remaining=pipeline.deps.llm.budget.remaining,
    )
