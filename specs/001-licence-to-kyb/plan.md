# Implementation Plan: Trade Licence to KYB Onboarding Form

**Branch**: `feature/001-licence-to-kyb` for the specification; `feature/001-licence-to-kyb-<slug>` per unit of work, where `<slug>` is `foundation`, `us<N>` or `polish` (GitFlow) | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-licence-to-kyb/spec.md`

## Summary

A reviewer uploads a UAE trade licence and receives a draft KYB onboarding form. Every value on the form is checked and linked to the text it was copied from. The reviewer examines only the flagged fields, approves or corrects them, and submits. The system stores the submission, reads it back, and confirms that it matches what the reviewer approved.

The technical approach is a fixed LangGraph workflow. Three of its steps use a model:

1. **Route:** classify the document and its issuing authority. No tools.
2. **Extract:** fill a strict schema, with an evidence quote for every value. No tools. The critical fields are read in two independent passes.
3. **Resolve:** one bounded agent that re-reads values that failed a check, using read-only tools. Its `licence_reread_region` tool makes a vision model call, which counts against the resolver budget.

All other steps are plain Python:
- file checks, rendering, OCR and QR decoding
- business rules
- grounding checks
- evidence-based confidence and routing
- form mapping (a draft before review, rebuilt after each decision)
- the review and submit pauses, which use `interrupt()` with a SQLite checkpointer
- submission read-back

A React 19 and Astryx web app provides the upload, review, run list and trace pages.

The full design, with one licence traced end to end, is in [`docs/architecture.md`](../../docs/architecture.md).

## Technical Context

**Language/Version**: Python 3.12 (backend). TypeScript 5 with React 19 (frontend).

**Primary Dependencies**:
- **Backend:** `langgraph` and `langgraph-checkpoint-sqlite`; `anthropic` (official SDK); `pydantic` v2; `fastapi` and `uvicorn`; `pypdfium2` and `pdfplumber`; `pytesseract` (Tesseract `eng+ara`); `opencv-python-headless` (QR decoding, deskew); `rapidfuzz`; `cryptography` (Fernet); `pyyaml`
- **Test data:** `reportlab`, `arabic-reshaper`, `python-bidi`, `qrcode`, `faker`, `pillow` (see research R9a: no system packages are needed)
- **Frontend:** `@astryxdesign/core`, `@astryxdesign/theme-neutral`, `@stylexjs/stylex`, `vite`, `openapi-typescript`

**Storage**: SQLite holds the application database (runs, submissions, audit events, traces) and, in a separate file, the LangGraph checkpoints. Encrypted files live on the local filesystem.

**Testing**:
- **Backend:** `pytest`, `hypothesis` (property tests), `pytest-asyncio`.
- **Frontend:** Vitest with Testing Library, plus browser checks with chrome-devtools-axi.
- **Evals:** a custom harness with graders that read state.

**Target Platform**: Linux server or a local machine through Docker Compose. Reviewers use a desktop browser.

**Project Type**: Web application (backend + frontend).

**Performance Goals**: p95 processing of 60 s or less per document, excluding human time. A clean licence goes from upload to verified submission in under 2 minutes of reviewer time. The latency budget per stage is below.

**Constraints**:
- Average cost per document is measured, with a target below $0.40 (see the cost estimate below).
- Resolver limits are defined once, in [contracts/resolver-tools.md](contracts/resolver-tools.md#budgets-the-only-definition).
- A deadline of 120 s per processing attempt, and a daily token cap (FR-039, FR-040).
- Offline unit and graph tests, with recorded model responses from synthetic documents only.
- Personal data masked in logs and traces.

**Scale/Scope**:
- Demonstration scale: tens to hundreds of documents, and reviewer accounts from configuration.
- Four authority profiles (DET, ADDED, DMCC, IFZA) plus a generic profile.
- Five UI pages: sign-in, upload, review, run list, trace.
- An eval set of about 100 labelled cases, split 50/50 into calibration and test.

### Latency budget

| Stage | p95 budget |
|---|---|
| Intake and preprocess (render, OCR, QR) | 8 s |
| Route | 4 s |
| Extract, two passes in parallel | 18 s |
| Validate, confidence, gate, draft form | 1 s |
| Resolver, when it runs (hard limit 45 s) | 45 s |
| **Total, without resolver / with resolver** | **31 s / 76 s** (targets: 60 s / 90 s, SC-006) |

- **These budgets are provisional.** An extract pass with about 4,000 output and thinking tokens fits 18 s only above about 220 tokens per second.
- The Foundation task T034 is a manual SDK probe, outside CI. It measures output throughput and latency with prompts of the planned sizes and synthetic page images, at the planned efforts. Each budget is then set from the probe. The eval report later replaces the probe figures with measured per-stage numbers.
- If the extract pass cannot fit its budget, the first levers are lower effort on the secondary pass and a shorter output schema for it.
- The eval report shows the measured p95 for each stage next to its budget.

### Cost estimate

Prices: `claude-opus-5-5` costs $4 per million input tokens and $20 per million output tokens, and thinking tokens bill as output.

| Call | Input tokens | Output + thinking tokens | Cost |
|---|---|---|---|
| Route (effort low, mostly cached prefix) | 3,000 | 800 | ≈ $0.028 |
| Extract primary (effort medium) | 10,000 | 4,000 | ≈ $0.120 |
| Extract secondary (critical fields) | 10,000 | 2,000 | ≈ $0.080 |
| **Typical run, no resolver** | | | **≈ $0.23** |
| Resolver, typical (2 to 3 turns) | | | ≈ $0.10 to $0.20 more |
| Resolver at its hard limit (40k tokens, all billed as output in the worst case) | | | up to $0.80 more (upper bound) |

Prompt caching lowers the input cost of the stable prefix. The target is an average below $0.40. Three experiments measure cheaper configurations against SC-001 and SC-002:
- `claude-haiku-5-5` as the router
- `claude-sonnet-5-5` for the secondary pass
- one pass instead of two

The README reports the measured numbers.

## Constitution Check

*GATE: Must pass before research. Re-check after design.*

| Principle | How the plan complies | Status |
|---|---|---|
| I. Workflow first, one bounded agent | Twelve fixed steps in a LangGraph graph. One agent node, with hard limits enforced in code. [ADR-001](../../docs/decisions/ADR-001-workflow-with-one-agent.md) | PASS |
| II. Typed contracts at every boundary | Pydantic models for every step output, structured outputs for route and extract, `strict` resolver tools, Pydantic API bodies, and TypeScript types generated from OpenAPI. Escape values and `not_present` on every field ([data-model.md](data-model.md)). | PASS |
| III. Untrusted input cannot act | Route and extract have no tools. The resolver tools are read-only, and the QR payload is treated as untrusted data. Writes exist only in harness code, in dedicated nodes after the interrupt. **Every write** (decision, approval, audit event, captured correction, submission) has an idempotency key ([data-model.md](data-model.md#writes-and-resumption)). Injected-text cases are in the eval set. | PASS |
| IV. Code enforces rules and verifies outcomes | All rules are in `rules/` as plain code. The submission is read back and compared. Budget exhaustion, a processing failure, a passed deadline and a fallback model all route to review, never to a dead end (FR-039 to FR-041). | PASS |
| V. A person approves every submission | Submit needs a signed-in reviewer with their own account, and an approval bound to the form version. Every action is audited exactly once. Every correction is captured, and joins the eval set as a synthetic twin after maintainer approval. Automatic rejection needs a corroborated expiry, and a rejected run can be reopened (FR-037, FR-038). | PASS |
| VI. Outcome-based tests before code | `tasks.md` puts backend **and frontend** test tasks before implementation in every story. Tests are parametrised over [test-cases.md](test-cases.md) and assert outcomes and reason codes, never message text. They use a fixed clock of 2026-06-01 and run without network. The public licence is used only in the live eval. | PASS |
| VII. Evidence-based confidence, measured by evals | Signals-based scoring, `calibrate.py` thresholds, and an eval harness with state graders. The README reports measured results. | PASS |
| VIII. Personal data protection | Fernet (MultiFernet rotation) at rest, including captured corrections. A masking log filter and trace serializer. A scheduled retention job. Captured corrections stay in the database and leave it only as synthetic twins. `evals/cases/captured/` does not exist. | PASS |
| IX. Plain interface language | `frontend/src/copy.ts` follows [`docs/ui-copy.md`](../../docs/ui-copy.md), and `scripts/lint_copy.py` runs in CI. | PASS |
| Branching and releases (GitFlow) | The specification is on `feature/001-licence-to-kyb`. Setup and Foundation are on `feature/001-licence-to-kyb-foundation`, each user story on `feature/001-licence-to-kyb-us<N>`, and Polish on `feature/001-licence-to-kyb-polish`. Each branch comes from `develop`, with one pull request per branch. The release goes `release/x.y.z` → `main` (pull request), then a back-merge → `develop` (pull request), with a signed tag, a changelog entry and the eval report. | PASS |
| Engineering standards | Setup and polish tasks create the CI gate, pre-commit hooks, Dependabot, pinned Actions, SECURITY/CODEOWNERS/CONTRIBUTING files, the SBOM and attestations ([docs/engineering-practices.md](../../docs/engineering-practices.md)). | PASS |
| X. Simplicity | One model family. No vector store and no framework wrapper around the SDK ([ADR-002](../../docs/decisions/ADR-002-anthropic-sdk-inside-langgraph-nodes.md)). Work is ordered by user-story priority. No scope is labelled with versions or "MVP". The second extraction pass and the resolver each have an experiment that can remove them. | PASS |

**Post-design re-check:** PASS, after the cross-artifact analysis on 2026-11-21. That analysis found violations of III, VIII and X, and all three are fixed in the data model, spec, test cases and tasks. The Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-licence-to-kyb/
├── spec.md              # what and why (speckit-specify, speckit-clarify)
├── plan.md              # this file (speckit-plan)
├── research.md          # research: technical decisions
├── data-model.md        # design: entities, fields, validation, state transitions
├── test-cases.md        # value-driven case tables used by the tests
├── quickstart.md        # design: run-and-verify guide
├── contracts/
│   ├── http-api.md      # REST endpoints and bodies
│   ├── model-calls.md   # route and extract request/response contracts
│   └── resolver-tools.md # tool definitions, results and errors
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # speckit-tasks output
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── src/licence_kyb/
│   ├── config.py              # settings, models.yaml, thresholds.yaml loading
│   ├── graph.py               # StateGraph wiring, checkpointer, interrupts
│   ├── state.py               # RunState
│   ├── schemas/               # licence.py, results.py, kyb_form.py, api.py
│   ├── profiles/              # det.yaml, added.yaml, dmcc.yaml, ifza.yaml, generic.yaml
│   ├── nodes/                 # intake, preprocess, route, extract, map_form, review
│   │                          # (apply one reviewer action), later: resolve, confidence, gate
│   ├── pipeline.py            # the graph: process → wait_for_reviewer → apply_action → … → done
│   ├── rules/                 # expiry, number_format, dates, ownership, legal_form,
│   │                          # arabic_name, activity, grounding, qr, registry, applicant
│   ├── tools/                 # reread_region, ocr_region, registry_mock,
│   │                          # activity_lookup, validation_report, errors (shared error responses)
│   ├── llm/                   # client.py (LLMClient), recorder.py, prompts/
│   ├── store/                 # db.py, runs.py, submissions.py, audit.py, files.py
│   ├── security.py            # Fernet, masking filter, retention
│   ├── tracing.py             # spans
│   ├── ops.py                 # startup resume, deadline sweep, retention schedule, daily budget, metrics
│   └── api/                   # app.py, routes_runs.py, routes_session.py, routes_health.py, csrf.py
├── config/                    # models.yaml, thresholds.yaml, budgets.yaml
└── tests/
    ├── unit/                  # schemas, rules (case tables + Hypothesis), mapping, confidence, gate
    ├── graph/                 # end-to-end graph runs with recorded model responses
    ├── api/                   # HTTP behaviour
    └── fixtures/              # llm/ recordings, documents/

frontend/
├── package.json
├── src/
│   ├── copy.ts
│   ├── api/                   # generated.ts (from OpenAPI), client.ts
│   ├── pages/                 # SignIn, Upload, Review, Runs, Trace
│   └── components/            # DocumentViewer, FieldRow, StatusBadge, SpanTree
└── tests/                     # Vitest + Testing Library, per page and component

data/                          # high_risk_activities.yaml, activities_sample.yaml, registry_mock.json
scripts/                       # gen_licences.py, make_twin.py, fetch_public_samples.py, calibrate.py, lint_copy.py, measure_throughput.py
evals/                         # runner.py (foundation), run.py, graders.py, compare.py, cases/{synthetic,public,twins,precision}/, reports/
docs/                          # architecture, problem statement, worksheet, decisions, UI copy, research
docker-compose.yml  Makefile  .pre-commit-config.yaml  commitlint.config.mjs
.github/
├── workflows/             # ci.yml, evals.yml (manual + release branches), release.yml (SBOM, attestations)
├── dependabot.yml
├── CODEOWNERS
├── pull_request_template.md
└── ISSUE_TEMPLATE/
CHANGELOG.md  CONTRIBUTING.md  SECURITY.md  LICENSE
```

**Structure Decision**: web application, with `backend/` and `frontend/` separated by a generated, typed HTTP contract. The test data generator, calibration and evals live at the repository root, because they exercise the whole system and not one package.

## Complexity Tracking

No violations. The table is intentionally empty.
