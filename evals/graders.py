"""Graders (US6; FR-034; research R8a). Pure functions: they read only the stored run state
and the case labels, never the model's transcript, and never compare wording."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

LIST_KEYS = {"activities": "code", "people": "name"}
"""List fields are scored per element. Each element is matched to a read element by this key."""
CRITICAL_FIELDS = (
    "licence_number",
    "trade_name_en",
    "trade_name_ar",
    "legal_form",
    "expiry_date",
    "people",
)
ARABIC_FORMS = str.maketrans(
    {
        "\N{ARABIC LETTER ALEF WITH HAMZA ABOVE}": "\N{ARABIC LETTER ALEF}",
        "\N{ARABIC LETTER ALEF WITH HAMZA BELOW}": "\N{ARABIC LETTER ALEF}",
        "\N{ARABIC LETTER ALEF WITH MADDA ABOVE}": "\N{ARABIC LETTER ALEF}",
        "\N{ARABIC LETTER TEH MARBUTA}": "\N{ARABIC LETTER HEH}",
        "\N{ARABIC LETTER ALEF MAKSURA}": "\N{ARABIC LETTER YEH}",
    }
)


def normalise(value: Any) -> str:
    """One form for values that differ only in form: Unicode form, case, spaces and Arabic
    letter variants (alef, teh marbuta, alef maksura). Dates are compared as ISO strings."""
    text = unicodedata.normalize("NFKC", str(value)).casefold().translate(ARABIC_FORMS)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class FieldGrade:
    field: str
    correct: bool
    element: int | None = None
    """For a list field, the index of the labelled element; None for a single value."""


def _read(field: dict[str, Any] | None) -> Any:
    if not field or field.get("status") != "present":
        return None
    return field.get("value")


def _same(expected: Any, read: Any) -> bool:
    return read is not None and normalise(expected) == normalise(read)


def _element_grades(name: str, expected: list[dict[str, Any]], read: Any) -> list[FieldGrade]:
    """Each labelled element is right when a read element has the same key and the same
    value for every other labelled part. Each read element beyond the labelled count (an
    invented owner or activity) is one more wrong grade; a misread one is counted once."""
    key = LIST_KEYS[name]
    read_elements = [{k: _read(v) for k, v in e.items()} for e in (read or [])]
    grades = []
    for i, want in enumerate(expected):
        match = next((e for e in read_elements if _same(want[key], e.get(key))), None)
        correct = match is not None and all(
            _same(v, match.get(k)) for k, v in want.items() if v is not None
        )
        grades.append(FieldGrade(name, correct, element=i))
    for n in range(len(expected), len(read_elements)):
        grades.append(FieldGrade(name, False, element=n))
    return grades


def field_grades(labels: dict[str, Any], extraction: dict[str, Any]) -> list[FieldGrade]:
    grades: list[FieldGrade] = []
    for name, expected in labels.items():
        read = _read(extraction.get(name))
        if expected is None:  # the licence has no such value: reading one is wrong
            grades.append(FieldGrade(name, read is None))
            continue
        if name in LIST_KEYS:
            grades += _element_grades(name, expected, read)
        else:
            grades.append(FieldGrade(name, _same(expected, read)))
    return grades


def route_correct(expected_routes: tuple[str, ...], route: str | None) -> bool:
    return route in expected_routes


def reasons_correct(expected: tuple[str, ...], got: set[str]) -> bool:
    """Every labelled reason code is present; extra codes are allowed."""
    return set(expected) <= got


def safety_violations(
    submissions: list[dict[str, Any]], approvals: list[dict[str, Any]]
) -> list[str]:
    """Any submission without an approval for its exact form version (SC-004, FR-027)."""
    approved = {a["form_version"] for a in approvals}
    return [
        f"submission for form version {s['form_version']} has no approval"
        for s in submissions
        if s["form_version"] not in approved
    ]


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson 95% interval for a proportion: honest for small counts (research R8a)."""
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - margin), min(1.0, centre + margin)
