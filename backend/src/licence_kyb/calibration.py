"""Fit per-field confidence thresholds on labelled readings (US3; research R5, R8a).

Input: one ``SignalRow`` per field per case from an eval run: the field's signals and
whether the model's value was right. Only rows from the *calibration* split are used, so
the *test* split stays clean for reporting.

For each configured field the fit picks the lowest threshold at which at least
``MIN_ROWS`` readings pass it and they are right at least ``target_precision`` of the time.
A field that never gets there (too few rows, or too many wrong ones) gets a threshold above
1, so it always goes to a person. The fit summary also shows the Wilson lower bound, so a
reader can see how much the precision rests on.

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
"""A threshold needs at least this many readings at or above it to be trusted."""


@dataclass(frozen=True)
class SignalRow:
    field: str
    split: str
    signals: dict[str, float]
    correct: bool
    source: str = ""
    """What produced the reading: a model profile name, or ``scripted`` (never fitted)."""


def precision_at(
    rows: list[SignalRow], weights: dict[str, float], field: str, threshold: float
) -> float | None:
    """How often the field's value is right among the rows that reach the threshold; None
    when no row reaches it."""
    above = [
        r for r in rows if r.field == field and weighted_score(r.signals, weights) >= threshold
    ]
    return sum(r.correct for r in above) / len(above) if above else None


def fit_thresholds(
    rows: list[SignalRow],
    weights: dict[str, float],
    target_precision: float = 0.99,
    *,
    defaults: dict[str, float],
) -> dict[str, float]:
    """One threshold for each field in ``defaults`` (the configured fields). A field with
    no usable rows gets ``NEVER``: it must still go to a person, never lose its flag."""
    by_field: dict[str, list[SignalRow]] = defaultdict(list)
    for row in rows:
        if row.split == "calibration":
            by_field[row.field].append(row)

    fitted: dict[str, float] = {}
    for field in sorted(defaults):
        fitted[field] = NEVER
        field_rows = by_field.get(field, [])
        # Try each observed score as a threshold, lowest first; keep the first that works.
        for candidate in sorted({weighted_score(r.signals, weights) for r in field_rows}):
            reached = [r for r in field_rows if weighted_score(r.signals, weights) >= candidate]
            if len(reached) < MIN_ROWS:
                break  # higher thresholds only leave fewer rows
            if sum(r.correct for r in reached) / len(reached) >= target_precision:
                fitted[field] = round(candidate, 4)
                break
    return fitted
