# Experiments

Each experiment changes one thing, runs the full eval suite, and records the measured result. Results replace the "pending" entries below.

| Experiment | Question | Compared | Result |
|---|---|---|---|
| Throughput probe (T034) | What output speed and latency do the planned calls get? | SDK probe, planned prompt sizes and efforts | pending |
| Resolver on vs. off | Does the agent improve accuracy or review rate enough to justify its cost? | full pipeline vs. resolver disabled | Scripted model: 0 cases change (a model that reads from labels never needs a re-read). Needs real readings on the full suite: a local CPU model takes 25 to 50 minutes per licence (see below), so this waits for the API or a GPU. |
| Router model | Does a smaller model route as well? | `claude-haiku-5-5` vs. `claude-opus-5-5` at low effort | pending |
| Second extraction pass | Does pass agreement improve `ready` precision? | two passes vs. one pass on critical fields | pending |
| OCR text in the extract prompt | Does adding OCR text to the images improve field accuracy? | images + OCR vs. images only | pending |
| Secondary-pass model | Does a cheaper model keep pass agreement useful? | `claude-sonnet-5-5` vs. `claude-opus-5-5` for the secondary pass | pending |
| Reviewer time (SC-005) | How long does a reviewer take? | 5 clean and 5 flagged timed walkthroughs, from audit timestamps | pending |
| Rule test strength | Do the rule tests catch behaviour changes? | `mutmut` mutation score on `rules/` | 64% at first; **77%** (790 of 1,029) after the tests below |

## First real readings: a local model on a CPU (T111, 2026-11-22)

**Set-up:** Mistral-7B-Instruct v0.2 (Q4_K_M GGUF) on llama.cpp b11985, CPU only (16 threads), profile `local`, resolver on. Generation speed: about 2.6 tokens per second. Reports: `evals/reports/local-smoke/` and `evals/reports/local-public/`.

| Case | Fields correct | Route | Reasons | Time |
|---|---|---|---|---|
| `clean_002` (synthetic, clean) | 9 of 12 | needs review (label: ready) | `processing_failed`: the second reading failed the schema twice | 49 min |
| ADCB licence (public, real) | 6 of 10 | needs review (accepted) | `evidence_mismatch`, `resolver_budget`, `arabic_name_missing`, `ubo_needs_examination` | 27 min |

**What it shows:**
- **A weak model sends work to a person; it does not submit wrong values.** Neither run reached "ready". On ADCB the evidence check caught the misread values and the resolver ran out of budget, as designed. No safety violations.
- **The misses are mostly the hard fields.** On both licences the model read the licence number, the legal form, the English trade name, and the issue and expiry dates correctly. It missed the activities on both; the Arabic name and the issuing authority on `clean_002`; and the people, the chamber number and the establishment date on ADCB. Lists and bilingual fields fail most.
- **The report hid one failure.** Reason accuracy allows extra codes, so `processing_failed` on a clean case still scored 100% there. The report now counts runs that stopped in processing.
- **Speed rules out the full suite on this machine.** At 25 to 50 minutes per licence, the 45 test cases would take 19 to 37 hours. The full eval (T101), the resolver on/off comparison and fitted thresholds need the Claude API or a GPU.

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
| p95 per stage | preprocess 1.7 s; every other stage well inside its budget |

Found by this first run: demo mode matched a short licence number inside a longer one and
answered for the wrong case (fixed: whole numbers, longest first). The report and its
cases are in `evals/reports/scripted-baseline/`; `evals/reports/baseline.json` is the
baseline that `make eval-compare` uses.

## Mutation testing of the rules (T100, 2026-11-22)

`make mutation` runs `mutmut` 3.8.1 on `backend/src/licence_kyb/rules/` against
`tests/unit/test_rules.py`. A mutant is a small change to the code (`or` to `and`, a changed
field name); a strong test suite fails on it ("killed").

| Run | Killed | Survived | Score |
|---|---|---|---|
| First run | 661 | 368 | 64% |
| After the contract and boundary tests | 790 | 239 | **77%** |

What the survivors taught, and what was added:
- **A result with a wrong rule ID or field survived.** The review page attaches each result
  to its fields by name, so a test now pins every rule's fields across varied inputs.
- **The QR rule's `or` survived as `and`.** No test had a QR code without a number, or the
  reverse; both are now cases.
- **Expiry boundaries** (31, 30, 29, 1, 0 days) are now explicit cases.
- **Owner branches** (one owner of a sole establishment, no owners table, no shares) are now
  inputs.

What still survives, on purpose: changes to the wording inside `detail` values (tests check
outcomes, never wording; constitution, testing principle), and equivalent mutants that do
not change behaviour (for example a default that is never read).
