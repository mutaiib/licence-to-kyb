"""licence_reread_region: re-read one region with the vision model."""

from __future__ import annotations

from licence_kyb.tools import ToolContext
from licence_kyb.tools.errors import ToolResult, answer, tool_error

RETRIES = 1  # one code retry before the model sees an error


def run(ctx: ToolContext, page: int, field: str, region: str) -> ToolResult:
    current = getattr(ctx.extraction, field).value
    for attempt in range(RETRIES + 1):
        try:
            assert ctx.reread is not None  # noqa: S101 - the tool is offered only with vision
            text = ctx.reread(page, region)
            break
        except Exception:
            if attempt == RETRIES:
                return tool_error(
                    "vision_call_failed",
                    what_failed=f"licence_reread_region for page {page}, region {region}",
                    why="The vision re-read failed after a retry.",
                    state="Nothing changed.",
                    next_action=f"Call licence_ocr_region for page {page}, region {region}.",
                )
    return answer(
        f"Page {page}, {region} region, read again at high resolution. Text found: "
        f"'{text}'. The current value of {field} is '{current}'."
    )
