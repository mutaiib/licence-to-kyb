"""Threshold fitting (US3, T070): the fitted thresholds reach the precision target on the
calibration split, and the test split is never used."""

from __future__ import annotations

import random

from licence_kyb.calibration import SignalRow, fit_thresholds, precision_at
from licence_kyb.config import default_profile_name

WEIGHTS = {
    "agreement": 3.0,
    "grounding": 3.0,
    "rules": 2.0,
    "ocr": 1.0,
    "corroboration": 2.0,
    "self_rating": 0.5,
}

DEFAULTS = {"licence_number": 0.9, "expiry_date": 0.9, "people": 0.85}


def rows(seed: int, n: int, split: str = "calibration") -> list[SignalRow]:
    """Synthetic rows: a right value tends to have strong signals; a wrong one weak ones."""
    rng = random.Random(seed)  # noqa: S311 - test data, not security
    out = []
    for _ in range(n):
        correct = rng.random() < 0.85
        level = rng.uniform(0.7, 1.0) if correct else rng.uniform(0.0, 0.8)
        signals = {s: min(1.0, max(0.0, level + rng.uniform(-0.1, 0.1))) for s in WEIGHTS}
        out.append(SignalRow(field="expiry_date", split=split, signals=signals, correct=correct))
    return out


def test_fitted_thresholds_reach_the_precision_target_on_the_calibration_split() -> None:
    calibration = rows(seed=1, n=400)

    fit = fit_thresholds(calibration, WEIGHTS, target_precision=0.99, defaults=DEFAULTS)

    threshold = fit["expiry_date"]
    assert precision_at(calibration, WEIGHTS, "expiry_date", threshold) >= 0.99
    assert threshold < 1.0  # the fit still lets some fields through


def test_the_test_split_never_changes_the_fit() -> None:
    calibration = rows(seed=1, n=400)
    misleading_test = [
        SignalRow("expiry_date", "test", {s: 1.0 for s in WEIGHTS}, correct=False)
        for _ in range(500)
    ]

    alone = fit_thresholds(calibration, WEIGHTS, target_precision=0.99, defaults=DEFAULTS)
    mixed = fit_thresholds(
        calibration + misleading_test, WEIGHTS, target_precision=0.99, defaults=DEFAULTS
    )

    assert alone == mixed


def test_a_field_that_never_reaches_the_target_always_goes_to_a_person() -> None:
    always_wrong = [
        SignalRow("legal_form", "calibration", {s: 1.0 for s in WEIGHTS}, False) for _ in range(50)
    ]

    fit = fit_thresholds(
        always_wrong, WEIGHTS, target_precision=0.99, defaults={"legal_form": 0.85}
    )
    assert fit["legal_form"] > 1.0


def test_a_configured_field_with_no_rows_keeps_going_to_a_person() -> None:
    """A field with no readings must not lose its threshold: no threshold means no flag."""
    fit = fit_thresholds(rows(seed=1, n=400), WEIGHTS, defaults=DEFAULTS)

    assert set(fit) == set(DEFAULTS)
    assert fit["people"] > 1.0
    assert fit["licence_number"] > 1.0


def test_a_threshold_needs_enough_rows_at_or_above_it() -> None:
    """One right row at the top and many wrong rows below is not evidence for that score."""
    top = [SignalRow("expiry_date", "calibration", {s: 1.0 for s in WEIGHTS}, True)]
    below = [
        SignalRow("expiry_date", "calibration", {s: 0.2 for s in WEIGHTS}, False) for _ in range(25)
    ]

    assert fit_thresholds(top + below, WEIGHTS, defaults=DEFAULTS)["expiry_date"] > 1.0


def test_precision_is_unknown_when_no_row_reaches_the_threshold() -> None:
    assert precision_at(rows(seed=1, n=50), WEIGHTS, "expiry_date", 1.01) is None


def test_the_default_profile_has_a_name() -> None:
    assert default_profile_name() == "anthropic"
