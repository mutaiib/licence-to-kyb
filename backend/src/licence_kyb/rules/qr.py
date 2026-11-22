"""QR code agrees with the printed licence number. The payload is untrusted data:
it is matched as text and never opened or fetched (FR-007)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from licence_kyb.normalise import normalise_number
from licence_kyb.rules.base import failed, not_applicable, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult


def qr_rule(ctx: RuleContext) -> list[RuleResult]:
    number = present(ctx.extraction.licence_number)
    if not ctx.qr_payload or number is None:
        return [not_applicable("qr", "licence_number")]
    payload = normalise_number(ctx.qr_payload)
    # Whole numbers only: 1234567 must not match inside 81234567 or 9912345670.
    found = ctx.profile.numbers_in.findall(payload) or re.findall(r"[\w-]+", payload)
    if normalise_number(number) in found:
        return [passed("qr", "licence_number")]
    shown = found[0] if found else payload[:40]
    return [
        failed(
            "qr",
            "licence_number",
            severity="block",
            reason="qr_mismatch",
            detail={"qr": shown, "value": number},
        )
    ]
