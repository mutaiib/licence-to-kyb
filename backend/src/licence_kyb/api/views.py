"""Build API views from stored state. Values come from the checkpoint (encrypted at rest)."""

from __future__ import annotations

import json
from typing import Any

from licence_kyb.api.schemas import (
    ConfidenceView,
    EvidenceBox,
    FormFieldView,
    FormView,
    ReasonView,
    RuleView,
    RunView,
    StepState,
    StepView,
)
from licence_kyb.graph import thread_config
from licence_kyb.nodes.map_form import SOURCES, read_values
from licence_kyb.nodes.preprocess import Word, visual_rows
from licence_kyb.pipeline import Pipeline
from licence_kyb.rules.base import normalise_text
from licence_kyb.schemas.kyb_form import FieldState, FormValue, KYBOnboardingForm
from licence_kyb.schemas.licence import Field, TradeLicenceExtraction
from licence_kyb.schemas.results import RuleResult

ACTIVE_STATUSES = frozenset({"received", "processing"})

# Each step, and the state key that holds its output. A step is done when its key has a value.
STEP_OUTPUT: dict[str, str] = {
    "preprocess": "pages",
    "route": "route",
    "extract": "extraction",
    "validate": "rule_results",
    "confidence": "confidence",
    "map_form": "form",
    "gate": "decision",
}


def build_run_view(pipeline: Pipeline, run_id: str) -> RunView | None:
    run = pipeline.db.get_run(run_id)
    if run is None:
        return None
    snapshot = pipeline.graph.get_state(thread_config(run_id))
    state: dict[str, Any] = dict(snapshot.values) if snapshot and snapshot.values else {}
    form, documents = _form_view(state)
    return RunView(
        run_id=run_id,
        status=run["status"],
        steps=_step_views(state, finished=run["status"] not in ACTIVE_STATUSES),
        route=run["route"],
        reasons=[ReasonView(**r) for r in json.loads(run["reasons_json"])],
        form=form,
        required_documents=documents,
        pages=state.get("pages", {}).get("page_count", 0),
    )


def _step_views(state: dict[str, Any], *, finished: bool) -> list[StepView]:
    """A step without output is ``pending`` while the run is active, else ``skipped``."""
    steps: list[StepView] = []
    for name, output in STEP_OUTPUT.items():
        step_state: StepState
        if state.get(output):
            step_state = "done"
        elif finished:
            step_state = "skipped"
        else:
            step_state = "pending"
        steps.append(StepView(name=name, state=step_state))
    return steps


def _form_view(state: dict[str, Any]) -> tuple[FormView | None, list[str]]:
    """The form, one view per field, and the documents to request. None before map_form."""
    if not state.get("form"):
        return None, []
    form = KYBOnboardingForm.model_validate(state["form"])
    extraction = TradeLicenceExtraction.model_validate(state["extraction"])
    read = read_values(extraction)
    words = [Word.from_dict(w) for w in state["pages"]["words"]]
    rules = [RuleResult.model_validate(r) for r in state.get("rule_results", [])]

    fields: dict[str, FormFieldView] = {}
    for form_field, source_name in SOURCES.items():
        failing = [r for r in rules if source_name in r.fields and r.counts_as_failed]
        fields[form_field] = _field_view(
            form_field,
            form,
            source=getattr(extraction, source_name),
            read_value=read[form_field],
            words=words,
            failing=failing,
            confidence=state.get("confidence", {}).get(source_name),
        )
    documents: list[str] = [item.document for item in form.required_documents]
    return FormView(version=form.version, fields=fields), documents


def _field_view(
    form_field: str,
    form: KYBOnboardingForm,
    *,
    source: Field[Any],
    read_value: FormValue,
    words: list[Word],
    failing: list[RuleResult],
    confidence: dict[str, Any] | None,
) -> FormFieldView:
    form_value: FormValue = getattr(form, form_field)
    has_form_value = form_value is not None and form_value != ()
    field_state: FieldState = form.field_states.get(form_field, "needs_examination")
    if field_state == "needs_examination" and failing:
        field_state = "flagged"
    return FormFieldView(
        value=form_value if has_form_value else read_value,
        state=field_state,
        status=source.status,
        origin=source.origin,
        evidence_quote=source.evidence_quote,
        evidence_box=_evidence_box(words, source.evidence_quote, source.page),
        rule_results=[_rule_view(r) for r in failing],
        # A value the reviewer typed has no reading, so the reading's score does not apply.
        confidence=(
            ConfidenceView(**confidence) if confidence and source.origin == "read" else None
        ),
    )


def _rule_view(result: RuleResult) -> RuleView:
    return RuleView(
        rule_id=result.rule_id,
        severity=result.severity,
        outcome=result.outcome,
        reason_code=result.reason_code,
        overridable=result.overridable,
        detail=result.detail,
    )


def _evidence_box(words: list[Word], quote: str | None, page: int | None) -> EvidenceBox | None:
    """The box around the page words that make up ``quote``.

    The page words are read in visual order. The longest run of words that matches the quote
    word by word, from its first word, wins. When no run matches, the box falls back to the
    words equal to the quote's last word, which is usually the value itself.
    """
    if not quote or page is None:
        return None
    tokens = normalise_text(quote).split()
    if not tokens:
        return None
    on_page: list[Word] = []
    for row in visual_rows([w for w in words if w.page == page]):
        on_page.extend(row)
    matched = _longest_match(on_page, tokens)
    if not matched:
        matched = [w for w in on_page if normalise_text(w.text) == tokens[-1]]
    if not matched:
        return None
    return _union(page, matched)


def _longest_match(words: list[Word], tokens: list[str]) -> list[Word]:
    best: list[Word] = []
    for start in range(len(words)):
        run: list[Word] = []
        for word, token in zip(words[start:], tokens, strict=False):
            if normalise_text(word.text) != token:
                break
            run.append(word)
        if len(run) > len(best):
            best = run
    return best


def _union(page: int, words: list[Word]) -> EvidenceBox:
    """The smallest box that holds every word."""
    x0 = min(w.bbox[0] for w in words)
    y0 = min(w.bbox[1] for w in words)
    x1 = max(w.bbox[2] for w in words)
    y1 = max(w.bbox[3] for w in words)
    return EvidenceBox(page=page, x=x0, y=y0, w=x1 - x0, h=y1 - y0)
