"""The gate: one route per run, with its reasons (US3; FR-020, FR-021, FR-037, FR-041).

- **reject** only for an invalid file, a document that is not a licence (corroborated in
  ``route.py``), or a corroborated expired licence.
- **needs_review** for any other reason: a failed or could-not-run check, a field below its
  confidence threshold (``low_confidence``, from ``confidence.py``), or a run-level reason
  such as ``fallback_model``.
- **ready** only when there is no reason at all.

An expired value is *corroborated* when both readings agree and the evidence check passes,
or when the registry confirms the expiry. Otherwise it becomes ``expiry_uncertain``, so a
misread date can never reject a licence on its own.
"""

from __future__ import annotations

from typing import Any

from licence_kyb.schemas.results import FILE_REASONS, RuleResult, reason_entry

ALWAYS_REJECT = FILE_REASONS | {"out_of_scope", "expired"}


def _passed(rules: list[RuleResult], rule_id: str, field: str) -> bool:
    return any(r.rule_id == rule_id and field in r.fields and r.outcome == "passed" for r in rules)


def expiry_corroborated(rules: list[RuleResult], agreement: dict[str, bool]) -> bool:
    readings_agree = agreement.get("expiry_date") is True
    evidence_matches = _passed(rules, "evidence", "expiry_date")
    registry_confirms = _passed(rules, "registry", "expiry_date")
    return (readings_agree and evidence_matches) or registry_confirms


def with_expiry_corroboration(
    rules: list[RuleResult], agreement: dict[str, bool]
) -> list[RuleResult]:
    """The rule results, with an uncorroborated ``expired`` changed to ``expiry_uncertain``.

    The change is made on the rule result itself, so the field, the run reasons and the
    review page all say the same thing.
    """
    if expiry_corroborated(rules, agreement):
        return rules
    return [
        r.model_copy(update={"reason_code": "expiry_uncertain"})
        if r.reason_code == "expired" and r.counts_as_failed
        else r
        for r in rules
    ]


def rule_reasons(rules: list[RuleResult]) -> list[dict[str, Any]]:
    """One reason per failed or could-not-run check and field. ``not_applicable`` never fails."""
    reasons = []
    for r in rules:
        if not r.counts_as_failed or r.reason_code is None:
            continue
        for f in r.fields or (None,):
            reasons.append(reason_entry(r.reason_code, field=f, rule_id=r.rule_id, detail=r.detail))
    return reasons


def decide_route(
    *,
    run_reasons: list[dict[str, Any]],
    rule_results: list[RuleResult],
    agreement: dict[str, bool],
) -> dict[str, Any]:
    """``{"route": ..., "reasons": [...]}``. Reasons are empty only when the route is ready."""
    checked = with_expiry_corroboration(rule_results, agreement)
    reasons = [*run_reasons, *rule_reasons(checked)]
    codes = {r["code"] for r in reasons}
    if codes & ALWAYS_REJECT:
        route = "reject"
    elif reasons:
        route = "needs_review"
    else:
        route = "ready"
    return {"route": route, "reasons": reasons}
