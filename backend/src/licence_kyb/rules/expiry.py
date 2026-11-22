"""Expiry: expired (today or earlier) blocks; fewer than 30 days warns (FR-012)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, not_applicable, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult

NEAR_EXPIRY_DAYS = 30


def expiry_rule(ctx: RuleContext) -> list[RuleResult]:
    expiry = present(ctx.extraction.expiry_date)
    if expiry is None:
        return [not_applicable("expiry", "expiry_date")]
    if expiry <= ctx.today:
        return [
            failed(
                "expiry",
                "expiry_date",
                severity="block",
                reason="expired",
                detail={"date": expiry.isoformat()},
            )
        ]
    second = ctx.secondary_expiry
    if second is not None and second <= ctx.today and ctx.extraction.expiry_date.origin == "read":
        # The second reading says the licence has expired; the first does not. Neither is
        # proven, so a person (or a re-read) must look: never ready, never rejected.
        return [
            failed(
                "expiry",
                "expiry_date",
                severity="block",
                reason="expiry_uncertain",
                detail={"date": second.isoformat()},
            )
        ]
    days = (expiry - ctx.today).days
    if days < NEAR_EXPIRY_DAYS:
        return [
            failed(
                "expiry",
                "expiry_date",
                severity="warn",
                reason="near_expiry",
                detail={"days": str(days)},
            )
        ]
    return [passed("expiry", "expiry_date")]
