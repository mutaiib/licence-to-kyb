"""Arabic trade name present where the authority shows one (FR-012)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, not_applicable, passed

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult


def arabic_name_rule(ctx: RuleContext) -> list[RuleResult]:
    if not ctx.profile.arabic_name_required:
        return [not_applicable("arabic_name", "trade_name_ar", severity="warn")]
    if ctx.extraction.trade_name_ar.status == "present":
        return [passed("arabic_name", "trade_name_ar", severity="warn")]
    return [
        failed(
            "arabic_name",
            "trade_name_ar",
            severity="warn",
            reason="arabic_name_missing",
            detail={"authority": ctx.authority},
        )
    ]
