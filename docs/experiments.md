# Experiments

Each experiment changes one thing, runs the full eval suite, and records the measured result. Results replace the "pending" entries below.

| Experiment | Question | Compared | Result |
|---|---|---|---|
| Throughput probe (T034) | What output speed and latency do the planned calls get? | SDK probe, planned prompt sizes and efforts | pending |
| Resolver on vs. off | Does the agent improve accuracy or review rate enough to justify its cost? | full pipeline vs. resolver disabled | Scripted model: 0 cases change (a model that reads from labels never needs a re-read). Needs real readings: pending on the local model (T111) or the API. |
| Router model | Does a smaller model route as well? | `claude-haiku-5-5` vs. `claude-opus-5-5` at low effort | pending |
| Second extraction pass | Does pass agreement improve `ready` precision? | two passes vs. one pass on critical fields | pending |
| OCR text in the extract prompt | Does adding OCR text to the images improve field accuracy? | images + OCR vs. images only | pending |
| Secondary-pass model | Does a cheaper model keep pass agreement useful? | `claude-sonnet-5-5` vs. `claude-opus-5-5` for the secondary pass | pending |
| Reviewer time (SC-005) | How long does a reviewer take? | 5 clean and 5 flagged timed walkthroughs, from audit timestamps | pending |
| Rule test strength | Do the rule tests catch behaviour changes? | `mutmut` mutation score on `rules/` | pending |

## Eval baseline: scripted model (2026-11-22)

`python -m evals.run --model scripted` on the 45 test-split cases. **The scripted model answers
from the case labels, so this run checks the pipeline (OCR, rules, confidence, gate, resolver
flow), not the model's reading.** Real reading quality needs `--model profile`.

| Metric | Value |
|---|---|
| Route accuracy | 100% |
| Reason-code accuracy | 100% |
| `ready` precision (critical fields) | 15/15, Wilson 95% [0.80, 1.00] |
| Review rate, realistic mix | 28.2% |
| Field accuracy | 100% for every field |
| Safety violations | 0 |
| p95 per stage | preprocess 1.6 s; every other stage well inside its budget |

Found by this first run: demo mode matched a short licence number inside a longer one and
answered for the wrong case (fixed: whole numbers, longest first). The report and its
cases are in `evals/reports/scripted-baseline/`; `evals/reports/baseline.json` is the
baseline that `make eval-compare` uses.
