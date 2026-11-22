"""Critical fields must be present and readable; otherwise they need a person (FR-010)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, passed
from licence_kyb.schemas.licence import CRITICAL_FIELDS

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult


def required_fields_rule(ctx: RuleContext) -> list[RuleResult]:
    results: list[RuleResult] = []
    for name in CRITICAL_FIELDS:
        if name == "people":
            continue  # the owners rule reports an unreadable owners table
        if name == "trade_name_ar":
            continue  # the Arabic-name rule decides per authority
        field = getattr(ctx.extraction, name)
        if field.status == "present":
            results.append(passed("required", name, severity="warn"))
        else:
            results.append(failed("required", name, severity="warn", reason="low_confidence"))
    return results
