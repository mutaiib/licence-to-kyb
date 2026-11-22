# 13 — Lessons from the design reviews

The design went through three independent, read-only reviews before any code was written. Each review ran Spec Kit's `analyze` across every artifact.

| Round | Findings |
|---|---|
| 1 | 50 findings: 4 critical, 15 high |
| 2 | 17 new issues, created by the fixes themselves |
| 3 | 9 small issues |

These are the mistakes most worth remembering. Each one is written as the mistake, why it mattered, the fix, and the principle behind it.

## Safety and correctness

| Mistake | Why it mattered | Fix | Principle |
|---|---|---|---|
| An expired licence was rejected automatically, based on a date only the model had read. | A misread year would reject a valid merchant, with no person involved. | Reject only on a corroborated expiry. Otherwise route to review with `expiry_uncertain`. Add reopen. | Never take an irreversible decision on an uncorroborated model output. ([05](05-grounding-and-confidence.md)) |
| Out-of-scope documents were rejected on the model's label alone. | The same flaw, in another place. | Code must find no labelled licence number and no licence title. | Look for every place the same flaw can occur. |
| Audit writes sat inside the node that calls `interrupt()`. | LangGraph runs that node again on resume, so each event would be duplicated. | Writes go in dedicated nodes after the interrupt, each keyed. | Know your framework's re-execution semantics. ([08](08-durable-execution-and-idempotency.md)) |
| The submission key was `run_id`. | After a failed read-back, resubmission was impossible. | Submissions are unique per approved form version, and a verification failure raises the version. | Idempotency must block duplicates, not legitimate retries. |
| The audit key `run_id:action:form_version` was too broad. | Reject, reopen, reject silently lost the second reject. | Use a client-generated `action_id` for every user action. | Key by the intent of one action, not by its shape. |
| Captured corrections were written to the repository. | They contained personal data. | Keep them encrypted in the database. They leave only as synthetic twins. | Data protection covers the learning loop too. ([07](07-trust-boundaries-and-security.md)) |
| Lists like `people` were plain lists. | An unreadable owners table became "0 beneficial owners". | Use `Field[list]` with an `unclear` status. | Every value needs an honest "cannot read" state. ([02](02-structured-output-and-validation.md)) |
| The daily budget stopped new runs. | It blocked the path to a person. | Skip the model steps and route to review. Add retry and manual entry. | A guardrail must never block the path to a human. ([06](06-human-in-the-loop.md)) |
| A deadline was fixed at the run's creation. | Every retry would have failed at once. | Reset the deadline on each processing attempt. | Time limits belong to attempts, not to records. |

## Numbers that did not add up

| Mistake | Fix | Principle |
|---|---|---|
| The cost target ($0.15) ignored thinking tokens, which cannot be turned off and bill as output. | Re-estimate at about $0.23 per typical run, set the target below $0.40, and list cheaper setups as experiments. | Do the arithmetic before you set the target. ([10](10-observability-cost-latency.md)) |
| The latency budget needed about 220 tokens per second. The resolver had 25 s for up to 12 calls. | Mark the budgets provisional, run a throughput probe first, and split SC-006 into 60 s and 90 s. | Measure before you limit. ([04](04-agent-loop-and-budgets.md)) |
| A 99% precision target was set on about 20 `ready` cases. | Use a held-out split and a Wilson bound, plus a planned precision set of at least 400 `ready` runs with a real model (not built yet: T101). | Report intervals, and size the data to the claim. ([09](09-evaluation.md)) |
| The resolver limits were restated in four files, and they drifted apart. | Keep one normative table and link to it. | One source for each fact. ([11](11-spec-driven-development.md)) |

## Process and governance

| Mistake | Fix | Principle |
|---|---|---|
| Linear history on `develop`, together with `--no-ff` back-merges. | Drop the linear-history rule. | Check that the rules can all hold together. ([12](12-engineering-practices.md)) |
| One required approval, with a single maintainer. | Required checks are the gate, and CODEOWNERS only requests reviewers. | Design the process for the real team size. |
| The constitution was bumped MINOR for a redefinition. | Bump it to 2.0.0, MAJOR. | Follow your own versioning rules. |
| Tests asserted message meaning or wording. | Assert reason codes, error codes and structure. | Tests check outcomes, not wording. |
| UI strings broke their own ASD-STE100 rules: passive voice, two instructions in one sentence, banned terms. | Rewrite the strings, and add a lint check and human review. | A style rule needs a check and a reviewer. |

## The meta-lessons

1. **Most defects were between files, not inside one.** A document can be correct alone and contradict its neighbour.
2. **Fixes create new defects.** Round 2 found 17 issues caused by round 1's fixes, so re-verify after every fix round.
3. **An independent reviewer finds what the author cannot.** The reviewer had no stake in the earlier choices.
4. **Every finding becomes a test row or a rule.** Each lesson above is now a case in [test cases](../../specs/001-licence-to-kyb/test-cases.md) or a line in the constitution.

## Self-check

<details><summary>1. Name three places where "do not trust an uncorroborated model output" applies in this system.</summary>

1. Automatic rejection on expiry.
2. Automatic rejection as out of scope.
3. The `ready` route, which needs calibrated confidence from checkable signals, not the model's self-rating, and no fallback model.
</details>

<details><summary>2. Why did the fixes in round 1 cause new issues in round 2?</summary>

Each fix changed one file's assumption, and other files still held the old one. For example, the submission was keyed by `run_id` while a new rule said to "submit again". Cross-file re-verification caught them.
</details>
