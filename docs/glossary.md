# Glossary

The terms used in these docs, each with where it lives in the code. Paths are relative to
`backend/src/licence_kyb/` unless they start with a top-level folder. The rules, reason codes,
API routes and settings are listed in [reference.md](reference.md).

## The domain

| Term | Meaning | Where |
|---|---|---|
| **Trade licence** | The document a UAE authority issues to let a business operate. It names the business, its legal form, activities, owners, and the issue and expiry dates. | `schemas/licence.py` |
| **Issuing authority** | The body that issued the licence: DET (Dubai mainland), ADDED (Abu Dhabi mainland), DMCC and IFZA (free zones). Each has its own number format and layout. | `profiles/*.yaml` |
| **KYB** | Know Your Business: the checks a payment provider makes before it onboards a merchant. | `schemas/kyb_form.py` |
| **KYB onboarding form** | The form this system fills from the licence. A person approves it and submits it. | `nodes/map_form.py` |
| **UBO** | Ultimate beneficial owner: a person who owns 25% or more. Each UBO needs an identity document. | `nodes/map_form.py`, `rules/ownership.py` |
| **Documents to request** | What to ask the applicant for after the review: memorandum of association, identity documents, a tenancy contract (Ejari in Dubai, Tawtheeq in Abu Dhabi) or a free zone lease. | `nodes/map_form.py` |
| **Registry** | The authority's public verification service. Here it is a mock with the same answers: found, not found, expiry date. | `tools/registry_mock.py`, `registry.py` |

## Reading and checking

| Term | Meaning | Where |
|---|---|---|
| **Field** | One value on the licence, with its status (`present`, `not_present`, `unclear`) and the exact text it came from. The schema never forces the model to invent a value. | `schemas/licence.py` |
| **Evidence quote** | The text on the licence that a value came from. | `schemas/licence.py` |
| **Grounding** | The check that the evidence quote is really on the page (OCR text) and that the value is in the quote. Dates and identifiers must match exactly. | `rules/grounding.py` |
| **Rule** (check) | Plain code that tests one thing, such as "the licence is not expired". It returns a result with a severity: `block` or `warn`. | `rules/` |
| **Reason code** | A short code that says why a field or a run needs attention, such as `near_expiry`. The UI turns it into a sentence. | `schemas/results.py`; `frontend/src/copy.ts` |
| **Corroboration** | A second, independent source that agrees with a value: the QR code on the licence or the registry. An "expired" date rejects a licence only when it is corroborated. | `rules/qr.py`, `rules/registry.py`, `nodes/gate.py` |
| **Two readings** (passes) | Two independent model readings of the same licence. Where they agree on a critical field, that is evidence. | `nodes/extract.py` |
| **Confidence** | A score per field from six signals: agreement, grounding, rules, OCR quality, corroboration and the model's own rating (small weight). | `nodes/confidence.py`, ADR-003 |
| **Threshold** | The confidence a field needs to pass without review. Fitted per model profile on labelled cases. | `backend/config/thresholds.yaml`, `scripts/calibrate.py` |
| **Gate** | Code that picks the route of a run from the checks and the confidence. | `nodes/gate.py` |
| **Route** | `ready` (nothing to examine), `needs_review` (a person examines flagged fields) or `reject` (out of scope, or a corroborated expiry). | `nodes/gate.py` |

## The agent

| Term | Meaning | Where |
|---|---|---|
| **Workflow** | Steps whose order code decides. Everything here except the resolver. | `pipeline.py`; ADR-001 |
| **Agent** | A model that chooses its own next action (tool calls) in a loop. | `nodes/resolve.py` |
| **Resolver** | The one agent: it re-reads values that failed a re-readable check, with read-only tools. | `nodes/resolve.py` |
| **Tool** | A function the agent can ask code to run, such as `licence_reread_region`. Defined with a strict schema. | `tools/definitions.py` |
| **Tool runner** | Code that checks each tool call (known tool, valid arguments, field in scope, page exists, not a duplicate, budget left) before it runs. | `tools/runner.py` |
| **Tool error** | A tool result with `is_error: true` that says what failed, why, and what to do next. Never a stack trace. | `tools/errors.py` |
| **Proposal** (`propose_fix`) | A new value the agent suggests. Code accepts it only if every rule then passes. | `nodes/resolve.py` |
| **Budget** | Limits on turns, tokens, tool calls and seconds. The soft limit tells the agent to finish; the hard limit stops the loop. | `backend/config/budgets.yaml` |
| **Round** | One run of the resolver loop. At most 2 per run. | `pipeline.py` |
| **Daily budget** | A token limit per day. When it is used up, new runs skip the model steps and go to review. | `llm/client.py` (`DailyBudget`) |

## Human review and durability

| Term | Meaning | Where |
|---|---|---|
| **Flagged field** | A field that needs a person's decision: approve, correct, or override a check that could not run. | `nodes/review.py` |
| **Form version** | A number that changes with every change to the form. An approval applies to one version only. | `nodes/review.py` |
| **Read-back** | After a submit, the stored record is read again and compared with the approved form. The run is `done` only if they are equal. | `pipeline.py` (`_apply_submit`) |
| **Interrupt** | LangGraph's pause: the run stops and waits for the reviewer, and survives a restart. | `pipeline.py` (`wait_for_reviewer`) |
| **Checkpoint** | The saved state of a run after each step (SQLite). | `graph.py` |
| **Keyed write** (idempotency) | Every write carries an ID from the client; a repeated request writes nothing new. | `store/db.py` |
| **Audit event** | A record of every decision, approval and submit, with the person who made it. | `store/db.py` |

## Models, evals and engineering

| Term | Meaning | Where |
|---|---|---|
| **Model profile** | Configuration that names the provider and the model of each step. `MODEL_PROFILE` picks it. | `backend/config/models.yaml`; ADR-004 |
| **Transport** | The code that turns one model request into one provider's API: Anthropic, or OpenAI-compatible. | `llm/client.py`, `llm/openai_compatible.py` |
| **Scripted model / demo mode** | A stand-in model that answers from the case labels. Tests the pipeline, not reading quality. Free. | `testdata/answers.py` |
| **Eval case** | A licence with its labels: expected values, route and reason codes. | `evals/cases/` |
| **Split** | Cases used to fit thresholds (`calibration`) are kept apart from cases used to report results (`test`). | `evals/cases/` |
| **Wilson interval** | A confidence interval for a rate measured on few cases: 15 of 15 is [0.80, 1.00], not "100%". | `evals/graders.py` |
| **pass^3** | A routing case counts only if it is correct in all 3 of 3 runs: a check on consistency (`--pass3`). | `evals/run.py` |
| **Twin** | A synthetic licence made from an approved correction, with the same fault but no personal data. | `scripts/make_twin.py` |
| **Trace / span** | A record of one step, model call or tool call, with time, tokens and cost. | `tracing.py` |
| **Mutation testing** | Small changes to the code; a good test suite fails on each one. | `make mutation` |
| **ASD-STE100** | Simplified Technical English: the writing standard for all interface text. | `docs/ui-copy.md`, `scripts/lint_copy.py` |
| **SBOM** | Software bill of materials: the list of every library in a release. | `.github/workflows/release.yml` |
| **Spec Kit / SDD** | Spec-driven development: spec, plan, tasks, then tests, then code. | `specs/001-licence-to-kyb/`; handbook 11 |
