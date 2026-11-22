"""Run one tool call with every check first (contracts/resolver-tools.md, "Loop contract").

Order of checks: budget, known tool, arguments, page, field scope, repeat. Only then does
the tool run. Any unexpected failure inside a tool becomes ``tool_internal_error``: it is
logged for us and never shown to the model.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from licence_kyb.config import ResolverBudget
from licence_kyb.schemas.licence import TradeLicenceExtraction
from licence_kyb.schemas.results import ProposedFix
from licence_kyb.tools import (
    ToolContext,
    activity_lookup,
    ocr_region,
    registry_mock,
    reread_region,
    validation_report,
)
from licence_kyb.tools.definitions import ARGS
from licence_kyb.tools.errors import ToolResult, answer, tool_error

log = logging.getLogger(__name__)
READ_TOOLS: dict[str, Any] = {
    "licence_reread_region": reread_region,
    "licence_ocr_region": ocr_region,
    "licence_lookup_registry": registry_mock,
    "licence_lookup_activity": activity_lookup,
    "licence_get_validation_report": validation_report,
}
# The date fields as printed on the licence (written DD/MM/YYYY in a proposal).
SOURCE_DATE_FIELDS = frozenset({"issue_date", "expiry_date", "establishment_date"})
LIST_FIELDS = frozenset({"activities", "people"})


@dataclass
class Budget:
    """The resolver's limits (contracts/resolver-tools.md, "Budgets"). Turns count per round;
    tokens, time and tool calls count per run."""

    limits: ResolverBudget
    clock: Callable[[], float] = time.monotonic
    turns: int = 0
    tokens: int = 0
    tool_calls: int = 0
    started: float = field(default=-1.0)

    def __post_init__(self) -> None:
        if self.started < 0:
            self.started = self.clock()

    def new_round(self) -> None:
        self.turns = 0

    def charge_turn(self, tokens: int) -> None:
        self.turns += 1
        self.tokens += tokens

    def charge_tokens(self, tokens: int) -> None:
        self.tokens += tokens

    def _seconds(self) -> float:
        return self.clock() - self.started

    def soft(self) -> bool:
        lim = self.limits
        return (
            self.turns >= lim.soft_turns
            or self.tokens >= lim.soft_tokens
            or self._seconds() >= lim.soft_seconds
        )

    def hard(self) -> bool:
        lim = self.limits
        return (
            self.turns >= lim.hard_turns
            or self.tokens >= lim.hard_tokens
            or self.tool_calls >= lim.hard_tool_calls
            or self._seconds() >= lim.hard_seconds
        )


@dataclass
class ToolRunner:
    ctx: ToolContext
    budget: Budget
    proposals: list[ProposedFix] = field(default_factory=list)
    finished: bool = False
    _seen: dict[str, ToolResult] = field(default_factory=dict)

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        if self.budget.hard():
            return _hard_limit(name)
        if name not in ARGS:
            return _unknown_tool(name)
        try:
            parsed = ARGS[name].model_validate(args)
        except ValidationError as err:
            return _invalid_arguments(name, err)
        values = parsed.model_dump()
        problem = self._scope_problem(name, values)
        if problem is not None:
            return problem
        key = f"{name}:{json.dumps(values, sort_keys=True)}"
        if key in self._seen:
            return self._seen[key].with_notice(_duplicate(name))
        self.budget.tool_calls += 1
        try:
            result = self._run(name, values)
        except Exception:
            log.exception("resolver tool failed", extra={"tool": name})
            result = _internal_error(name)
        self._seen[key] = result
        if self.budget.soft() and name not in ("propose_fix", "finish"):
            result = result.with_notice(_soft_limit())
        return result

    # ------------------------------------------------------------------ checks
    def _scope_problem(self, name: str, values: dict[str, Any]) -> ToolResult | None:
        page = values.get("page")
        if page is not None and page > self.ctx.page_count:
            pages = list(range(1, self.ctx.page_count + 1))
            return tool_error(
                "page_not_found",
                what_failed=f"{name} for page {page}",
                why=f"Page {page} does not exist. The document has {self.ctx.page_count} page(s).",
                state="Nothing changed.",
                next_action="Call the tool again with a page in allowed.",
                allowed=pages,
            )
        target = values.get("field")
        if target is not None and target not in self.ctx.failed_fields:
            code = "proposal_refused" if name == "propose_fix" else "field_out_of_scope"
            return tool_error(
                code,
                what_failed=f"{name} for field {target}",
                why=f"{target} passed every check, so it is not investigated or changed.",
                state="Nothing changed. No proposal was recorded.",
                next_action="Use one of the fields in allowed, or call finish.",
                allowed=list(self.ctx.failed_fields),
            )
        return None

    # ------------------------------------------------------------------ dispatch
    def _run(self, name: str, values: dict[str, Any]) -> ToolResult:
        if name == "propose_fix":
            return self._propose(values)
        if name == "finish":
            self.finished = True
            return answer("Investigation finished. Proposals are checked now.")
        # Each tool's arguments have the same names as its run() parameters.
        result: ToolResult = READ_TOOLS[name].run(self.ctx, **values)
        return result

    def _propose(self, v: dict[str, Any]) -> ToolResult:
        codes = allowed_codes(v["field"])
        if codes and v["new_value"].strip() not in codes:
            return tool_error(
                "proposal_refused",
                what_failed=f"propose_fix for field {v['field']}",
                why=f"{v['field']} takes one of its codes, not the printed words.",
                state="No proposal was recorded.",
                next_action="Propose the code that matches the licence, or call finish.",
                allowed=codes,
            )
        value = normalised_value(v["field"], v["new_value"])
        if value is None:
            kind = (
                "a date written DD/MM/YYYY"
                if v["field"] in SOURCE_DATE_FIELDS
                else "a single value"
            )
            return tool_error(
                "proposal_refused",
                what_failed=f"propose_fix for field {v['field']}",
                why=f"'{v['new_value']}' is not {kind}.",
                state="No proposal was recorded.",
                next_action=f"Propose {v['field']} again as {kind}, or call finish.",
                allowed=[f for f in self.ctx.failed_fields if f not in LIST_FIELDS],
            )
        self.proposals = [p for p in self.proposals if p.field != v["field"]]
        self.proposals.append(
            ProposedFix(
                field=v["field"],
                new_value=value,
                evidence_quote=v["evidence_quote"],
                self_confidence=v["self_confidence"],
                rationale=v["rationale"],
            )
        )
        return answer(f"Proposal recorded for {v['field']}. It is checked after you finish.")


def allowed_codes(field_name: str) -> list[str]:
    """The codes a coded field takes (legal_form: llc, fze, ...); empty for a free-text field."""
    annotation = TradeLicenceExtraction.model_fields[field_name].annotation
    schema: dict[str, Any] = getattr(annotation, "model_json_schema", dict)()
    options = schema.get("properties", {}).get("value", {}).get("anyOf", [])
    return next((list(o["enum"]) for o in options if "enum" in o), [])


def normalised_value(field_name: str, value: str) -> str | None:
    """The value in the extraction's format, or None when it cannot be used."""
    if field_name in LIST_FIELDS:
        return None
    if field_name not in SOURCE_DATE_FIELDS:
        return value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ------------------------------------------------------------------ errors
def _hard_limit(name: str) -> ToolResult:
    return tool_error(
        "budget_hard_limit",
        what_failed=name,
        why="The resolver reached a hard limit.",
        state="The tool did not run. The investigation ends after this turn.",
        next_action="None: the system keeps the accepted fixes so far.",
    )


def _unknown_tool(name: str) -> ToolResult:
    return tool_error(
        "invalid_arguments",
        what_failed=f"a call to {name}",
        why=f"There is no tool named {name}. The resolver can only read and propose.",
        state="Nothing ran.",
        next_action="Use one of the tools in allowed.",
        allowed=sorted(ARGS),
    )


def _invalid_arguments(name: str, err: ValidationError) -> ToolResult:
    problems = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()]
    return tool_error(
        "invalid_arguments",
        what_failed=f"{name} with invalid arguments",
        why="; ".join(problems),
        state="Nothing ran.",
        next_action="Call the tool again with the corrections in allowed.",
        allowed=problems,
    )


def _duplicate(name: str) -> ToolResult:
    return tool_error(
        "duplicate_call",
        what_failed=name,
        why="This exact call was made before.",
        state="The earlier result is above. The tool did not run again.",
        next_action="Use the earlier result. Do not repeat the call.",
        is_error=False,
    )


def _soft_limit() -> ToolResult:
    return tool_error(
        "budget_soft_limit",
        what_failed="the investigation",
        why="The resolver is close to its limits.",
        state="Nothing changed.",
        next_action="Call propose_fix for any field you are sure of, then call finish.",
        is_error=False,
    )


def _internal_error(name: str) -> ToolResult:
    return tool_error(
        "tool_internal_error",
        what_failed=name,
        why="The tool failed for a reason inside the system.",
        state="Nothing changed.",
        next_action="Continue with other tools, or call finish. Do not repeat this call.",
    )
