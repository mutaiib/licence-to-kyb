# Experiments

Each experiment changes one thing, runs the full eval suite, and records the measured result. Results replace the "pending" entries below.

| Experiment | Question | Compared | Result |
|---|---|---|---|
| Throughput probe (T034) | What output speed and latency do the planned calls get? | SDK probe, planned prompt sizes and efforts | pending |
| Resolver on vs. off | Does the agent improve accuracy or review rate enough to justify its cost? | full pipeline vs. resolver disabled | pending |
| Router model | Does a smaller model route as well? | `claude-haiku-5-5` vs. `claude-opus-5-5` at low effort | pending |
| Second extraction pass | Does pass agreement improve `ready` precision? | two passes vs. one pass on critical fields | pending |
| OCR text in the extract prompt | Does adding OCR text to the images improve field accuracy? | images + OCR vs. images only | pending |
| Secondary-pass model | Does a cheaper model keep pass agreement useful? | `claude-sonnet-5-5` vs. `claude-opus-5-5` for the secondary pass | pending |
| Reviewer time (SC-005) | How long does a reviewer take? | 5 clean and 5 flagged timed walkthroughs, from audit timestamps | pending |
| Rule test strength | Do the rule tests catch behaviour changes? | `mutmut` mutation score on `rules/` | pending |
