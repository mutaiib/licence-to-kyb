"""Field confidence from evidence (US3, FR-019): which signals a field gets, how they
combine, and when a field is flagged as low confidence."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from licence_kyb.nodes.confidence import (
    SIGNALS,
    ConfidenceConfig,
    field_signals,
    low_confidence_results,
    weighted_score,
)
from licence_kyb.nodes.preprocess import Word
from licence_kyb.rules.base import failed, not_applicable, passed
from tests.builders import extraction, field

WEIGHTS = {
    "agreement": 3.0,
    "grounding": 3.0,
    "rules": 2.0,
    "ocr": 1.0,
    "corroboration": 2.0,
    "self_rating": 0.5,
}
CONFIG = ConfidenceConfig(weights=WEIGHTS, thresholds={"expiry_date": 0.9}, fitted=False)


def words_for(quote: str, conf: float) -> list[Word]:
    return [
        Word(1, t, (0.1 * i, 0.1, 0.1 * i + 0.05, 0.12), conf) for i, t in enumerate(quote.split())
    ]


def test_a_clean_field_has_every_signal_at_its_best() -> None:
    ex = extraction(expiry_date=field("2027-03-01", quote="Expiry Date 01/03/2027"))
    rules = [
        passed("evidence", "expiry_date", severity="warn"),
        passed("expiry", "expiry_date"),
        passed("registry", "licence_number", "expiry_date"),
    ]

    signals = field_signals(
        "expiry_date", ex, {"expiry_date": True}, rules, words_for("Expiry Date 01/03/2027", 0.96)
    )

    assert signals == {
        "agreement": 1.0,
        "grounding": 1.0,
        "rules": 1.0,
        "ocr": 0.96,
        "corroboration": 1.0,
        "self_rating": 1.0,
    }
    assert weighted_score(signals, WEIGHTS) > 0.99


def test_each_doubt_lowers_its_own_signal() -> None:
    ex = extraction(expiry_date=field("2027-03-01", quote="Expiry Date 01/03/2027"))
    rules = [
        failed("evidence", "expiry_date", severity="warn", reason="evidence_mismatch"),
        failed("number_format", "expiry_date", severity="block", reason="number_format"),
        failed(
            "registry",
            "licence_number",
            "expiry_date",
            severity="block",
            reason="registry_not_found",
        ),
    ]

    signals = field_signals("expiry_date", ex, {"expiry_date": False}, rules, [])

    assert signals["agreement"] == 0.0
    assert signals["grounding"] == 0.0
    assert signals["rules"] == 0.0
    assert signals["corroboration"] == 0.0
    assert "ocr" not in signals  # no words matched the quote: no OCR signal, not a zero


def test_a_warning_is_not_a_reading_doubt() -> None:
    ex = extraction(expiry_date=field("2026-06-11"))
    rules = [failed("expiry", "expiry_date", severity="warn", reason="near_expiry")]

    assert field_signals("expiry_date", ex, {}, rules, [])["rules"] == 1.0


def test_a_check_that_does_not_apply_gives_no_signal() -> None:
    ex = extraction(expiry_date=field("2027-03-01"))
    rules = [
        not_applicable("registry", "licence_number", "expiry_date"),
        not_applicable("evidence", "expiry_date", severity="warn"),
    ]

    signals = field_signals("expiry_date", ex, {}, rules, [])

    assert "corroboration" not in signals
    assert "grounding" not in signals
    assert "agreement" not in signals


def test_a_score_below_its_threshold_flags_the_field_as_low_confidence() -> None:
    scores = {
        "expiry_date": {"score": 0.81, "threshold": 0.9, "signals": {}},
        "licence_number": {"score": 0.95, "threshold": 0.9, "signals": {}},
    }

    flagged = low_confidence_results(scores)

    assert [(r.fields, r.reason_code, r.outcome) for r in flagged] == [
        (("expiry_date",), "low_confidence", "failed")
    ]


SIGNAL_VALUES = st.dictionaries(st.sampled_from(SIGNALS), st.floats(0, 1), min_size=1)


@given(SIGNAL_VALUES, st.sampled_from(SIGNALS), st.floats(0, 1))
def test_raising_any_signal_never_lowers_the_score(
    signals: dict[str, float], name: str, rise: float
) -> None:
    before = weighted_score(signals, WEIGHTS)
    higher = {**signals, name: min(1.0, signals.get(name, 0.0) + rise)}

    if name in signals:
        assert weighted_score(higher, WEIGHTS) >= before - 1e-9


@given(SIGNAL_VALUES)
def test_the_score_stays_between_0_and_1(signals: dict[str, float]) -> None:
    assert 0.0 <= weighted_score(signals, WEIGHTS) <= 1.0


def test_a_field_with_its_own_failed_check_is_not_also_flagged_as_low_confidence() -> None:
    scores = {"expiry_date": {"score": 0.6, "threshold": 0.9, "signals": {}}}
    expired = [failed("expiry", "expiry_date", severity="block", reason="expired")]

    assert low_confidence_results(scores, expired) == []
