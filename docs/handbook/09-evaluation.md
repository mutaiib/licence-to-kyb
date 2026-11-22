# 09 — Evaluation

## In one minute

An eval is a set of repeatable tasks plus graders. It tells you whether a change made the system better or worse.

**Start with 20 to 50 tasks drawn from real failures.** Grade the final state, not the transcript. Report numbers you could defend in a review.

## Rules

- **Balance the set.** Include cases where the system should act and cases where it should refuse or escalate. A set of only "should act" cases rewards a system that always acts.
- **Give every case a reference answer.** This proves the case is solvable and the grader works.
- **Use the cheapest grader that can answer the question:**
  1. code that checks the final state (route, reason codes, values, submissions)
  2. a model grader with a narrow rubric and an "unknown" answer
  3. sampled human review
- **Grade the outcome, not the path.** Do not require one sequence of tool calls.
- **Use clean trials:** a fresh database and a fixed clock for every case.
- **Hold data out.** Fit thresholds on a calibration split, and report on a test split.
- **Report intervals.** Use a Wilson interval for precision, because small counts mislead.
- **Weight by a realistic mix.** Here: 70% clean, 20% scans, 10% problems. Report the review rate on that mix, not on an adversarial set.
- **Use pass^k when every run must succeed.** A case passes only if all k trials pass. Here, pass^3 on a 30-case routing subset.
- **Run regression comparisons.** Every change lists exactly the cases whose result changed.
- **Turn corrections into cases.** Every human correction becomes a case. Here it becomes a **synthetic twin**: same fault, no real personal data.
- **Avoid template bias.** Use at least two layouts per authority, so the eval does not only measure fit to one template.

## In this repository

- **The catalogue:** about 100 cases, the split, the mix and the precision set ([test cases](../../specs/001-licence-to-kyb/test-cases.md)).
- **The metrics,** defined as requirements: FR-034 and SC-001 to SC-010 ([spec](../../specs/001-licence-to-kyb/spec.md)).
- **The eval tooling:**
  - runner: task T033
  - graders, report and compare: tasks T089 to T096
  - twins: task T095
  - ([tasks](../../specs/001-licence-to-kyb/tasks.md))
- **Experiments:** each one measures one change ([experiments](../experiments.md)).

## Mistakes to avoid

- **Grading by string match on the transcript.**
- **Calibrating and reporting on the same data.**
- **A "realistic" review-rate target measured on an adversarial set.** Found in review: the target was untestable until the mix was defined.
- **Evals as an afterthought.** Here, the case generator and a minimal runner are built in Foundation, before any model work.

## Self-check

<details><summary>1. Why does every injected-text case have a clean twin?</summary>

The pass condition is "same outcome as the twin": the same route, values and writes. That tests the effect of the injection directly, without having to guess what a correct answer looks like.
</details>

<details><summary>2. What are the three grader types, and when does each fit?</summary>

1. **Code:** state checks, whenever the outcome is in stored state. It is cheap and reliable.
2. **Model grader:** judging meaning that code cannot check. It needs a narrow rubric, an "unknown" answer, and calibration against people.
3. **Human:** the most trusted, but slow, so it is used for sampled checks.
</details>

<details><summary>3. A prompt change raises field accuracy by 2 points. What else must the comparison show before you merge it?</summary>

The list of cases that changed, including any that got worse. Also check `ready` precision with its interval, the review rate on the mix, and cost and latency against the previous report.
</details>
