"""Fit per-field confidence thresholds on labelled readings (US3; research R5, R8a).

Input: one ``SignalRow`` per field per case from an eval run: the field's signals and
whether the model's value was right. Only rows from the *calibration* split are used, so
the *test* split stays clean for reporting.

For each field the fit picks the lowest threshold at which the fields that pass it are
right at least ``target_precision`` of the time. A field that never reaches the target
gets a threshold above 1, so it always goes to a person.

The weights are not fitted: they stay the documented defaults in ``thresholds.yaml``.
Fitting weights needs more labelled cases than this project has (research R5).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from licence_kyb.nodes.confidence import weighted_score

NEVER = 1.01
"""A threshold no score can reach: the field always goes to a person."""
MIN_ROWS = 20
"""Fewer rows than this for a field: too few to trust a fit, so the field goes to a person."""


@dataclass(frozen=True)
class SignalRow:
    field: str
    split: str
    signals: dict[str, float]
    correct: bool


def precision_at(
    rows: list[SignalRow], weights: dict[str, float], field: str, threshold: float
) -> float:
    """How often the field's value is right among the rows that reach the threshold."""
    above = [
        r for r in rows if r.field == field and weighted_score(r.signals, weights) >= threshold
    ]
    return sum(r.correct for r in above) / len(above) if above else 1.0


def fit_thresholds(
    rows: list[SignalRow], weights: dict[str, float], target_precision: float = 0.99
) -> dict[str, float]:
    by_field: dict[str, list[SignalRow]] = defaultdict(list)
    for row in rows:
        if row.split == "calibration":
            by_field[row.field].append(row)

    fitted: dict[str, float] = {}
    for field, field_rows in sorted(by_field.items()):
        fitted[field] = NEVER
        if len(field_rows) < MIN_ROWS:
            continue
        # Try each observed score as a threshold, lowest first; keep the first that works.
        for candidate in sorted({weighted_score(r.signals, weights) for r in field_rows}):
            reached = [r for r in field_rows if weighted_score(r.signals, weights) >= candidate]
            if sum(r.correct for r in reached) / len(reached) >= target_precision:
                fitted[field] = round(candidate, 4)
                break
    return fitted
