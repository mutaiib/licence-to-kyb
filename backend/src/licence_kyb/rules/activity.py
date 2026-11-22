"""High-risk activities need more checks (FR-012; data/high_risk_activities.yaml)."""

from __future__ import annotations

import re
from functools import cache
from typing import TYPE_CHECKING

import yaml

from licence_kyb.config import DATA_DIR
from licence_kyb.rules.base import failed, normalise_text, not_applicable, passed, present

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.results import RuleResult

DATA = DATA_DIR / "high_risk_activities.yaml"


Words = tuple[str, ...]
ARTICLE = "ال"  # the Arabic definite article, written joined to its word


def words(text: str) -> Words:
    """Lower-case whole words, without the Arabic article "ال" (التجارة → تجارة)."""
    found = re.findall(r"\w+", normalise_text(text))
    return tuple(w.removeprefix(ARTICLE) if len(w) > len(ARTICLE) + 1 else w for w in found)


def _same_word(word: str, keyword: str) -> bool:
    """A word matches its keyword or the keyword's plural: never a longer word (golden)."""
    return word in (keyword, f"{keyword}s", f"{keyword}es")


def has_phrase(text: Words, phrase: Words) -> bool:
    """``phrase`` appears in ``text`` as consecutive whole words."""
    n = len(phrase)
    return any(
        all(_same_word(text[i + j], phrase[j]) for j in range(n)) for i in range(len(text) - n + 1)
    )


@cache
def high_risk_catalogue() -> tuple[tuple[str, frozenset[str], tuple[Words, ...]], ...]:
    entries = yaml.safe_load(DATA.read_text("utf-8"))["high_risk"]
    return tuple(
        (e["id"], frozenset(e["codes"]), tuple(words(k) for k in e["keywords"])) for e in entries
    )


def activity_rule(ctx: RuleContext) -> list[RuleResult]:
    activities = present(ctx.extraction.activities)
    if not activities:
        return [not_applicable("high_risk_activity", "activities", severity="warn")]
    hits: list[str] = []
    for act in activities:
        code = present(act.code) or ""
        text = words(
            " ".join(filter(None, (present(act.description_en), present(act.description_ar))))
        )
        for _id, codes, keywords in high_risk_catalogue():
            if code in codes or any(has_phrase(text, k) for k in keywords):
                hits.append(present(act.description_en) or code)
                break
    if not hits:
        return [passed("high_risk_activity", "activities", severity="warn")]
    return [
        failed(
            "high_risk_activity",
            "activities",
            severity="warn",
            reason="high_risk_activity",
            detail={"activity": "; ".join(hits)},
        )
    ]
