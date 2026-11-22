"""Tool results and the one error format (contracts/resolver-tools.md, "Error responses").

A failed call never ends the run and never shows the model an exception. It returns an
error that says what failed, why, what is true now, and what to do next.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

MAX_RESULT_CHARS = 1500
ERROR_CODES = frozenset(
    {
        "invalid_arguments",
        "field_out_of_scope",
        "page_not_found",
        "region_unreadable",
        "registry_unavailable",
        "registry_not_applicable",
        "vision_call_failed",
        "proposal_refused",
        "duplicate_call",
        "budget_soft_limit",
        "budget_hard_limit",
        "tool_internal_error",
    }
)


@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False
    error_code: str | None = None
    notice_code: str | None = None
    """A notice added to a normal result: ``duplicate_call`` or ``budget_soft_limit``."""

    def block(self, tool_use_id: str) -> dict[str, Any]:
        """The ``tool_result`` content block the model receives."""
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
        }

    def with_notice(self, notice: ToolResult) -> ToolResult:
        """This result, followed by a notice (both stay within the size limit)."""
        room = MAX_RESULT_CHARS - len(notice.content) - 1
        return replace(
            self,
            content=_cut(self.content, room) + "\n" + notice.content,
            notice_code=notice.error_code,
        )


def answer(text: str) -> ToolResult:
    return ToolResult(content=_cut(text, MAX_RESULT_CHARS))


def tool_error(
    code: str,
    *,
    what_failed: str,
    why: str,
    state: str,
    next_action: str,
    retryable: bool = False,
    allowed: list[Any] | None = None,
    is_error: bool = True,
) -> ToolResult:
    assert code in ERROR_CODES, code  # noqa: S101 - a programming error, caught by the tests
    message = f"{why} {state} {next_action}"
    body: dict[str, Any] = {
        "error_code": code,
        "what_failed": what_failed,
        "why": why,
        "state": state,
        "retryable": retryable,
        "next_action": next_action,
        "allowed": allowed,
        "message": message,
    }
    text = json.dumps(body, ensure_ascii=False)
    if len(text) > MAX_RESULT_CHARS:  # shorten the free text, never the structure
        body["what_failed"] = _cut(what_failed, 200)
        body["message"] = _cut(message, 400)
        text = json.dumps(body, ensure_ascii=False)
    return ToolResult(content=text, is_error=is_error, error_code=code)


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    note = " … (shortened: the rest was left out)"
    return text[: max(limit - len(note), 0)] + note
