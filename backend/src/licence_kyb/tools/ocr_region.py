"""licence_ocr_region: the OCR words of one region, with their confidence."""

from __future__ import annotations

from licence_kyb.tools import ToolContext
from licence_kyb.tools.errors import ToolResult, answer, tool_error
from licence_kyb.tools.regions import REGIONS, words_in


def run(ctx: ToolContext, page: int, region: str) -> ToolResult:
    found = words_in(ctx.words, page, region)
    if not found:
        readable = [r for r in REGIONS if r != region and words_in(ctx.words, page, r)]
        return tool_error(
            "region_unreadable",
            what_failed=f"licence_ocr_region for page {page}, region {region}",
            why=f"The OCR found no words in the {region} region of page {page}.",
            state="Nothing changed.",
            next_action="Try one of the regions in allowed, or propose nothing for this field.",
            allowed=readable or [r for r in REGIONS if r != region],
        )
    listed = ", ".join(f"'{w.text}' ({w.conf:.2f})" for w in found)
    mean = sum(w.conf for w in found) / len(found)
    return answer(f"Page {page}, {region}: {listed}. Mean confidence {mean:.2f}.")
