# 05 — Grounding and confidence

## In one minute

A model's statement about a document is a claim. Make every value carry the exact text it came from, and check that text in code.

A model's self-rated confidence is unreliable until it is calibrated. So score confidence from signals code can check, and fit the thresholds on labelled data.

## Rules

- **Ground every value:**
  - The value must appear in its quote.
  - The quote must appear in the OCR text (fuzzy match ≥ 0.85).
  - **A date or an identifier must also appear exactly in the OCR text.** A quote that repeats a misread digit ("11/06/2028" for a printed "11/06/2026") still matches the page fuzzily, so the value itself must be found ([16](16-what-the-checks-caught.md)).
  - A failed check flags the field. It does not reject the case.
- **Grounding proves the document says something.** It does not prove the document is true or current. For that, use corroboration: the QR code, or a registry.
- **Build confidence from checkable signals:**
  - agreement between two independent readings
  - the grounding score
  - the rule results
  - the OCR quality in the evidence region
  - corroboration
  - the model's self-rating, at a small weight only
- **Calibrate on one split and report on another.** Fitting the thresholds and measuring on the same cases overfits.
- **Report intervals, not just rates.** 20 out of 20 correct gives a Wilson 95% lower bound of about 84%, not 100%. Showing 99% needs about 380 or more correct `ready` runs with zero errors.
- **Choose the threshold by the cost of errors.** A wrong "ready" costs more than one extra review, so maximise ready coverage subject to ≥ 99% precision on critical fields.
- **Never take an irreversible decision on an uncorroborated value.** Auto-reject only when two readings agree and grounding passes, or when the registry confirms the value. (A QR code that carries only the licence number can confirm the number, never a date.)
- **A fallback model invalidates calibration.** If a backup model served the call, the run cannot be "ready".

## In this repository

- **Evidence fields:** `evidence_quote` and `page` on every value ([data model](../../specs/001-licence-to-kyb/data-model.md)).
- **The signals and calibration:** [architecture §8](../architecture.md#8-confidence-and-the-gate), [ADR-003](../decisions/ADR-003-confidence-from-evidence.md).
- **Corroborated rejection:** FR-037 and the `expiry_uncertain` reason ([spec](../../specs/001-licence-to-kyb/spec.md)).
- **Statistics:** the 50/50 split, the Wilson bound and the 400-ready-run precision set ([research R8a](../../specs/001-licence-to-kyb/research.md), [test cases](../../specs/001-licence-to-kyb/test-cases.md)).

## Mistakes to avoid

- **Using the model's "high confidence" as the gate.** It can be high when the value is wrong.
- **Auto-rejecting on a misread date.** Found in review: an expiry read wrongly by the model would have rejected a valid merchant with no person involved.
- **Claiming 99% precision from 20 cases.** Found in review. The claim needs an interval and enough data.
- **Out-of-scope rejection from a model label alone.** Found in review. Code now checks that the text contains no labelled licence number and no licence title.

## Self-check

<details><summary>1. Both extraction passes read expiry 2026-05-31 (expired), but the quote does not match the OCR text. Route?</summary>

`needs_review` with `expiry_uncertain`. The expiry is not corroborated, because grounding failed and there is no registry confirmation. A person must decide.
</details>

<details><summary>2. Why weight the model's self-rating low?</summary>

It is not calibrated: the model can be confidently wrong. Agreement, grounding and corroboration are checkable, so they carry the weight.
</details>

<details><summary>3. All 30 "ready" test cases were correct. What precision can you claim?</summary>

Only the Wilson 95% lower bound, about 89%. To claim 99%, you need roughly 380 or more `ready` runs with no errors.
</details>
