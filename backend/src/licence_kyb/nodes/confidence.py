"""Field confidence from evidence (US3; FR-019, research R5, ADR-003).

Each field gets up to six signals, each from 0 to 1:

| Signal | 1.0 means | Absent when |
|---|---|---|
| ``agreement`` | the second, independent reading gives the same value | the field is not critical |
| ``grounding`` | the evidence quote is in the OCR text | the evidence check does not apply |
| ``rules`` | no blocking check fails on the field | always present |
| ``ocr`` | the OCR words of the quote were read with full confidence | no quote words found |
| ``corroboration`` | the QR code or the registry confirms the value | neither applies |
| ``self_rating`` | the model rated its own reading "high" | the model gave no rating |

A warning (for example ``near_expiry``) is a business flag, not a doubt about the reading,
so it does not lower the ``rules`` signal.

The score is the weighted average of the signals that are present. A missing signal is
left out, not counted as 0. Weights are never negative, so raising a signal never lowers
the score. Weights and thresholds come from ``config/thresholds.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from licence_kyb.config import load_yaml
from licence_kyb.nodes.preprocess import Word
from licence_kyb.rules.base import failed, normalise_text
from licence_kyb.schemas.licence import TradeLicenceExtraction
from licence_kyb.schemas.results import RuleResult

SIGNALS = ("agreement", "grounding", "rules", "ocr", "corroboration", "self_rating")
SELF_RATING = {"high": 1.0, "medium": 0.7, "low": 0.4}
CORROBORATING_RULES = frozenset({"qr", "registry"})


@dataclass(frozen=True)
class ConfidenceConfig:
    weights: dict[str, float]
    thresholds: dict[str, float]
    """Source field → the lowest score that needs no person. Fields not listed are scored
    and shown, but never flagged for low confidence."""
    fitted: bool
    """False until ``scripts/calibrate.py`` fits the thresholds on real model readings."""


def load_config(name: str = "thresholds.yaml") -> ConfidenceConfig:
    data = load_yaml(name)
    return ConfidenceConfig(
        weights={k: float(v) for k, v in data["weights"].items()},
        thresholds={k: float(v) for k, v in data["thresholds"].items()},
        fitted=bool(data["fitted"]),
    )


# ------------------------------------------------------------------ signals
def _outcome_signal(
    rules: list[RuleResult], rule_ids: set[str] | frozenset[str], source: str
) -> float | None:
    """1.0 if every matching rule passed, 0.0 if one failed, None if none applied."""
    matching = [
        r
        for r in rules
        if r.rule_id in rule_ids and source in r.fields and r.outcome != "not_applicable"
    ]
    if not matching:
        return None
    return 0.0 if any(r.counts_as_failed for r in matching) else 1.0


def _ocr_signal(words: list[Word], quote: str | None, page: int | None) -> float | None:
    """The mean OCR confidence of the words that make up the evidence quote."""
    if not quote:
        return None
    tokens = set(normalise_text(quote).split())
    confs = [
        w.conf
        for w in words
        if (page is None or w.page == page) and normalise_text(w.text) in tokens
    ]
    return sum(confs) / len(confs) if confs else None


def field_signals(
    source: str,
    extraction: TradeLicenceExtraction,
    agreement: dict[str, bool],
    rules: list[RuleResult],
    words: list[Word],
) -> dict[str, float]:
    field = getattr(extraction, source)
    blocking = [
        r
        for r in rules
        if source in r.fields and r.severity == "block" and r.rule_id not in CORROBORATING_RULES
    ]
    signals: dict[str, float | None] = {
        "agreement": None if source not in agreement else float(agreement[source]),
        "grounding": _outcome_signal(rules, {"evidence"}, source),
        "rules": 0.0 if any(r.counts_as_failed for r in blocking) else 1.0,
        "ocr": _ocr_signal(words, field.evidence_quote, field.page),
        "corroboration": _outcome_signal(rules, CORROBORATING_RULES, source),
        "self_rating": SELF_RATING.get(field.self_confidence),
    }
    return {name: value for name, value in signals.items() if value is not None}


def weighted_score(signals: dict[str, float], weights: dict[str, float]) -> float:
    total = sum(weights.get(name, 0.0) for name in signals)
    if total == 0:
        return 0.0
    return sum(value * weights.get(name, 0.0) for name, value in signals.items()) / total


# ------------------------------------------------------------------ per run
def score_fields(
    extraction: TradeLicenceExtraction,
    agreement: dict[str, bool],
    rules: list[RuleResult],
    words: list[Word],
    config: ConfidenceConfig,
) -> dict[str, dict[str, Any]]:
    """Source field → ``{score, threshold, signals}`` for every field the model read."""
    scores: dict[str, dict[str, Any]] = {}
    for source in TradeLicenceExtraction.model_fields:
        field = getattr(extraction, source)
        if field.status != "present" or field.origin == "entered_by_reviewer":
            continue  # nothing read, or typed by a person: no reading to be unsure about
        signals = field_signals(source, extraction, agreement, rules, words)
        scores[source] = {
            "score": round(weighted_score(signals, config.weights), 4),
            "threshold": config.thresholds.get(source),
            "signals": signals,
        }
    return scores


def low_confidence_results(scores: dict[str, dict[str, Any]]) -> list[RuleResult]:
    """A failed ``confidence`` check for each field below its threshold. The form, the review
    page and the review actions then treat it like any other failed check."""
    return [
        failed(
            "confidence",
            source,
            severity="warn",
            reason="low_confidence",
            detail={"score": f"{s['score']:.2f}", "threshold": f"{s['threshold']:.2f}"},
        )
        for source, s in scores.items()
        if s.get("threshold") is not None and s["score"] < s["threshold"]
    ]
