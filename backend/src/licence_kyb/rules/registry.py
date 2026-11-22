"""Registry: the authority's register is the source of truth; the paper copy is a claim.

- no register lookup for this authority → not applicable (never blocks ``ready``);
- the lookup fails → could not run, which a reviewer may override with a reason;
- no record, or a different expiry → blocking, never overridable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from licence_kyb.rules.base import failed, not_applicable, passed, present
from licence_kyb.schemas.results import RuleResult

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext

FIELDS = ("licence_number", "expiry_date")


def registry_rule(ctx: RuleContext) -> list[RuleResult]:
    number = present(ctx.extraction.licence_number)
    if not ctx.profile.has_register or number is None:
        return [not_applicable("registry", *FIELDS)]
    try:
        record = ctx.registry(number, ctx.authority)
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
    expiry = present(ctx.extraction.expiry_date)
    if record.expiry_date and expiry and record.expiry_date != expiry:
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
