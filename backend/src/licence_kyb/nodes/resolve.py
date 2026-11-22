"""The resolver: the one bounded agent (US4; ADR-001, FR-015 to FR-018).

It runs only when a check that a second reading can fix has failed (``re_readable_fields``).
It is a plain loop: ask the model, run the tools it calls (``tools/runner.py``), send the
results back, and stop at ``finish``, at a hard limit, or when the model stops calling tools.
After the loop, ``apply_proposals`` keeps each proposal only if every rule on its field
passes (FR-016). The model can only read and propose; it can never write (FR-018).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from licence_kyb.config import StepModel
from licence_kyb.llm.client import LLMClient, LLMError, ModelRequest
from licence_kyb.llm.prompts import load_prompt
from licence_kyb.schemas.licence import TradeLicenceExtraction
from licence_kyb.schemas.results import ProposedFix, RuleResult
from licence_kyb.tools import ToolContext
from licence_kyb.tools.definitions import tool_definitions
from licence_kyb.tools.runner import Budget, ToolRunner

# Failed checks that a second reading can fix (contracts/resolver-tools.md, "When the
# resolver runs"). An unreadable required value is the `required` check's low_confidence.
RE_READABLE = frozenset(
    {
        "evidence_mismatch",
        "number_format",
        "date_order",
        "qr_mismatch",
        "expiry_uncertain",
        "registry_not_found",
    }
)

RunRules = Callable[[TradeLicenceExtraction], list[RuleResult]]


def re_readable_fields(rules: list[RuleResult]) -> tuple[str, ...]:
    fields: set[str] = set()
    for r in rules:
        if not r.counts_as_failed:
            continue
        if r.reason_code in RE_READABLE or (r.rule_id == "required"):
            fields.update(r.fields)
    return tuple(sorted(fields))


@dataclass
class ResolverOutcome:
    extraction: dict[str, Any]
    """The extraction with the accepted proposals applied."""
    proposals: list[ProposedFix] = field(default_factory=list)
    budget_reached: bool = False


def run_resolver(
    *,
    llm: LLMClient,
    model: StepModel,
    ctx: ToolContext,
    budget: Budget,
    extraction: dict[str, Any],
    run_rules: RunRules,
) -> ResolverOutcome:
    tools = tool_definitions(ctx.failed_fields, vision=ctx.reread is not None)
    runner = ToolRunner(ctx, budget)
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": [{"type": "text", "text": _brief(ctx)}]}
    ]
    budget.new_round()
    while not runner.finished and not budget.hard():
        request = ModelRequest(
            step="resolve",
            model=model.model,
            effort=model.effort,
            max_tokens=model.max_tokens,
            system=load_prompt("resolve"),
            messages=messages,
            tools=tools,
        )
        try:
            response = llm.call(request)
        except LLMError:
            break  # the run continues with what was accepted so far
        budget.charge_turn(response.usage.billed_tokens)
        calls = [b for b in response.content if b.get("type") == "tool_use"]
        if response.stop_reason != "tool_use" or not calls:
            break
        results = [runner.call(c["name"], c.get("input") or {}).block(c["id"]) for c in calls]
        messages += [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": results},
        ]
    reached = budget.hard() and not runner.finished
    applied, proposals = apply_proposals(extraction, runner.proposals, run_rules)
    return ResolverOutcome(extraction=applied, proposals=proposals, budget_reached=reached)


def apply_proposals(
    extraction: dict[str, Any], proposals: list[ProposedFix], run_rules: RunRules
) -> tuple[dict[str, Any], list[ProposedFix]]:
    """Keep each proposal only if no check that doubts the value fails on its field (FR-016)."""
    current = dict(extraction)
    checked = []
    for p in proposals:
        old = current.get(p.field, {})
        candidate = {
            **current,
            p.field: {
                "value": p.new_value,
                "status": "present",
                "origin": "read",
                "evidence_quote": p.evidence_quote,
                "page": old.get("page") or 1,
                "self_confidence": p.self_confidence,
            },
        }
        results = run_rules(TradeLicenceExtraction.model_validate(candidate))
        passes = not any(_reading_problem(r) for r in results if p.field in r.fields)
        if passes:
            current = candidate
        checked.append(p.model_copy(update={"accepted": passes}))
    return current, checked


def _reading_problem(r: RuleResult) -> bool:
    """A failed check that says the value may be wrong: any blocking check, or a check that
    a re-read can fix. A business warning (``near_expiry``) is true of a correct value too."""
    return r.counts_as_failed and (r.severity == "block" or r.reason_code in RE_READABLE)


def _brief(ctx: ToolContext) -> str:
    """The first message: the failed fields, their values and quotes, and why they failed."""
    lines = [f"The licence has {ctx.page_count} page(s). These fields failed a check:"]
    for name in ctx.failed_fields:
        f = getattr(ctx.extraction, name)
        reasons = ", ".join(
            sorted(
                {
                    str(r.reason_code)
                    for r in ctx.rule_results
                    if name in r.fields and r.counts_as_failed
                }
            )
        )
        lines.append(f"- {name}: value '{f.value}', quote '{f.evidence_quote}'. Failed: {reasons}.")
    lines.append(
        "Investigate them with the tools, propose what the document shows, then call finish."
    )
    return "\n".join(lines)
