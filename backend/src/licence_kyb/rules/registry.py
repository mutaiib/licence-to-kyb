"""Registry: the authority's register is the source of truth; the paper copy is a claim.

- no register lookup for this authority → not applicable (never blocks ``ready``);
- the lookup fails → could not run, which a reviewer may override with a reason;
- no record, or a different expiry → blocking, never overridable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.normalise import normalise_number
from licence_kyb.rules.base import failed, not_applicable, passed, present
from licence_kyb.schemas.results import RuleResult

if TYPE_CHECKING:
    from datetime import date

    from licence_kyb.rules import RuleContext
    from licence_kyb.rules.base import RegistryResult

FIELDS = ("licence_number", "expiry_date")
KNOWN_STATUSES = ("active", "expired")
"""Statuses with their own checks: ``expired`` is the expiry rule's case. Any other status
(cancelled, suspended, revoked) blocks."""


def registry_rule(ctx: RuleContext) -> list[RuleResult]:
    number = present(ctx.extraction.licence_number)
    if not ctx.profile.has_register or number is None:
        return [not_applicable("registry", *FIELDS)]
    try:
        record = ctx.registry(normalise_number(number), ctx.authority)
    except Exception:  # any lookup failure means the check could not run
        return [
            RuleResult(
                rule_id="registry",
                fields=FIELDS,
                severity="block",
                outcome="could_not_run",
                reason_code="registry_unavailable",
                overridable=True,
            )
        ]
    if not record.found:
        return [failed("registry", *FIELDS, severity="block", reason="registry_not_found")]
    if record.status not in (None, *KNOWN_STATUSES):
        # A cancelled or suspended licence still has a record: the record is not enough.
        return [
            failed(
                "registry",
                "licence_number",
                severity="block",
                reason="registry_inactive",
                detail={"status": str(record.status)},
            )
        ]
    return _expiry_check(record, present(ctx.extraction.expiry_date))


def _expiry_check(record: RegistryResult, expiry: date | None) -> list[RuleResult]:
    """A found, active record: does its expiry date agree with the licence?"""
    if record.expiry_date is None:
        # The record confirms the number but says nothing about the expiry date, so it must
        # not count as corroborating an expired date (nodes/gate.py).
        return [passed("registry", "licence_number")]
    if expiry and record.expiry_date != expiry:
        return [
            failed(
                "registry",
                *FIELDS,
                severity="block",
                reason="registry_expiry_mismatch",
                detail={"registry": record.expiry_date.isoformat(), "value": expiry.isoformat()},
            )
        ]
    return [passed("registry", *FIELDS)]
