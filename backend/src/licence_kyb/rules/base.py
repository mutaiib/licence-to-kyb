"""Shared helpers for rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from licence_kyb.normalise import ascii_digits
from licence_kyb.schemas.results import ReasonCode, RuleResult, Severity

if TYPE_CHECKING:
    from licence_kyb.schemas.licence import Field


@dataclass(frozen=True)
class RegistryResult:
    """What the authority register says about a licence number."""

    found: bool
    status: str | None = None
    expiry_date: date | None = None
    trade_name_en: str | None = None


def passed(rule_id: str, *fields: str, severity: Severity = "block") -> RuleResult:
    return RuleResult(rule_id=rule_id, fields=fields, severity=severity, outcome="passed")


def failed(
    rule_id: str,
    *fields: str,
    severity: Severity,
    reason: ReasonCode,
    detail: dict[str, str] | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        fields=fields,
        severity=severity,
        outcome="failed",
        reason_code=reason,
        detail=detail or {},
    )


def not_applicable(rule_id: str, *fields: str, severity: Severity = "block") -> RuleResult:
    return RuleResult(rule_id=rule_id, fields=fields, severity=severity, outcome="not_applicable")


def present[T](f: Field[T]) -> T | None:
    return f.value if f.status == "present" else None


_LEGAL_SUFFIXES = {
    "l.l.c": "llc",
    "l.l.c.": "llc",
    "llc.": "llc",
    "est.": "est",
    "establishment": "est",
    "f.z.e": "fze",
    "f.z.e.": "fze",
    "fz-llc": "fzllc",
    "fz llc": "fzllc",
}


def normalise_name(text: str) -> str:
    """Lowercase, Unicode-normalise, unify legal suffixes, drop punctuation."""
    value = unicodedata.normalize("NFKC", text).casefold().strip()
    for raw, norm in _LEGAL_SUFFIXES.items():
        value = value.replace(raw, norm)
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


# Arabic diacritics (tashkeel) and the tatweel stretch: they change the look, not the word.
_ARABIC_MARKS = re.compile("[\\u064b-\\u065f\\u0640]")


def normalise_text(text: str) -> str:
    """For evidence matching: NFKC, ASCII digits, no Arabic marks, casefold, collapse
    whitespace, strip bidi marks."""
    value = ascii_digits(unicodedata.normalize("NFKC", text)).casefold()
    value = _ARABIC_MARKS.sub("", value)
    value = re.sub("[\\u200e\\u200f\\u202a-\\u202e]", "", value)
    return re.sub(r"\s+", " ", value).strip()
