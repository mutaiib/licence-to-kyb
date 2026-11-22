"""The business name on the application matches the licence (FR-012)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rapidfuzz import fuzz

from licence_kyb.rules.base import failed, normalise_name, not_applicable, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult


def applicant_rule(ctx: RuleContext) -> list[RuleResult]:
    name = present(ctx.extraction.trade_name_en)
    if name is None or not ctx.applicant_name.strip():
        return [not_applicable("applicant_name", "trade_name_en", severity="warn")]
    score = fuzz.token_sort_ratio(normalise_name(name), normalise_name(ctx.applicant_name)) / 100
    if score >= ctx.applicant_threshold:
        return [passed("applicant_name", "trade_name_en", severity="warn")]
    return [
        failed("applicant_name", "trade_name_en", severity="warn", reason="applicant_name_mismatch")
    ]
