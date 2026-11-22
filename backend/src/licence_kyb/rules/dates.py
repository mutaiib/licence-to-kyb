"""Date order: issue before expiry, establishment not after issue (FR-012)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult


def date_order_rule(ctx: RuleContext) -> list[RuleResult]:
    ex = ctx.extraction
    issue, expiry, est = (
        present(ex.issue_date),
        present(ex.expiry_date),
        present(ex.establishment_date),
    )
    if issue is not None and expiry is not None and issue >= expiry:
        return [
            failed("date_order", "issue_date", "expiry_date", severity="block", reason="date_order")
        ]
    if est is not None and issue is not None and est > issue:
        return [
            failed(
                "date_order",
                "establishment_date",
                "issue_date",
                severity="block",
                reason="date_order",
            )
        ]
    return [passed("date_order", "issue_date", "expiry_date")]
