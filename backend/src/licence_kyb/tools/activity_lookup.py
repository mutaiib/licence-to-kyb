"""licence_lookup_activity: search the activity catalogue by code or by words."""

from __future__ import annotations

from functools import cache
from typing import Any

import yaml

from licence_kyb.config import DATA_DIR
from licence_kyb.rules.activity import has_phrase, high_risk_catalogue, words
from licence_kyb.rules.base import normalise_text
from licence_kyb.tools import ToolContext
from licence_kyb.tools.errors import ToolResult, answer

MAX_MATCHES = 5


@cache
def _catalogue() -> tuple[dict[str, Any], ...]:
    data = yaml.safe_load((DATA_DIR / "activities_sample.yaml").read_text("utf-8"))
    return tuple(data["activities"])


def _high_risk(code: str, description: str) -> bool:
    text = words(description)
    return any(
        code in codes or any(has_phrase(text, k) for k in keys)
        for _id, codes, keys in high_risk_catalogue()
    )


def run(ctx: ToolContext, query: str) -> ToolResult:
    wanted = normalise_text(query)
    matches = [
        a
        for a in _catalogue()
        if wanted in a["code"] or wanted in normalise_text(a["en"]) or wanted in a["ar"]
    ]
    if not matches:
        return answer(f"No activity matches '{query}'. Try a code such as 4690.01 or one word.")
    listed = "; ".join(
        f"{a['code']} {a['en']}"
        + (" (high risk)" if _high_risk(a["code"], normalise_text(a["en"])) else "")
        for a in matches[:MAX_MATCHES]
    )
    return answer(f"{len(matches)} matches: {listed}.")
