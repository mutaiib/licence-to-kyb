"""Critical fields must be present and readable; otherwise they need a person (FR-010)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, passed
from licence_kyb.schemas.licence import CRITICAL_FIELDS

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult


# Critical fields that another rule reports: the owners rule reports an unreadable owners
# table, and the Arabic-name rule decides per authority whether the Arabic name is needed.
REPORTED_ELSEWHERE = frozenset({"people", "trade_name_ar"})


def required_fields_rule(ctx: RuleContext) -> list[RuleResult]:
    results: list[RuleResult] = []
    for name in CRITICAL_FIELDS:
        if name in REPORTED_ELSEWHERE:
            continue
        field = getattr(ctx.extraction, name)
        if field.status == "present":
            results.append(passed("required", name, severity="warn"))
        else:
            results.append(failed("required", name, severity="warn", reason="low_confidence"))
    return results
