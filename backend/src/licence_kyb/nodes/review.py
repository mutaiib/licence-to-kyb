"""Reviewer actions (User Story 2): check an action, then work out what it changes.

A reviewer sends one of four actions: ``review`` (field decisions, and optionally approve
or reject the whole form), ``submit``, ``reopen`` or ``retry``.

Two steps, both pure functions with no database or model calls:

1. ``check_*`` refuses an invalid action with ``ActionRefused`` and a contract error code.
   The pipeline calls it *before* it resumes the paused run, so the run only sees valid
   actions.
2. ``apply_review`` returns the new state of the run. The pipeline writes the audit
   events and the captured corrections that the result lists. Every write is keyed by
   the client's ID, so the same action sent twice changes nothing the second time.

Names: a *form field* is a field of the KYB form (``legal_name_en``). A *source field* is
the licence field it comes from (``trade_name_en``). ``SOURCES`` maps one to the other.
Rule results name source fields.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from licence_kyb.nodes.map_form import SOURCES, build_form
from licence_kyb.schemas.licence import TradeLicenceExtraction
from licence_kyb.schemas.results import ActionErrorCode, RuleResult, reason_entry

# Fields a reviewer can type a value into. Lists (activities, owners) are approved, not retyped.
CORRECTABLE = frozenset(
    {
        "legal_name_en",
        "legal_name_ar",
        "legal_form",
        "licence_number",
        "issue_date",
        "expiry_date",
        "registered_address",
        "chamber_number",
    }
)
DATE_FIELDS = frozenset({"issue_date", "expiry_date"})
RETRYABLE = frozenset({"processing_failed", "budget_exhausted"})

RunRules = Callable[[TradeLicenceExtraction], list[RuleResult]]
"""Runs every rule on an extraction (the pipeline supplies today's date, OCR text, QR, registry)."""


class ActionRefused(Exception):  # noqa: N818 - reads as "the action was refused"
    """An action the contract answers with 409 and an error code."""

    def __init__(
        self, code: ActionErrorCode, *, field: str | None = None, rule_id: str | None = None
    ):
        super().__init__(code)
        self.code, self.field, self.rule_id = code, field, rule_id

    def body(self) -> dict[str, str | None]:
        return {"code": self.code, "field": self.field, "rule_id": self.rule_id}


@dataclass
class ReviewResult:
    """The run after a review action, plus the records the pipeline must write."""

    state: dict[str, Any]
    """Updates for the run state: decisions, extraction, rule results, form, status, reasons."""
    new_decisions: list[dict[str, Any]] = field(default_factory=list)
    approved_version: int | None = None
    rejected: bool = False


# ------------------------------------------------------------------ small helpers
def form_fields_of(sources: tuple[str, ...]) -> list[str]:
    """The form fields filled from any of these source fields."""
    return [f for f, s in SOURCES.items() if s in sources]


def empty_extraction() -> dict[str, Any]:
    """An extraction in which nothing was read. Used when processing fails, so the reviewer
    can still enter every value by hand (FR-043)."""
    nothing = {
        "value": None,
        "status": "not_present",
        "evidence_quote": None,
        "page": None,
        "self_confidence": "unknown",
    }
    return {name: dict(nothing) for name in TradeLicenceExtraction.model_fields}


def form_json(form: dict[str, Any]) -> str:
    """Canonical JSON, so a stored submission can be compared with the approved form."""
    return json.dumps(form, sort_keys=True, ensure_ascii=False, default=str)


def new_ids_only(state: dict[str, Any], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop decisions whose ID was already applied (a repeated call)."""
    applied = set(state.get("applied_ids", []))
    return [d for d in decisions if d["decision_id"] not in applied]


# ------------------------------------------------------------------ decisions → new form
def corrected_extraction(read: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    """The extraction as read, with each corrected value replaced by the reviewer's value."""
    updated = dict(read)
    for target, d in decisions.items():
        if d["action"] != "correct":
            continue
        source = SOURCES[target]
        value = date.fromisoformat(d["value"]).isoformat() if target in DATE_FIELDS else d["value"]
        read_field = read.get(source, {})
        updated[source] = {
            "value": value,
            "status": "present",
            "origin": "entered_by_reviewer",
            # Keep where the licence shows this field, so the reviewer still sees the text.
            # The evidence check does not apply to a typed value (rules/grounding.py).
            "evidence_quote": read_field.get("evidence_quote"),
            "page": read_field.get("page"),
            "self_confidence": "unknown",
        }
    return updated


def overridden_rules(decisions: dict[str, Any]) -> set[str]:
    return {target for target, d in decisions.items() if d["action"] == "override"}


def decided_sources(decisions: dict[str, Any], results: list[RuleResult]) -> set[str]:
    """Source fields a person has approved, corrected, or covered with an override."""
    sources = {SOURCES[t] for t, d in decisions.items() if d["action"] != "override"}
    for r in results:
        if r.rule_id in overridden_rules(decisions):
            sources.update(r.fields)
    return sources


def build_reviewed_form(
    extraction: TradeLicenceExtraction,
    results: list[RuleResult],
    decisions: dict[str, Any],
    *,
    authority: str,
    version: int,
) -> dict[str, Any]:
    """The draft form with every decision applied, and each decided field's state."""
    form = build_form(
        extraction,
        results,
        authority=authority,
        version=version,
        approved=frozenset(decided_sources(decisions, results)),
    ).model_dump(mode="json")
    states = form["field_states"]
    for target, d in decisions.items():
        if d["action"] == "approve":
            states[target] = "approved"
        elif d["action"] == "correct":
            states[target] = "corrected"
    for r in results:
        if r.rule_id in overridden_rules(decisions):
            for f in form_fields_of(r.fields):
                states[f] = "overridden"
    return form


def open_reasons(
    results: list[RuleResult], decided: set[str], overridden: set[str]
) -> list[dict[str, Any]]:
    """Failed rules on fields that no one has decided yet."""
    reasons = []
    for r in results:
        if not r.counts_as_failed or r.rule_id in overridden:
            continue
        for f in r.fields or (None,):
            if f not in decided:
                assert r.reason_code is not None  # noqa: S101 - every failed rule has a reason code
                reasons.append(
                    reason_entry(r.reason_code, field=f, rule_id=r.rule_id, detail=r.detail)
                )
    return reasons


def without_version(form: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in form.items() if k != "version"}


# ------------------------------------------------------------------ the review action
def check_review_target(state: dict[str, Any], d: dict[str, Any]) -> None:
    """Refuse a decision that names no valid field or rule, or lacks a needed reason."""
    if d["action"] == "override":
        if not d.get("reason"):
            raise ActionRefused("reason_required", rule_id=d.get("rule_id"))
        rule = next(
            (r for r in state.get("rule_results", []) if r["rule_id"] == d.get("rule_id")), None
        )
        if rule is None or rule["outcome"] != "could_not_run" or not rule["overridable"]:
            raise ActionRefused("not_overridable", rule_id=d.get("rule_id"))
        return
    name = d.get("field")
    if name not in SOURCES or (d["action"] == "correct" and name not in CORRECTABLE):
        raise ActionRefused("blocking_rule_failed", field=name)
    if d["action"] == "correct" and name in DATE_FIELDS:
        try:
            date.fromisoformat(d.get("value") or "")
        except ValueError:
            raise ActionRefused("blocking_rule_failed", field=name) from None


def blocking_failure(results: list[RuleResult], form_field: str, overridden: set[str]) -> bool:
    """True when a blocking rule still fails on this field after the re-check."""
    source = SOURCES[form_field]
    return any(
        r.counts_as_failed
        and r.severity == "block"
        and source in r.fields
        and r.rule_id not in overridden
        for r in results
    )


def new_form_action(state: dict[str, Any], action: dict[str, Any]) -> str | None:
    """``approve`` or ``reject`` when the request asks for one that was not applied yet."""
    if action["action_id"] in state.get("applied_ids", []):
        return None
    if action.get("reject_case"):
        return "reject"
    return "approve" if action.get("approve_form") else None


def check_review_request(
    state: dict[str, Any], action: dict[str, Any], fresh: list[dict[str, Any]]
) -> None:
    if state.get("status") not in ("awaiting_review", "awaiting_submit"):
        raise ActionRefused("stale_version")
    if action["form_version"] != state["form"]["version"]:
        raise ActionRefused("stale_version")
    if action.get("reject_case") and not action.get("reject_reason"):
        raise ActionRefused("reason_required")
    for d in fresh:
        check_review_target(state, d)


def next_form(
    old_form: dict[str, Any],
    extraction: TradeLicenceExtraction,
    results: list[RuleResult],
    decisions: dict[str, Any],
    authority: str,
) -> tuple[dict[str, Any], bool]:
    """The rebuilt form, and whether its content changed. A change raises the version."""
    version = old_form["version"]
    form = build_reviewed_form(extraction, results, decisions, authority=authority, version=version)
    changed = without_version(form) != without_version(old_form)
    form["version"] = version + 1 if changed else version
    return form, changed


def next_status(status: str, form: dict[str, Any], changed: bool, form_action: str | None) -> str:
    if form_action == "reject":
        return "rejected"
    if form_action == "approve":
        undecided = [f for f, s in form["field_states"].items() if s == "needs_examination"]
        if undecided:
            raise ActionRefused("undecided_fields", field=undecided[0])
        return "awaiting_submit"
    return "awaiting_review" if changed else status  # any change needs a new approval


def apply_review(
    state: dict[str, Any], action: dict[str, Any], run_rules: RunRules
) -> ReviewResult:
    """Check a review action and work out the new run state. Raises ``ActionRefused``."""
    fresh = new_ids_only(state, action["decisions"])
    form_action = new_form_action(state, action)
    if not fresh and form_action is None:
        return ReviewResult(state={})  # a repeated call: nothing to do
    if state.get("form") is None:
        return _reject_without_form(state, action, fresh, form_action)
    check_review_request(state, action, fresh)

    # Apply all decisions so far to the extraction as read, then re-run every rule.
    decisions = dict(state.get("decisions", {}))
    for d in fresh:
        decisions[d.get("field") or d["rule_id"]] = d
    read = state.get("read_extraction") or state["extraction"]
    extraction = corrected_extraction(read, decisions)
    parsed = TradeLicenceExtraction.model_validate(extraction)
    results = run_rules(parsed)
    overridden = overridden_rules(decisions)
    for d in fresh:
        if d["action"] != "override" and blocking_failure(results, d["field"], overridden):
            raise ActionRefused("blocking_rule_failed", field=d["field"])

    authority = state["route"]["authority"]
    form, changed = next_form(state["form"], parsed, results, decisions, authority)
    status = next_status(state["status"], form, changed, form_action)

    reasons = [r for r in state.get("reasons", []) if r.get("rule_id") is None]
    if form_action == "reject":
        reasons.append(reason_entry("reviewer_rejected"))
    reasons += open_reasons(results, decided_sources(decisions, results), overridden)
    applied = [*state.get("applied_ids", []), *(d["decision_id"] for d in fresh)]
    if form_action:
        applied.append(action["action_id"])
    return ReviewResult(
        state={
            "decisions": decisions,
            "read_extraction": read,
            "extraction": extraction,
            "rule_results": [r.model_dump(mode="json") for r in results],
            "form": form,
            "status": status,
            "reasons": reasons,
            "applied_ids": applied,
        },
        new_decisions=fresh,
        approved_version=form["version"] if form_action == "approve" else None,
        rejected=form_action == "reject",
    )


def _reject_without_form(
    state: dict[str, Any],
    action: dict[str, Any],
    fresh: list[dict[str, Any]],
    form_action: str | None,
) -> ReviewResult:
    """Processing crashed before the form existed. The reviewer can retry or reject the case;
    there is nothing to decide or approve yet."""
    if fresh or form_action != "reject":
        raise ActionRefused("no_form")
    if state.get("status") != "awaiting_review":
        raise ActionRefused("stale_version")
    if not action.get("reject_reason"):
        raise ActionRefused("reason_required")
    return ReviewResult(
        state={
            "status": "rejected",
            "reasons": [*state.get("reasons", []), reason_entry("reviewer_rejected")],
            "applied_ids": [*state.get("applied_ids", []), action["action_id"]],
        },
        rejected=True,
    )


# ------------------------------------------------------------------ submit, reopen, retry
def check_submit(state: dict[str, Any], action: dict[str, Any], *, approved: bool) -> None:
    """``approved``: an approval exists for the requested form version."""
    if state.get("status") not in ("awaiting_review", "awaiting_submit"):
        raise ActionRefused("not_awaiting_submit")  # rejected, done or still processing
    if state.get("form") is None:
        raise ActionRefused("no_form")  # processing crashed before the form existed
    if action["form_version"] != state["form"]["version"]:
        raise ActionRefused("stale_version")
    if not approved:
        raise ActionRefused("not_approved")


def check_reopen(state: dict[str, Any]) -> None:
    if state.get("status") != "rejected":
        raise ActionRefused("not_rejected")


def check_retry(state: dict[str, Any]) -> None:
    codes = {r["code"] for r in state.get("reasons", [])}
    if state.get("status") != "awaiting_review" or not codes & RETRYABLE:
        raise ActionRefused("not_retryable")
