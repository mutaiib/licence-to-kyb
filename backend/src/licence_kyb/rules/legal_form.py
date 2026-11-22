"""Legal form allowed for the authority (FR-012)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, not_applicable, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult


def legal_form_rule(ctx: RuleContext) -> list[RuleResult]:
    form = present(ctx.extraction.legal_form)
    if form is None:
        return [not_applicable("legal_form", "legal_form")]
    if form in ctx.profile.allowed_legal_forms:
        return [passed("legal_form", "legal_form")]
    return [
        failed(
            "legal_form",
            "legal_form",
            severity="block",
            reason="legal_form_not_allowed",
            detail={"authority": ctx.authority, "form": form},
        )
    ]
