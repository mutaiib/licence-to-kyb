"""licence_get_validation_report: the checks that still fail."""

from __future__ import annotations

from licence_kyb.tools import ToolContext
from licence_kyb.tools.errors import ToolResult, answer


def run(ctx: ToolContext) -> ToolResult:
    failing = [r for r in ctx.rule_results if r.counts_as_failed]
    if not failing:
        return answer("All checks pass.")
    listed = "; ".join(
        f"{', '.join(r.fields) or 'document'} ({r.rule_id}, {r.severity}): {r.reason_code}"
        for r in failing
    )
    return answer(f"{len(failing)} checks fail: {listed}.")
