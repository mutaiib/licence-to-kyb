"""The resolver's read-only tools (US4; contracts/resolver-tools.md).

Each tool is a small function ``run(ctx, args) -> ToolResult`` in its own module.
``runner.ToolRunner`` checks every call first (budget, scope, arguments, repeats) and then
dispatches to the tool. No tool can write anything: status, audit and submissions are only
changed by harness code (FR-018).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from licence_kyb.nodes.preprocess import Word
from licence_kyb.rules.base import RegistryResult
from licence_kyb.schemas.licence import TradeLicenceExtraction
from licence_kyb.schemas.results import RuleResult


@dataclass
class ToolContext:
    """What the tools may read for one run."""

    page_count: int
    words: list[Word]
    extraction: TradeLicenceExtraction
    rule_results: list[RuleResult]
    failed_fields: tuple[str, ...]
    """The fields the resolver may investigate and propose values for."""
    authority: str
    registry: Callable[[str, str], RegistryResult]
    reread: Callable[[int, str], str] | None
    """Reads one page region with the vision model. None for a text-only model profile."""
