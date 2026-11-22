"""The eval report (US6, T093; FR-034, FR-044; research R8a).

    uv --project backend run python -m evals.run --model scripted     # offline, no cost
    MODEL_PROFILE=local uv --project backend run python -m evals.run --model profile
    uv --project backend run python -m evals.run --model profile --no-resolver

Each case runs the whole pipeline on its document and is graded on its state at the first
pause (route, reasons, values, confidence). The review flow is covered by the US2 tests.

- ``--model scripted`` answers from the case labels: it checks routing and rules, never the
  model's reading, and the report says so.
- ``--model profile`` calls the models of ``MODEL_PROFILE`` (ADR-004). The report names them.

Output, in ``evals/reports/<name>/``: ``report.md``, ``report.json`` (input for
``evals.compare``) and ``signals.jsonl`` (input for ``scripts/calibrate.py``).
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from evals.graders import (
    CRITICAL_FIELDS,
    field_grades,
    reasons_correct,
    route_correct,
    safety_violations,
    wilson_interval,
)
from evals.runner import Case, load_cases, run_each
from licence_kyb.clock import FixedClock
from licence_kyb.config import DATA_DIR, REPO_ROOT, Settings, active_profile, active_profile_name
from licence_kyb.llm.client import DailyBudget, LLMClient, ModelRequest, ModelResponse, Transport
from licence_kyb.llm.select import profile_transport
from licence_kyb.pipeline import Deps, Pipeline
from licence_kyb.registry import MockRegistry
from licence_kyb.security import Cipher
from licence_kyb.testdata.answers import LabelDemoTransport

CASES = REPO_ROOT / "evals" / "cases" / "synthetic"
PUBLIC = REPO_ROOT / "evals" / "cases" / "public"
"""Real licences their companies publish: downloaded at eval time, never committed."""
REPORTS = REPO_ROOT / "evals" / "reports"
MIX = {"clean": 0.7, "scans_and_photos": 0.2, "problem": 0.1}
"""The realistic mix for the review rate (research R8a)."""
STAGE_BUDGET_MS = {
    "preprocess": 8000,
    "route": 4000,
    "extract": 18000,
    "validate": 1000,
    "resolve": 45000,
}
"""p95 budget per stage (plan.md, "Latency budget")."""
PASS3_CASES = 30


# ------------------------------------------------------------------ running one case
@dataclass
class CountingTransport:
    """Counts the replies that stopped at the token limit (a report metric)."""

    inner: Transport
    calls: int = 0
    max_token_stops: int = 0

    def send(self, req: ModelRequest) -> ModelResponse:
        response = self.inner.send(req)
        self.calls += 1
        self.max_token_stops += response.stop_reason == "max_tokens"
        return response


def grade(case: Case, state: dict[str, Any], pipeline: Pipeline) -> dict[str, Any]:
    route = state.get("decision", {}).get("route")
    codes = {r["code"] for r in state.get("reasons", [])}
    grades = field_grades(case.expected_values or {}, state.get("extraction", {}))
    fields = {
        g.field if g.element is None else f"{g.field}[{g.element}]": g.correct for g in grades
    }
    critical_ok = all(g.correct for g in grades if g.field in CRITICAL_FIELDS)
    run_id = state["run_id"]
    with pipeline.db.connect() as conn:
        submissions = [
            dict(r)
            for r in conn.execute(
                "SELECT form_version FROM submissions WHERE run_id = ?", (run_id,)
            )
        ]
        approvals = [
            dict(r)
            for r in conn.execute("SELECT form_version FROM approvals WHERE run_id = ?", (run_id,))
        ]
    stages = {
        s["name"]: s["latency_ms"] for s in pipeline.tracer.spans_for(run_id) if s["kind"] == "step"
    }
    cost, _ = pipeline.tracer.run_totals(run_id)
    signals = [
        {"field": f, "split": case.split, "signals": c["signals"], "correct": fields.get(f, False)}
        for f, c in state.get("confidence", {}).items()
        if f in fields
    ]
    return {
        "route": route,
        "route_ok": route_correct(case.expected_route, route),
        "reason_codes": sorted(codes),
        "reasons_ok": reasons_correct(case.expected_reason_codes, codes),
        "fields": fields,
        "critical_ok": critical_ok,
        "safety": safety_violations(submissions, approvals),
        "cost_usd": cost,
        "stages_ms": stages,
        "signals": signals,
        "split": case.split,
        "mix_bucket": case.mix_bucket,
    }


def run_cases(cases: list[Case], transport: Transport, *, resolver: bool) -> dict[str, Any]:
    """Run each case to its first pause, in its own clean directory, and grade it."""
    key = Fernet.generate_key().decode()

    def run_one(case: Case, workdir: Path) -> dict[str, Any]:
        pipeline = Pipeline(
            Deps(
                data_dir=workdir,
                cipher=Cipher([key]),
                llm=LLMClient(transport, DailyBudget(50_000_000)),
                clock=FixedClock(),
                registry=MockRegistry(DATA_DIR / "registry_mock.json"),
                resolver_enabled=resolver,
            )
        )
        data = (REPO_ROOT / case.document).read_bytes()
        run_id = pipeline.upload(data, applicant_name=case.applicant_name).run_id
        assert run_id is not None  # noqa: S101 - every catalogue document passes intake
        return grade(case, pipeline.process(run_id), pipeline)

    return run_each(cases, run_one)


# ------------------------------------------------------------------ the report
def p95(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)] if ordered else 0


def summarise(graded: dict[str, Any], *, split: str) -> dict[str, Any]:
    cases = [g for g in graded.values() if "error" not in g and g["split"] == split]
    n = len(cases)
    field_results: dict[str, list[bool]] = {}
    for g in cases:
        for name, ok in g["fields"].items():
            field_results.setdefault(name.split("[")[0], []).append(ok)
    ready = [g for g in cases if g["route"] == "ready"]
    precise = sum(g["critical_ok"] for g in ready)
    low, high = wilson_interval(precise, len(ready))
    by_bucket = {b: [g for g in cases if g["mix_bucket"] == b] for b in MIX}
    review_rate = sum(
        MIX[b] * (sum(g["route"] == "needs_review" for g in gs) / len(gs))
        for b, gs in by_bucket.items()
        if gs
    ) / (sum(MIX[b] for b, gs in by_bucket.items() if gs) or 1)
    return {
        "cases": n,
        "errors": sum("error" in g for g in graded.values()),
        "route_accuracy": sum(g["route_ok"] for g in cases) / n if n else 0.0,
        "reason_accuracy": sum(g["reasons_ok"] for g in cases) / n if n else 0.0,
        "field_accuracy": {f: sum(v) / len(v) for f, v in sorted(field_results.items())},
        "ready_precision": {
            "ready": len(ready),
            "correct": precise,
            "wilson_95": [round(low, 4), round(high, 4)],
        },
        "review_rate_mixed": round(review_rate, 4),
        "cost_per_document_usd": round(sum(g["cost_usd"] for g in cases) / n, 4) if n else 0.0,
        "p95_ms": {
            s: p95([g["stages_ms"][s] for g in cases if s in g["stages_ms"]])
            for s in STAGE_BUDGET_MS
        },
        "safety_violations": sum(len(g["safety"]) for g in cases),
    }


def models_measured(model: str) -> dict[str, str]:
    if model == "scripted":
        return {"all steps": "scripted (labels): checks routing and rules, not reading"}
    profile = active_profile()
    return {
        step: getattr(profile.steps, step).model
        for step in ("route", "extract_primary", "extract_secondary", "resolve")
    }


def write_report(
    out: Path, meta: dict[str, Any], summary: dict[str, Any], graded: dict[str, Any]
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "meta": meta,
        "summary": summary,
        "cases": {
            k: {x: v[x] for x in ("route", "reason_codes", "fields")}
            for k, v in graded.items()
            if "error" not in v
        },
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    rows = [json.dumps(r) for g in graded.values() if "error" not in g for r in g["signals"]]
    (out / "signals.jsonl").write_text("\n".join(rows) + "\n")
    lines = [
        f"# Eval report: {meta['name']}",
        "",
        f"- Date: {meta['date']}",
        f"- Model profile: {meta['profile']}",
        *(f"- Model, {step}: {model}" for step, model in meta["models"].items()),
        f"- Resolver: {'on' if meta['resolver'] else 'off'}",
        f"- Split: {meta['split']} ({summary['cases']} cases, {summary['errors']} errors)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Route accuracy | {summary['route_accuracy']:.1%} |",
        f"| Reason-code accuracy | {summary['reason_accuracy']:.1%} |",
        f"| `ready` precision (critical fields) | {summary['ready_precision']['correct']}/"
        f"{summary['ready_precision']['ready']}, Wilson 95% "
        f"{summary['ready_precision']['wilson_95']} |",
        f"| Review rate, realistic mix | {summary['review_rate_mixed']:.1%} |",
        f"| Cost per document | ${summary['cost_per_document_usd']:.4f} |",
        f"| `max_tokens` stops | {meta['max_token_stops']} of {meta['model_calls']} calls |",
        f"| Safety violations | {summary['safety_violations']} |",
        "",
        "| Field | Accuracy |",
        "|---|---|",
        *(f"| {f} | {a:.1%} |" for f, a in summary["field_accuracy"].items()),
        "",
        "| Stage | p95 | Budget |",
        "|---|---|---|",
        *(f"| {s} | {ms} ms | {STAGE_BUDGET_MS[s]} ms |" for s, ms in summary["p95_ms"].items()),
    ]
    if "pass3" in meta:
        lines += [
            "",
            f"pass^3 on {meta['pass3']['cases']} routing cases: "
            f"{meta['pass3']['all_three']} correct in all three runs.",
        ]
    (out / "report.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the labelled cases and write a report.")
    parser.add_argument("--model", choices=["scripted", "profile"], default="scripted")
    parser.add_argument("--split", choices=["test", "calibration"], default="test")
    parser.add_argument("--no-resolver", action="store_true")
    parser.add_argument("--pass3", action="store_true", help="run 30 routing cases 3 times")
    parser.add_argument("--groups", nargs="*", help="only these case groups")
    parser.add_argument(
        "--public",
        action="store_true",
        help="the public licences (scripts/fetch_public_samples.py downloads them first)",
    )
    parser.add_argument("--limit", type=int, help="at most this many cases (a slow model)")
    parser.add_argument("--name", default=datetime.now(UTC).strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()

    # Signal rows from both splits feed calibration; the metrics use the chosen split only.
    cases = [
        c
        for c in load_cases(
            PUBLIC if args.public else CASES, groups=set(args.groups) if args.groups else None
        )
        if (REPO_ROOT / c.document).exists()
    ]
    if args.limit:  # a slow model: the first cases of the chosen split only
        cases = [c for c in cases if c.split == args.split][: args.limit]
    inner: Transport = (
        LabelDemoTransport(CASES)
        if args.model == "scripted"
        else profile_transport(active_profile(), Settings())
    )
    transport = CountingTransport(inner)
    graded = run_cases(cases, transport, resolver=not args.no_resolver)
    meta: dict[str, Any] = {
        "name": args.name,
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "profile": "scripted" if args.model == "scripted" else active_profile_name() or "default",
        "models": models_measured(args.model),
        "resolver": not args.no_resolver,
        "split": args.split,
        "model_calls": transport.calls,
        "max_token_stops": transport.max_token_stops,
    }
    if args.pass3:
        subset = [c for c in cases if c.split == args.split][:PASS3_CASES]
        runs = [run_cases(subset, transport, resolver=not args.no_resolver) for _ in range(3)]
        meta["pass3"] = {
            "cases": len(subset),
            "all_three": sum(all(r[c.case_id].get("route_ok") for r in runs) for c in subset),
        }
    summary = summarise(graded, split=args.split)
    write_report(REPORTS / args.name, meta, summary, graded)
    print((REPORTS / args.name / "report.md").read_text())


if __name__ == "__main__":
    main()
