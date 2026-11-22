# Status

What is complete, what is pending, and why. Last updated with release
[0.1.0](https://github.com/mutaiib/licence-to-kyb/releases/tag/v0.1.0).

**Legend:** ✅ complete · 🟡 partly measured · ⏳ pending (the reason is given)

## Features

| User story | Status | Where to see it |
|---|---|---|
| US1 Upload a licence and see the pre-filled form | ✅ | Upload page, review page |
| US2 Review flagged fields, approve, submit, read back | ✅ | Review page; [handbook 06](handbook/06-human-in-the-loop.md) |
| US3 Confidence from evidence, and a gate | ✅ | [`nodes/confidence.py`](../backend/src/licence_kyb/nodes/confidence.py), [`nodes/gate.py`](../backend/src/licence_kyb/nodes/gate.py) |
| US4 One bounded agent re-reads failed values | ✅ | [`nodes/resolve.py`](../backend/src/licence_kyb/nodes/resolve.py); [architecture §7](architecture.md#the-agent-loop-with-its-limits) |
| US5 Trace of every step, model call and tool call | ✅ | Trace page; [`tracing.py`](../backend/src/licence_kyb/tracing.py) |
| US6 Evals on labelled cases | ✅ | `make eval`; [`evals/`](../evals/) |
| Any model by configuration (Claude or a local model) | ✅ | [ADR-004](decisions/ADR-004-provider-neutral-model-calls.md), [handbook 14](handbook/14-model-providers.md) |
| Release with SBOMs and build provenance | ✅ | [`.github/workflows/release.yml`](../.github/workflows/release.yml) |

## Success criteria (spec)

| Criterion | Target | Status | Evidence or reason |
|---|---|---|---|
| SC-001 Field accuracy | ≥ 95% clean, ≥ 85% scans | 🟡 | Two licences on a local 7B model: 9 of 12 and 6 of 10 ([experiments](experiments.md)). The full suite needs the Claude API or a GPU (T101). |
| SC-002 `ready` precision, critical fields | ≥ 99% | 🟡 | Offline: 15 of 15 correct, Wilson 95% [0.80, 1.00]. With a real model: no run reached `ready` yet. |
| SC-003 Review rate, realistic mix | ≤ 40% | 🟡 | Offline: 28.2%. With a real model: pending T101. |
| SC-004 No seeded bad document submitted or `ready` | 0 | ✅ | 0 in the offline eval and in both local-model runs. |
| SC-005 Reviewer time | < 2 min clean, < 5 min flagged | ⏳ | Needs a person doing 10 timed walkthroughs (T099). The audit timestamps are recorded for it. |
| SC-006 Processing time, p95 | ≤ 60 s (≤ 90 s with re-reading) | ⏳ | Needs the Claude API (T034, T101). On a local CPU model a licence takes 25 to 50 minutes. |
| SC-007 Cost per document | < $0.40 | ⏳ | Needs the Claude API (T034, T101). A local model costs 0. |
| SC-008 Approver found from the audit record | 100% | ✅ | Tested: every submission names its approving account. |
| SC-009 Interface copy passes ASD-STE100 | 100% | ✅ | `scripts/lint_copy.py`, a required CI check. |
| SC-010 No automatic rejection on an unproven value | 0 | ✅ | 0 in the offline eval; an uncorroborated "expired" becomes `expiry_uncertain`. |

## Open tasks

| Task | What it needs | Why it is not done |
|---|---|---|
| T034 Throughput probe | An `ANTHROPIC_API_KEY`, and approval to spend | Paid calls. The script is ready: `scripts/measure_throughput.py`. |
| T099 Reviewer timing | A person, 10 timed walkthroughs | Cannot be automated honestly. |
| T101 Full eval with a real model | An API key (`make eval-live`) or a GPU for the local profile | 45 cases at 25 to 50 minutes each on this machine's CPU. |

**Experiments waiting for T101** ([experiments](experiments.md)): resolver on vs. off, a smaller router model, one vs. two extraction passes, OCR text in the prompt, a cheaper secondary model, and confidence thresholds fitted per model profile (`config/thresholds.yaml` holds documented defaults marked `fitted: false`).

## Known limits

- **Synthetic data, plus one public licence.** Real licences contain personal data; only a licence that its company publishes (ADCB) is used, downloaded at eval time and never committed.
- **The registry is a mock.** It stands in for the authorities' verification services.
- **One reviewer account type.** No roles or four-eyes approval.
- **SQLite and one process.** Enough for the reference implementation; a shared deployment needs a server database and a job queue.
- **The `submitted` run status is listed in the API but never set:** a submit goes straight to `done`, or back to review when the read-back differs.
- **A local CPU model is too slow for daily use.** It shows that the system works with any model, and how a weaker model fails safely.
