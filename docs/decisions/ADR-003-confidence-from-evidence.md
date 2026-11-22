# ADR-003 — Confidence from evidence, calibrated on labelled cases

## Status

Accepted.

## Context

The gate needs a confidence for each field. A model can rate its own confidence, but a self-rating is reliable only after calibration, and it can be high when the value is wrong.

## Decision

Each field's score is a transparent weighted sum of signals that code can check:

- agreement between two extraction passes
- the grounding match
- the rule results
- OCR confidence
- QR or registry corroboration
- the model's self-rating, at a small weight

`scripts/calibrate.py` fits the weights and the per-field thresholds on the labelled eval set. The target is at least 99% precision on critical fields among `ready` runs.

## Reasons

- **The review page can show why a score is low.** Each signal is visible.
- **The threshold reflects the cost of errors.** A wrong `ready` costs more than one extra review.
- **The method is simple enough to explain,** and simple enough to replace when more labelled data exists.

## Consequences

- Critical fields are extracted twice, which adds tokens to every run.
- Thresholds must be recalibrated when prompts or models change. The eval report shows when this is necessary.
