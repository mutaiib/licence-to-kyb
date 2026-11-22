# 16 — What the checks caught

## In one minute

Every bug below passed the unit tests at the time. A different kind of check found each one: a browser pass, an eval run, mutation testing, a Docker smoke test, joining two branches, an independent code review, or running the app with a real model. The lesson is not "write more tests"; it is "check from more than one side".

## The bugs, by the check that found them

| Check | What it found | Why the tests missed it | Lesson |
|---|---|---|---|
| Browser (visual) | The evidence box framed only the label, not the value | PDF text comes in extraction order, not reading order | Test against the real document layout, not a convenient fixture |
| Browser (visual) | A near-expiry licence showed as expired in the demo | The demo used today's date; the documents were made for a fixed date | Pin "today" everywhere the data assumes it |
| Browser (visual) | A ready run offered Submit before anyone approved it | Tests used the status to mean "approved" | Send the fact itself (`form_approved`), never infer it |
| Browser (visual) | An uncertain expiry said "expired, you cannot submit" on the field | The gate changed the reason, but not the check result the field shows | Change a result in one place that every reader uses |
| Browser (visual) | The resolver never ran on uncertain expiries | Corroboration ran after the step that decides to re-read | Order of steps is behaviour; test the whole graph |
| Browser (visual) | A corrected value showed "Not on the licence" | The correction dropped the original evidence | A person's value replaces the value, not the evidence of where it was |
| Eval run | Demo mode answered for the wrong document | A short licence number matched inside a longer one | Match whole tokens, longest first |
| Resolver tests | A misread date passed the evidence check | The model's own quote repeated the misreading and matched the page fuzzily | Dates and identifiers must match the document exactly |
| Catalogue routing test | "Wrong number format" cases routed as "unknown authority" | The generated wrong number fit another authority's format | Generate faults that are unambiguous, and test that they are |
| Mutation testing | A rule result with a wrong field name survived | Tests checked outcomes and reasons, not which field a result names | Pin the contract other code reads (field names) |
| Mutation testing | The QR rule's `or` survived as `and` | No case had a QR code without a number | Mutants show the branch your inputs never reach |
| Docker smoke test | The image crashed at startup (twice) | A test-only library was imported at the top level; `httpx` was dev-only | Build and start the real image in CI |
| Joining two branches | A crashed run could not be retried | The database said "in review" but the workflow did not | When state lives in two places, change both in one function |
| Readability review | A date-order rule could never fire | A schema validator rejected the same input first | Two layers checking the same thing hide each other |
| Independent code review | A reject, then a reopen, kept the old approval: Submit worked with no new approval | Each test checked one action, never a sequence | Test sequences of actions, not only single actions |
| Independent code review | A retry dropped the reasons found while routing, so the run could reach `ready` | The retry test used a case with no routing doubt | When a step is skipped on retry, its results must survive |
| Independent code review | Retention, the deadline sweep and the daily budget reset never ran | Each function was tested; nothing tested that the app calls it | Test the wiring: what calls the function, and when |
| Independent code review | Vision re-reads were not charged to the resolver's token limit | The limit was tested with the agent's own turns only | Every paid call inside a loop counts against the loop's budget |
| Independent code review | A `max_tokens` retry reported only the second call's usage | The test checked the answer, not the usage | Check the cost of a retry, not only its result |
| Independent code review | A registry record without an expiry date "confirmed" an expired date | Every mock record had a date | Test the absent case of every external answer |
| Running the app | A proxy answered with a web page; the UI took it as data and crashed | Tests always served JSON | A success status is not proof of data; check the body |
| First local-model run | A clean case stopped in processing but scored 100% on reasons | The reason grader allows extra codes | Report failures as their own metric, never inside another |
| Security review | A 2 KB PDF inflated to 2 GB in memory and crash-looped the API | Intake checked pages and size, not the decoded content | Put work on untrusted bytes in a process that is allowed to die |
| Security review | 20 parallel wrong passwords all reached the password check | The limit was tested one request at a time | Count the attempt before the slow work, under a lock |
| Security review | Licence numbers and reviewers' reasons sat in plain text in SQLite | Encryption was tested on the obvious columns only | Search the raw database file for a known value |
| Eval review | People and activities lost their thresholds after calibration, so they were never flagged | The fit kept only fields that had rows | A fit must start from the configured fields, never from the data |
| Eval review | Some groups were never in the test report; an injected copy could sit in the other split from its twin | Splits were per-case coin flips | Split evenly within each group; keep copies with their source |
| Eval review | An unlabelled document routed `ready` counted as precise | `all([])` is true | Check what a metric does with no data |
| Browser check | Demo traces showed `claude-opus-5-5` and token counts when no model ran | Tests checked cost, not the model name | A demo must say it is a demo in every output |

## Rules

- **Check from several sides.** Unit tests, a graph test over real documents, an eval over the catalogue, a browser pass, mutation testing and a real container each catch a different class of bug.
- **When a check finds a bug, add the test that would have caught it,** at the lowest level that can, before the fix.
- **Prefer facts over inferences** in what the backend sends the UI.

## Self-check

<details><summary>1. Your unit tests pass and coverage is 95%. What can still be wrong?</summary>

Behaviour that only appears when parts meet: step order in the graph, the real document layout, a container's dependencies, state split across two stores, and the UI inferring something the backend never said. Coverage counts lines run, not cases checked; mutation testing shows the difference.
</details>

<details><summary>2. A demo answers from labels and always reads perfectly. What can its eval still find?</summary>

Routing, rule and safety bugs, and bugs in the demo itself (here: matching the wrong case). It cannot measure reading quality; that needs a real model.
</details>
