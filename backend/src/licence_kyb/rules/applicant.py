"""The business name on the application matches the licence (FR-012).

Two names match when they are close overall (with or without spaces: "AlNoor" and
"Al Noor") **and** their distinctive words are close: "Zenith Trading LLC" and "Zenith
Foods Trading LLC" share most letters, but "Foods" makes them two businesses. An Arabic
name on the application is compared with the Arabic trade name.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

from licence_kyb.rules.base import failed, normalise_name, not_applicable, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult

# Words that many business names share: they say what a business is, not which one.
GENERIC = frozenset(
    {
        "llc", "est", "fze", "fzco", "fzllc", "co", "company", "limited", "liability",
        "sole", "establishment", "trading", "general", "gen", "services", "service",
        "technologies", "technology", "consultancy", "consultants", "group", "holding",
        "international", "the", "and", "of", "شركة", "مؤسسة", "ذ", "م",
    }
)  # fmt: skip
DISTINCTIVE_MIN = 90  # 0-100: how close the distinctive words must be


def _is_arabic(text: str) -> bool:
    return re.search("[\\u0600-\\u06ff]", text) is not None


def _distinctive(name: str) -> str:
    return "".join(w for w in normalise_name(name).split() if w not in GENERIC)


def names_match(applicant: str, licence: str, threshold: float) -> bool:
    a, b = normalise_name(applicant), normalise_name(licence)
    overall = max(fuzz.token_sort_ratio(a, b), fuzz.ratio(a.replace(" ", ""), b.replace(" ", "")))
    core = fuzz.ratio(_distinctive(applicant), _distinctive(licence))
    return overall / 100 >= threshold and core >= DISTINCTIVE_MIN


def applicant_rule(ctx: RuleContext) -> list[RuleResult]:
    applicant = ctx.applicant_name.strip()
    field_name = "trade_name_ar" if _is_arabic(applicant) else "trade_name_en"
    licence = present(getattr(ctx.extraction, field_name))
    if licence is None or not applicant:
        return [not_applicable("applicant_name", field_name, severity="warn")]
    if names_match(applicant, licence, ctx.applicant_threshold):
        return [passed("applicant_name", field_name, severity="warn")]
    return [failed("applicant_name", field_name, severity="warn", reason="applicant_name_mismatch")]
