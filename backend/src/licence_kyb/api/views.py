"""Build API views from stored state. Values come from the checkpoint (encrypted at rest)."""

from __future__ import annotations

import json
from typing import Any

from licence_kyb.api.schemas import (
    EvidenceBox,
    FieldViewState,
    FormFieldView,
    FormView,
    ReasonView,
    RuleView,
    RunView,
    StepView,
)
from licence_kyb.graph import thread_config
from licence_kyb.nodes.map_form import SOURCES
from licence_kyb.pipeline import Pipeline
from licence_kyb.rules.base import normalise_text

STEPS = ("preprocess", "route", "extract", "validate", "map_form", "decide")


def _evidence_box(
    words: list[dict[str, Any]], quote: str | None, page: int | None
) -> EvidenceBox | None:
    """The union of the page words that make up the quote (best contiguous match)."""
    if not quote or page is None:
        return None
    tokens = normalise_text(quote).split()
    on_page = [w for w in words if w["page"] == page]
    best: list[dict[str, Any]] = []
    for i in range(len(on_page)):
        run: list[dict[str, Any]] = []
        for w, token in zip(on_page[i:], tokens, strict=False):
            if normalise_text(w["text"]) != token:
                break
            run.append(w)
        if len(run) > len(best):
            best = run
    if not best:
        best = [w for w in on_page if normalise_text(w["text"]) in set(tokens[-1:])]
    if not best:
        return None
    x0 = min(w["bbox"][0] for w in best)
    y0 = min(w["bbox"][1] for w in best)
    x1 = max(w["bbox"][2] for w in best)
    y1 = max(w["bbox"][3] for w in best)
    return EvidenceBox(page=page, x=x0, y=y0, w=x1 - x0, h=y1 - y0)


def _display(form_field: str, form: dict[str, Any], extraction: dict[str, Any]) -> Any:
    value = form.get(form_field)
    if value not in (None, [], ()):
        return value
    source = extraction.get(SOURCES[form_field], {})
    raw = source.get("value")
    if form_field in ("beneficial_owners", "controllers") and isinstance(raw, list):
        return [
            {
                "name": p["name"]["value"],
                "share_pct": p["share_pct"]["value"],
                "role": p["role"]["value"],
            }
            for p in raw
        ]
    if form_field == "activities" and isinstance(raw, list):
        return [
            {"code": a["code"]["value"], "description": a["description_en"]["value"]} for a in raw
        ]
    return raw


def build_run_view(pipeline: Pipeline, run_id: str) -> RunView | None:
    run = pipeline.db.get_run(run_id)
    if run is None:
        return None
    snapshot = pipeline.graph.get_state(thread_config(run_id))
    state: dict[str, Any] = dict(snapshot.values) if snapshot and snapshot.values else {}
    reasons = [ReasonView(**r) for r in json.loads(run["reasons_json"])]
    form_view: FormView | None = None
    docs: list[str] = []
    if state.get("form"):
        form, extraction = state["form"], state.get("extraction", {})
        words = state.get("pages", {}).get("words", [])
        rules = state.get("rule_results", [])
        fields: dict[str, FormFieldView] = {}
        for form_field, source in SOURCES.items():
            failing = [
                RuleView(**{k: r[k] for k in RuleView.model_fields})
                for r in rules
                if source in r["fields"] and r["outcome"] in ("failed", "could_not_run")
            ]
            raw_state = form["field_states"].get(form_field, "needs_examination")
            view_state: FieldViewState = (
                "flagged" if raw_state == "needs_examination" and failing else raw_state
            )
            src = extraction.get(source, {})
            fields[form_field] = FormFieldView(
                value=_display(form_field, form, extraction),
                state=view_state,
                origin=src.get("origin", "read"),
                evidence_quote=src.get("evidence_quote"),
                evidence_box=_evidence_box(words, src.get("evidence_quote"), src.get("page")),
                rule_results=failing,
            )
        form_view = FormView(version=form["version"], fields=fields)
        docs = [d["document"] for d in form["required_documents"]]
    done = {
        k
        for k in ("pages", "route", "extraction", "rule_results", "form", "decision")
        if state.get(k)
    }
    key = dict(
        zip(
            STEPS, ("pages", "route", "extraction", "rule_results", "form", "decision"), strict=True
        )
    )
    finished = run["status"] not in ("received", "processing")
    steps = [
        StepView(name=s, state="done" if key[s] in done else ("skipped" if finished else "pending"))
        for s in STEPS
    ]
    return RunView(
        run_id=run_id,
        status=run["status"],
        steps=steps,
        route=run["route"],
        reasons=reasons,
        form=form_view,
        required_documents=docs,
        pages=state.get("pages", {}).get("page_count", 0),
    )
