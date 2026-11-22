"""Ownership: share totals, sole establishments, beneficial owners, unreadable tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, not_applicable, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.licence import Person
    from licence_kyb.schemas.results import RuleResult

SHARE_TOLERANCE = 0.5
OWNER_ROLES = frozenset({"owner", "partner", "shareholder"})


def _people(ctx: RuleContext) -> list[Person] | None:
    return present(ctx.extraction.people)


def _owners(people: list[Person]) -> list[Person]:
    return [p for p in people if (present(p.role) or "") in OWNER_ROLES]


def shares_total_rule(ctx: RuleContext) -> list[RuleResult]:
    people = _people(ctx)
    shares = [s for p in people or [] if (s := present(p.share_pct)) is not None]
    if not shares:
        return [not_applicable("shares_total", "people")]
    total = sum(shares)
    if abs(total - 100) <= SHARE_TOLERANCE:
        return [passed("shares_total", "people")]
    return [
        failed(
            "shares_total",
            "people",
            severity="block",
            reason="shares_total",
            detail={"total": f"{total:g}"},
        )
    ]


def sole_owner_rule(ctx: RuleContext) -> list[RuleResult]:
    people = _people(ctx)
    if present(ctx.extraction.legal_form) != "sole_establishment" or people is None:
        return [not_applicable("sole_owner_count", "legal_form", "people")]
    count = len(_owners(people))
    if count == 1:
        return [passed("sole_owner_count", "legal_form", "people")]
    return [
        failed(
            "sole_owner_count",
            "legal_form",
            "people",
            severity="block",
            reason="sole_owner_count",
            detail={"count": str(count)},
        )
    ]


def ubo_rule(ctx: RuleContext) -> list[RuleResult]:
    """With no printed shares, beneficial owners cannot be derived: flag them (FR-013)."""
    people = _people(ctx)
    if not people:
        return [not_applicable("ubo", "people", severity="warn")]
    owners = _owners(people)
    if owners and all(present(p.share_pct) is None for p in owners):
        return [failed("ubo", "people", severity="warn", reason="ubo_needs_examination")]
    return [passed("ubo", "people", severity="warn")]


def owners_rule(ctx: RuleContext) -> list[RuleResult]:
    if ctx.extraction.people.status != "present":
        return [failed("owners", "people", severity="warn", reason="owners_unclear")]
    return [passed("owners", "people", severity="warn")]
