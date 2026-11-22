"""Evidence: each value appears in its quote, and the quote appears on the document.

Grounding proves the document says something; it does not prove the document is true
(handbook 05). A reviewer's value has no quote, so the check is not applicable to it.
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Any

from rapidfuzz import fuzz

from licence_kyb.rules.base import failed, normalise_text, not_applicable, passed

if TYPE_CHECKING:
    from licence_kyb.rules import RuleContext
    from licence_kyb.schemas.licence import Field
    from licence_kyb.schemas.results import RuleResult

QUOTE_THRESHOLD = 85
VALUE_THRESHOLD = 90
# Fields whose value is a code (not printed verbatim): only the quote is checked.
CODED = frozenset({"legal_form", "licence_category", "issuing_authority", "activities", "people"})
LISTS = frozenset({"activities", "people"})
# Dates and identifiers must appear exactly: one wrong digit is a different value.
EXACT = frozenset(
    {
        "licence_number",
        "unified_licence_number",
        "register_number",
        "chamber_number",
        "establishment_date",
        "issue_date",
        "expiry_date",
    }
)
CHECKED = (
    "licence_number",
    "unified_licence_number",
    "register_number",
    "chamber_number",
    "trade_name_en",
    "trade_name_ar",
    "legal_form",
    "licence_category",
    "issuing_authority",
    "establishment_date",
    "issue_date",
    "expiry_date",
    "activities",
    "people",
    "address",
)


def _value_forms(value: Any) -> list[str]:
    """The ways a value can be printed: a date with or without leading zeros, with /, - or ."""
    if isinstance(value, date):
        padded = (f"{value.day:02d}", f"{value.month:02d}", str(value.year))
        plain = (str(value.day), str(value.month), str(value.year))
        return [sep.join(parts) for parts in (padded, plain) for sep in "/-."] + [value.isoformat()]
    return [str(value)]


def _has_token(text: str, value: str) -> bool:
    """``value`` appears as a whole token: "39353" is not in "Chamber No 393530"."""
    return re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-])", text) is not None


def _quote_on_page(quote: str, ocr: str) -> bool:
    """A PDF text layer can return Arabic in visual (reversed) order, so try both."""
    return (
        max(fuzz.partial_ratio(quote, ocr), fuzz.partial_ratio(quote, ocr[::-1])) >= QUOTE_THRESHOLD
    )


def _list_grounded(f: Field[Any], ocr: str) -> bool:
    """A list is grounded when each element's own fields are: one quote cannot span a table."""
    for element in f.value or []:
        parts = [
            getattr(element, k) for k in ("name", "code", "description_en") if hasattr(element, k)
        ]
        for part in parts:
            if (
                part.status == "present"
                and part.origin == "read"
                and not _quote_on_page(normalise_text(part.evidence_quote or ""), ocr)
            ):
                return False
    return True


def _grounded(name: str, f: Field[Any], ocr: str) -> bool:
    if name in LISTS:
        return _list_grounded(f, ocr)
    quote = normalise_text(f.evidence_quote or "")
    if not quote or not _quote_on_page(quote, ocr):
        return False
    if name in CODED:
        return True
    forms = [normalise_text(form) for form in _value_forms(f.value)]
    if name in EXACT:
        # Exact in the quote, and exact on the document: a quote that repeats a misread
        # digit still matches the page fuzzily, so the value itself must be found.
        return any(_has_token(quote, form) and _has_token(ocr, form) for form in forms)
    return any(fuzz.partial_ratio(form, quote) >= VALUE_THRESHOLD for form in forms)


def evidence_rule(ctx: RuleContext) -> list[RuleResult]:
    results: list[RuleResult] = []
    ocr = normalise_text(ctx.ocr_text) if ctx.ocr_text else None
    for name in CHECKED:
        f: Field[Any] = getattr(ctx.extraction, name)
        if f.status != "present" or f.origin == "entered_by_reviewer":
            results.append(not_applicable("evidence", name, severity="warn"))
        elif ocr is not None and _grounded(name, f, ocr):
            results.append(passed("evidence", name, severity="warn"))
        else:  # no OCR text, or the value is not on the document
            results.append(failed("evidence", name, severity="warn", reason="evidence_mismatch"))
    return results
