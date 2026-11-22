"""Licence number format for the issuing authority (FR-012)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, not_applicable, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult


def number_format_rule(ctx: RuleContext) -> list[RuleResult]:
    number = present(ctx.extraction.licence_number)
    if number is None:
        return [not_applicable("number_format", "licence_number")]
    if ctx.profile.matches_number(number):
        return [passed("number_format", "licence_number")]
    result = failed(
        "number_format",
        "licence_number",
        severity="block",
        reason="number_format",
        detail={"authority": ctx.authority},
    )
    # A pattern inferred from samples can be wrong for a real licence (an older, shorter
    # number): a reviewer may override it with a reason. A confirmed pattern cannot be.
    overridable = ctx.profile.number_pattern_source != "confirmed"
    return [result.model_copy(update={"overridable": overridable})]
