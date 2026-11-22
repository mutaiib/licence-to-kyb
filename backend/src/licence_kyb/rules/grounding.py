"""Evidence: each value appears in its quote, and the quote appears on the document.

Grounding proves the document says something; it does not prove the document is true
(handbook 05). A reviewer's value has no quote, so the check is not applicable to it.
"""

from __future__ import annotations

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
    if isinstance(value, date):
        return [value.strftime("%d/%m/%Y"), value.strftime("%d-%m-%Y"), value.isoformat()]
    return [str(value)]


def _grounded(name: str, f: Field[Any], ocr: str) -> bool:
    quote = normalise_text(f.evidence_quote or "")
    if not quote or fuzz.partial_ratio(quote, ocr) < QUOTE_THRESHOLD:
        return False
    if name in CODED:
        return True
    forms = [normalise_text(form) for form in _value_forms(f.value)]
    if name in EXACT:
        return any(form in quote for form in forms)
    return any(fuzz.partial_ratio(form, quote) >= VALUE_THRESHOLD for form in forms)


def evidence_rule(ctx: RuleContext) -> list[RuleResult]:
    results: list[RuleResult] = []
    ocr = normalise_text(ctx.ocr_text) if ctx.ocr_text else None
    for name in CHECKED:
        f: Field[Any] = getattr(ctx.extraction, name)
        if f.status != "present" or f.origin == "entered_by_reviewer":
            results.append(not_applicable("evidence", name, severity="warn"))
        elif ocr is None:
            results.append(failed("evidence", name, severity="warn", reason="evidence_mismatch"))
        elif _grounded(name, f, ocr):
            results.append(passed("evidence", name, severity="warn"))
        else:
            results.append(failed("evidence", name, severity="warn", reason="evidence_mismatch"))
    return results
