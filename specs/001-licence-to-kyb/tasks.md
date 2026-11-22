---
description: "Task list for Trade Licence to KYB Onboarding Form"
---

# Tasks: Trade Licence to KYB Onboarding Form

**Input**: Design documents from `/specs/001-licence-to-kyb/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [test-cases.md](test-cases.md), [quickstart.md](quickstart.md)

**Tests**: Required. Constitution Principle VI: tests come before code.
- In every story, backend and frontend test tasks come first, and they must fail before implementation starts.
- Tests are parametrised over [test-cases.md](test-cases.md) and assert outcomes and reason codes only.
- They use a fixed clock of 2026-06-01 and run without network.

**Organization**: tasks are grouped by user story, so each story can be implemented, verified and merged on its own.

**Visual check (constitution, Development Workflow)**: before its pull request, each story runs its quickstart rows in a browser against `make dev` (demo mode), fixes every defect with a regression test, and attaches screenshots to the pull request.

**Branching (GitFlow)**:
- The specification is on `feature/001-licence-to-kyb`, which merges first.
- Setup and Foundation are on `feature/001-licence-to-kyb-foundation`.
- Each user story is on `feature/001-licence-to-kyb-us<N>`, and Polish on `feature/001-licence-to-kyb-polish`.
- Every branch is created from an updated `develop`.
- Each branch merges by pull request when the CI gate passes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task serves (US1 to US6)

---

## Setup (Shared Infrastructure)

**Purpose**: repository standards, tooling and project skeletons.

- [X] T001 Create `main` with the first commit, then `develop` from `main`. Merge the specification branch `feature/001-licence-to-kyb` by pull request, then create `feature/001-licence-to-kyb-foundation` from `develop`. Configure GitHub rulesets for `main` and `develop` per `docs/engineering-practices.md` section 1, with CODEOWNERS used to request reviewers only.
- [X] T002 Create the backend project with `uv`, Python 3.12, the dependencies from plan.md (including `argon2-cffi`), and a committed lock file, in `backend/pyproject.toml` and `backend/uv.lock`
- [X] T003 [P] Create the frontend with Vite, React 19 and TypeScript `strict` in `frontend/package.json`. Install `@astryxdesign/core`, `@astryxdesign/theme-neutral`, `@stylexjs/stylex`, Vitest and Testing Library, then run `npx @astryxdesign/cli init`.
- [X] T004 [P] Configure ruff (strict rule set) and `mypy --strict` in `backend/pyproject.toml`
- [X] T005 [P] Configure ESLint, Prettier and `noUncheckedIndexedAccess` in `frontend/eslint.config.js` and `frontend/tsconfig.json`
- [X] T006 [P] Add pre-commit hooks for ruff, mypy, gitleaks, end-of-file and commitlint in `.pre-commit-config.yaml` and `commitlint.config.mjs`
- [X] T007 [P] Add the CI workflow in `.github/workflows/ci.yml`. It runs every check in the CI gate list of `docs/engineering-practices.md` section 4:
  - lint and format
  - type checks
  - backend offline tests
  - coverage ≥ 90% on the deterministic core
  - Vitest and the frontend build
  - OpenAPI type freshness
  - the copy check
  - gitleaks
  - `pip-audit` and `npm audit --audit-level=high`
  - the PR title check

  Actions are pinned to SHAs, with `permissions: contents: read`.
- [X] T008 [P] Add `.github/dependabot.yml` (pip, npm, actions, docker), `.github/CODEOWNERS`, `.github/pull_request_template.md` (spec link, test evidence, eval numbers, worksheet rows changed), and `.github/ISSUE_TEMPLATE/`
- [X] T009 [P] Add `CONTRIBUTING.md` (GitFlow, story branches, Conventional Commits, how to run checks), `SECURITY.md`, `LICENSE` (MIT), and `CHANGELOG.md` with an `Unreleased` section
- [X] T010 [P] Add a `Makefile` with the targets `setup`, `lint`, `test`, `data`, `eval`, `eval-compare`, `eval-precision`, `approve-capture`, `measure`, `demo`, `types` and `backup`, and add `.env.example`
- [X] T011 [P] Add `docker-compose.yml`, `backend/Dockerfile` and `frontend/Dockerfile`: multi-stage, base images pinned by digest, a non-root user and health checks on `/healthz`

**Checkpoint**: an empty project passes CI.

---

## Foundation (Blocking Prerequisites)

**Purpose**: contracts, storage, configuration, the model client, operations, test data and a case runner. Every story needs these.

**⚠️ CRITICAL**: no user story work begins until this section is complete.

### Tests for the foundation (write first; they must fail)

- [X] T012 [P] Write schema tests from the "Schemas and authority profiles" table in `backend/tests/unit/test_schemas.py`
- [X] T013 [P] Write profile tests in `backend/tests/unit/test_profiles.py`: each profile's pattern accepts its own valid examples and rejects other authorities' examples
- [X] T014 [P] Write security tests in `backend/tests/unit/test_security.py`:
  - a round trip through MultiFernet, plus decrypting with a rotated key
  - the stored bytes differ from the input
  - the masking filter removes PII-tagged values from log records and from trace output
- [X] T015 [P] Write `LLMClient` tests in `backend/tests/unit/test_llm_client.py`:
  - a recorded response and its serving model are returned for a known request hash
  - a missing recording fails, naming the hash
  - no network is used
  - an exhausted daily budget blocks the call and returns `budget_exhausted`
- [X] T016 [P] Write operations tests in `backend/tests/unit/test_ops.py`:
  - on startup, runs in `received` or `processing` resume
  - a run past `deadline_at` moves to `awaiting_review` with `processing_failed`
  - retention deletes expired runs, files and captured corrections, and keeps current ones
- [X] T017 [P] Write idempotent-write tests in `backend/tests/unit/test_store_idempotency.py`: writing any keyed entity twice with the same key leaves one row

### Implementation for the foundation

- [X] T018 [P] Implement `Field[T]` (with `origin`), `RouteResult`, `TradeLicenceExtraction`, `CriticalFields`, `Activity` and `Person` in `backend/src/licence_kyb/schemas/licence.py`
- [X] T019 [P] Implement `RuleResult` (with `outcome`), `ReasonCode`, `Reason`, `ProposedFix`, `FieldConfidence` and the routing `Decision` in `backend/src/licence_kyb/schemas/results.py`
- [X] T020 [P] Implement `KYBOnboardingForm` and `field_states` in `backend/src/licence_kyb/schemas/kyb_form.py`
- [X] T021 [P] Write the authority profiles in `backend/src/licence_kyb/profiles/{det,added,dmcc,ifza,generic}.yaml`, each with a `has_register` flag (IFZA is false), and a loader in `backend/src/licence_kyb/profiles/__init__.py`
- [X] T022 [P] Implement typed settings from the environment: reviewer accounts with argon2id hashes, keys, the daily budget, retention, and the applicant-name threshold. Also load `config/models.yaml`, `config/thresholds.yaml` and `config/budgets.yaml`. All of this goes in `backend/src/licence_kyb/config.py`.
- [X] T023 [P] Implement an injectable clock in `backend/src/licence_kyb/clock.py`
- [X] T024 Implement the SQLite schema and forward-only migrations in `backend/src/licence_kyb/store/db.py` and `backend/src/licence_kyb/store/migrations/`. It covers runs, files, review decisions, approvals, submissions, audit events, captured corrections and spans, with a unique key on every write entity.
- [X] T025 [P] Implement MultiFernet encryption, the masking log filter and the trace serializer in `backend/src/licence_kyb/security.py`, and structured JSON logging with the run ID in `backend/src/licence_kyb/logging.py`
- [X] T026 [P] Implement `LLMClient` in `backend/src/licence_kyb/llm/client.py`, following `contracts/model-calls.md`:
  - structured outputs, strict tools and explicit effort
  - cache-ordered prompts
  - refusal and `max_tokens` handling
  - server-side fallback, recording the serving model
  - a daily budget check
  - typed errors
  - a span per call

  Implement the replay recorder, which stores the serving model, in `backend/src/licence_kyb/llm/recorder.py`.
- [X] T027 [P] Implement spans (step, model call, tool call), with OpenTelemetry GenAI attribute names, requested and serving model, and thinking tokens, in `backend/src/licence_kyb/tracing.py`
- [X] T028 Implement `backend/src/licence_kyb/ops.py`:
  - startup resume of `received` and `processing` runs
  - the deadline sweep
  - the scheduled retention job
  - the daily budget counter

  Add `/healthz` and `/readyz` in `backend/src/licence_kyb/api/routes_health.py`.
- [X] T029 Implement `RunState` in `backend/src/licence_kyb/state.py`, and the graph skeleton with the SQLite checkpointer and the rule that side effects run only in their own nodes, in `backend/src/licence_kyb/graph.py`
- [X] T030 [P] Implement the synthetic licence generator in `scripts/gen_licences.py`, with layouts in `scripts/layouts/` (`reportlab`, per research R9a):
  - at least two bilingual layouts per authority, with Noto Naskh Arabic
  - QR codes and a SPECIMEN watermark
  - Faker values with a fixed seed
  - a ground-truth JSON per document, with its group, split and mix weight
  - the degradations in the catalogue
- [X] T031 [P] Add `data/high_risk_activities.yaml`, `data/activities_sample.yaml` and `data/registry_mock.json` (DET, ADDED and DMCC entries only)
- [X] T032 Generate the labelled catalogue (every group and count in `test-cases.md`) in `evals/cases/synthetic/`. Add `scripts/fetch_public_samples.py`, with hand labels in `evals/cases/public/`.
- [X] T033 Implement a minimal case runner in `evals/runner.py`. It runs the graph headless over a set of cases, with a simulated reviewer that answers from ground truth, and returns the final state of each case. US3 calibration and the US4 comparison use it before US6 adds reports.
- [ ] T034 *(script ready in `scripts/measure_throughput.py`; measurement pending owner approval of paid API use)* **Manual, not in CI (it uses the paid API).** Write a throughput probe in `scripts/measure_throughput.py`. It calls the SDK directly, with prompts of the planned sizes and synthetic page images, at the planned efforts. It needs no pipeline node. Record output tokens per second, time to first token and p95 latency in `docs/experiments.md`. Then set the provisional budgets in `contracts/resolver-tools.md` and the plan's latency budget from the probe.

**Checkpoint**: schemas, storage, client, operations, tracing, test data and the runner are ready. The foundation tests pass.

---

## User Story 1 - Get a pre-filled form from an uploaded licence (Priority: P1)

**Branch**: `feature/001-licence-to-kyb-us1`

**Goal**: upload a licence and get a draft KYB form. Every value is checked and linked to its evidence text.

**Independent Test**: upload `det_clean_001.pdf`. The draft form equals its ground truth, and each value has evidence. In this story, every flagged field routes to review. Only an invalid file or an out-of-scope document routes to reject.

### Tests for User Story 1 (write first; they must fail)

- [X] T035 [P] [US1] Write intake and preprocess tests from the "Intake and reading" table in `backend/tests/unit/test_intake_preprocess.py`
- [X] T036 [P] [US1] Write rule tests from the "Checks" table in `backend/tests/unit/test_rules.py`, and Hypothesis properties (≥ 500 examples each) in `backend/tests/unit/test_rules_properties.py`
- [X] T037 [P] [US1] Write form-mapping tests from the "Form filling" table in `backend/tests/unit/test_map_form.py`
- [X] T038 [P] [US1] Write graph tests from the "Document identification and extraction" table, using recorded responses from synthetic documents, in `backend/tests/graph/test_route_extract.py`
- [X] T039 [P] [US1] Write API tests per `contracts/http-api.md` in `backend/tests/api/test_session_and_upload.py`:
  - sign-in, sign-out and the rate limit
  - CSRF on state-changing requests
  - `POST /api/runs` and `GET /api/runs/{id}`
- [X] T040 [P] [US1] Write Vitest tests in `frontend/tests/upload_and_view.test.tsx`:
  - sign-in errors are shown
  - upload limits are shown before submit
  - flagged fields appear expanded with their reason
  - the evidence highlight follows the selected field
  - status is shown as text, not colour only

### Implementation for User Story 1

- [X] T041 [P] [US1] Implement the intake node in `backend/src/licence_kyb/nodes/intake.py`: magic-byte type check, size, page and megapixel limits, SHA-256 dedupe, encrypted storage
- [X] T042 [P] [US1] Implement the preprocess node in `backend/src/licence_kyb/nodes/preprocess.py`:
  - 200 DPI rendering with a time limit
  - the text-layer read
  - Tesseract `eng+ara` words with boxes
  - deskew and rotate
  - QR decoding as untrusted text
- [X] T043 [P] [US1] Write the route and extract prompts in `backend/src/licence_kyb/llm/prompts/route.md`, `extract_primary.md` and `extract_secondary.md`, following `contracts/model-calls.md`
- [X] T044 [US1] Implement the route node in `backend/src/licence_kyb/nodes/route.py`. It does the authority cross-check, and corroborates out of scope (no licence-number pattern and no licence title in the OCR text) before any reject. Unclear and uncorroborated labels go to review.
- [X] T045 [US1] Implement the extract node in `backend/src/licence_kyb/nodes/extract.py`: primary and secondary passes in parallel, one retry naming the failing fields, an agreement map, and `fallback_model` and `processing_failed` reasons
- [X] T046 [P] [US1] Implement the rule base, with the `passed`, `failed`, `could_not_run` and `not_applicable` outcomes, plus the expiry, number-format and date-order rules, in `backend/src/licence_kyb/rules/{base,expiry,number_format,dates}.py`
- [X] T047 [P] [US1] Implement the ownership, legal-form and Arabic-name rules in `backend/src/licence_kyb/rules/{ownership,legal_form,arabic_name}.py`
- [X] T048 [P] [US1] Implement the activity, evidence, QR, registry (mock, `not_applicable` without a register) and applicant-name rules in `backend/src/licence_kyb/rules/{activity,grounding,qr,registry,applicant}.py`
- [X] T049 [US1] Implement the validate node in `backend/src/licence_kyb/nodes/validate.py`. It runs every rule and never raises.
- [X] T050 [US1] Implement the map-form node (the draft form) in `backend/src/licence_kyb/nodes/map_form.py`. It handles required documents, Ejari and Tawtheeq, controller merging on name and nationality, and `ubo_needs_examination`.
- [X] T051 [US1] Wire intake → preprocess → route → extract → validate → map_form in `backend/src/licence_kyb/graph.py`. In this story, any flagged field routes to `needs_review`, and only file and `out_of_scope` reasons route to `reject`.
- [X] T052 [US1] Implement the session endpoints (argon2id, rate limit, CSRF, sign-out) in `backend/src/licence_kyb/api/routes_session.py` and `backend/src/licence_kyb/api/csrf.py`. Implement the runs endpoints (`POST /api/runs`, `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/pages/{n}`) in `backend/src/licence_kyb/api/routes_runs.py`.
- [X] T053 [P] [US1] Add the strings for sign-in, upload, progress, field states, route labels and reason codes to `frontend/src/copy.ts`, following `docs/ui-copy.md`. Implement the copy check in `scripts/lint_copy.py`.
- [X] T054 [US1] Generate `frontend/src/api/generated.ts` (`make types`). Build these pages, starting from `astryx template`, in `frontend/src/pages/` and `frontend/src/components/`:
  - the Sign-in page
  - the Upload page
  - a read-only Review page: a document viewer with evidence highlight, and the form with status labels
- [X] T055 [US1] Record the model responses for every US1 graph test in `backend/tests/fixtures/llm/`. Confirm that the US1 backend and frontend tests pass, then open the US1 pull request into `develop`.

**Checkpoint**: US1 works on its own. Upload a licence and see a checked draft form with evidence.

---

## User Story 2 - Examine flagged fields and submit the form (Priority: P2)

**Branch**: `feature/001-licence-to-kyb-us2`

**Goal**: the reviewer approves or corrects flagged fields, overrides only checks that could not run, rejects or reopens, and submits. The system verifies the stored submission and writes exactly one audit event per action.

**Independent Test**: correct one flagged field, approve and submit. Exactly one verified submission holds the corrected value, and the audit names the reviewer.

### Tests for User Story 2 (write first; they must fail)

- [X] T056 [P] [US2] Write graph tests from the "Review, submission and verification" table in `backend/tests/graph/test_review_submit.py`. Include "resumed twice → one audit event per decision, one captured correction, one version increase".
- [X] T057 [P] [US2] Write API tests for review, reopen, retry and submit, covering statuses 200, 202, 401, 403 and 409 and their codes (including `not_retryable`) per `contracts/http-api.md`, in `backend/tests/api/test_review_submit.py`
- [X] T058 [P] [US2] Write an audit property test (in `backend/tests/api/test_review_submit.py`, to reuse its API harness): for any sequence of decisions, including repeats, the audit log alone identifies the approver and every change before approval, with one event per key
- [X] T059 [P] [US2] Write Vitest tests in `frontend/tests/review_actions.test.tsx`:
  - Retry processing appears only for `processing_failed` and `budget_exhausted`
  - Enter value appears for `not_present` fields, and marks the value as "Value from reviewer"
  - Approve-form is disabled while any flagged field is undecided
  - Override asks for a reason
  - Submit is disabled after a change until the form is approved again
  - focus moves to the next flagged field
  - each 409 code shows its string

### Implementation for User Story 2

- [X] T060 [P] [US2] Use the keyed `Database` methods in `backend/src/licence_kyb/store/db.py` for decisions, approvals, submissions, audit events and captured corrections (built in Foundation). Add only what US2 needs: reading the latest submission and approvals per version. *(Simplified 2026-11-22: one store module, not five; same keys and guarantees.)*
- [X] T061 [US2] Add the `wait_for_reviewer` node in `backend/src/licence_kyb/pipeline.py`. It only calls `interrupt()` and returns the action; it has no side effects. Every run waits here after processing, including rejected runs, so reopen is just another action.
- [X] T062 [US2] Add the `apply_action` node, with its logic in `backend/src/licence_kyb/nodes/review.py`, for the review action:
  - keyed writes
  - re-validation, with the evidence check `not_applicable` for values entered by a reviewer
  - an override only on `could_not_run`, with a reason
  - a form version increase and a rebuilt draft form
  - a captured correction written encrypted, with `pending` status
- [X] T063 [US2] Handle the submit action in `apply_action` (logic in `backend/src/licence_kyb/nodes/review.py`):
  - the approval is bound to the form version
  - the write is idempotent, keyed by `action_id` and unique per approved form version
  - the read-back comparison sends the run to `done`, or back to review with `verification_failed`
  - after `verification_failed`, a newly approved form version can be submitted, and the run is done when its latest submission verifies
- [X] T064 [US2] Handle reject and reopen in `apply_action`, and `POST /api/runs/{id}/reopen` in `backend/src/licence_kyb/api/routes_runs.py`. Each needs a reason and a client `action_id`, so a reject → reopen → reject cycle records every event.
- [X] T065 [US2] Implement retry processing (`POST /api/runs/{id}/retry`, only after `processing_failed` or `budget_exhausted`, resuming from the last checkpoint) and hand entry of values for `not_present` fields, in `backend/src/licence_kyb/api/routes_runs.py` and `backend/src/licence_kyb/nodes/review.py`
- [X] T066 [US2] Wire `persist → wait_for_reviewer → apply_action → (wait_for_reviewer | the failed step on retry: preprocess when no pages were read, route when there is no route result, else extract | END when done)` in `backend/src/licence_kyb/pipeline.py`. Add the review, submit, reopen and retry endpoints in `backend/src/licence_kyb/api/routes_runs.py`. The endpoints live in `backend/src/licence_kyb/api/routes_review.py`. `Pipeline.check` runs the pure checks in `nodes/review.py` and the endpoint answers 409 before resuming the run, so the graph only sees valid actions.
- [X] T067 [US2] Add the strings for Approve, Correct, Override and its reason, Reject and its confirmation, Reopen, Retry processing, Enter value, Submit, verification and each error code to `frontend/src/copy.ts`. Add the Retry processing and Enter value actions. Make the Review page interactive in `frontend/src/pages/ReviewPage.tsx`.
- [X] T068 [US2] Record the model responses for the US2 graph tests (scripted responses from labels, per research R10a). Confirm that the US2 tests pass, then open the US2 pull request into `develop`.

**Checkpoint**: US1 and US2 work together. A licence can be examined, approved and submitted, and the record is verified.

---

## User Story 3 - Clean licences arrive ready, risky ones go to review (Priority: P3)

**Branch**: `feature/001-licence-to-kyb-us3`

**Goal**: evidence-based confidence, corroborated rejection, and calibrated routing into `ready`, `needs_review` or `reject`.

**Independent Test**: run the labelled test split with `evals/runner.py`. Every case gets its expected route and reason codes, and no failed blocking check routes `ready`.

### Tests for User Story 3 (write first; they must fail)

- [X] T069 [P] [US3] Write gate tests from the "Confidence and routing" table in `backend/tests/unit/test_gate.py`, and Hypothesis properties in `backend/tests/unit/test_gate_properties.py`. The properties include "reject only with a file reason, `out_of_scope` or a corroborated `expired`".
- [X] T070 [P] [US3] Write calibration tests in `backend/tests/unit/test_calibrate.py`. On a labelled fixture set of signal rows (one row per field: its signals and whether the value was right), the fitted thresholds reach ≥ 99% critical-field precision among `ready` cases in the calibration split. The tests never use the test split.
- [X] T071 [P] [US3] Write Vitest tests in `frontend/tests/confidence.test.tsx`: each flagged field shows its score, its threshold and the signal behind a low score

### Implementation for User Story 3

- [X] T072 [P] [US3] Implement the confidence node in `backend/src/licence_kyb/nodes/confidence.py`. It stores the score and every signal.
- [X] T073 [P] [US3] Implement the gate node in `backend/src/licence_kyb/nodes/gate.py`:
  - corroborated `expired` → reject
  - uncorroborated → `expiry_uncertain`
  - `fallback_model` is never `ready`
  - `not_applicable` checks never fail
- [X] T074 [US3] Implement `scripts/calibrate.py`. It fits the weights and thresholds on the calibration split through `evals/runner.py`, and writes `backend/config/thresholds.yaml` with a fit summary. Until a live eval runs (it needs a model API key), `thresholds.yaml` holds documented default values marked `fitted: false` (research R5).
- [X] T075 [US3] Insert confidence between validate and map_form, and replace the User Story 1 `decide` node with `gate`, in `backend/src/licence_kyb/pipeline.py`. A `ready` run waits at `awaiting_submit` (no field decisions needed); every other route waits at `awaiting_review` or `rejected`.
- [X] T076 [US3] Show the score, threshold and signals in a `ConfidenceDetails` component (`frontend/src/components/ConfidenceDetails.tsx`) inside the field details of `frontend/src/pages/ReviewPage.tsx`, with their strings in `frontend/src/copy.ts`. Open the US3 pull request into `develop`.

**Checkpoint**: clean licences arrive with no flagged fields. Risky ones are flagged with reason codes, and nothing is rejected on an uncorroborated value.

---

## Model providers (cross-cutting; FR-044, ADR-004)

**Branch**: `feature/001-licence-to-kyb-model-providers`

**Goal**: run every model step on another provider, including an open-weight model on this machine, by configuration only.

**Independent Test**: with `MODEL_PROFILE=local`, a synthetic licence is processed end to end with real readings, and the trace names the local model.

- [X] T105 [P] Write transport tests in `backend/tests/unit/test_openai_transport.py` against a fake HTTP server: the request mapping (system, JSON schema, images by `vision`, tools), the stop-reason mapping, usage, and each failure (server error, timeout, non-JSON reply) mapped to the existing retry and `processing_failed` paths, and a local call costing 0.
- [X] T106 [P] Write config tests in `backend/tests/unit/test_model_profiles.py`: `MODEL_PROFILE` picks a profile, an unknown profile fails at startup with a message that names the valid ones, and every profile names a model for every step.
- [X] T107 Implement `OpenAICompatibleTransport` in `backend/src/licence_kyb/llm/openai_compatible.py`.
- [X] T108 Move `config/models.yaml` to profiles (`anthropic`, `local`) with `vision`, `price_per_mtok` and `deadline_seconds`; load the profile in `config.py`; build the transport in `api/main.py`; use the profile price in `ModelResponse.cost_usd`. The profile's `deadline_seconds` overrides the default in `budgets.yaml`. `confidence.load_config` reads `thresholds.<profile>.yaml` when it exists, else `thresholds.yaml`; `scripts/calibrate.py` writes the active profile's file.
- [X] T109 Leave page images out of requests when the profile has no vision. Done once, in the transport (`llm/openai_compatible.py`), so the route and extract nodes do not change.
- [X] T110 Add `scripts/fetch_llama_server.sh` (pinned release and SHA-256) and `make local-model`, which starts `llama-server` with the model file from `LOCAL_MODEL_PATH`.
- [ ] T111 Run the quickstart "Providers" row on the local model, record the result and timings in `docs/experiments.md`, and open the pull request.

---

## User Story 4 - The system re-reads values that failed a check (Priority: P4)

**Branch**: `feature/001-licence-to-kyb-us4`

**Goal**: a bounded resolver agent with read-only tools proposes fixes, and code validates each proposal before it is used.

**Independent Test**: run the scan and photo cases with the resolver on and off through `evals/runner.py`. Compare field accuracy and review rate.

### Tests for User Story 4 (write first; they must fail)

- [X] T077 [P] [US4] Write graph tests from the "Re-reading failed values" table, using recorded tool loops, in `backend/tests/graph/test_resolver.py`
- [X] T078 [P] [US4] Write tool tests from the "Tool error responses" table and its properties in `backend/tests/unit/test_resolver_tools.py`. Check `is_error`, `error_code`, `next_action`, `allowed`, the size limit, and the absence of stack traces. Assert structure only, never wording.

### Implementation for User Story 4

- [X] T079 [P] [US4] Implement the read-only tools per `contracts/resolver-tools.md` in `backend/src/licence_kyb/tools/{reread_region,ocr_region,registry_mock,activity_lookup,validation_report}.py`. The vision call in `reread_region` goes through `LLMClient`, with its own span. Every failure returns the structured error response from the contract\'s "Error responses" section, through one shared `tools/errors.py`.
- [X] T080 [P] [US4] Write the resolver prompt and the tool definitions in `backend/src/licence_kyb/llm/prompts/resolve.md` and `backend/src/licence_kyb/tools/definitions.py`
- [X] T081 [US4] Implement the resolver loop in `backend/src/licence_kyb/nodes/resolve.py`:
  - the budgets from the contract table (turns, rounds, tokens including vision re-reads, wall time, tool calls)
  - scope and argument checks before each call
  - parallel tool results in one message
  - code retries for temporary errors
  - the best accepted fixes kept
- [X] T082 [US4] Add the conditional edge validate → resolve → validate (at most 2 rounds) → confidence, and the `resolver_enabled` setting, in `backend/src/licence_kyb/pipeline.py`. A profile's `resolver_seconds` overrides the time limits.
- [X] T083 [US4] Show proposed fixes, labelled as model output, in the field details of `frontend/src/pages/ReviewPage.tsx` (through `model_rationale`), with their strings in `copy.ts`. Add a Vitest case in `frontend/tests/confidence.test.tsx`.
- [X] T084 [US4] Record the tool-loop responses for the US4 graph tests (scripted, per research R10a), then open the US4 pull request into `develop`. The resolver on/off comparison needs real readings and the eval report, so it runs in User Story 6 on the local model (T111).

**Checkpoint**: poor scans produce fewer flagged fields, and no proposal bypasses validation.

---

## User Story 5 - Inspect how a run reached its result (Priority: P5)

**Branch**: `feature/001-licence-to-kyb-us5`

**Goal**: a trace of every step, with duration, cost, outcome and serving model, plus daily summary rates. Personal data is masked.

**Independent Test**: open the trace of a run with the owner "Ahmed Al Mansoori". Every step is listed, and the name never appears unmasked.

### Tests for User Story 5 (write first; they must fail)

- [X] T085 [P] [US5] Write API tests for `GET /api/runs/{id}/trace`, `GET /api/runs` and `GET /api/metrics/summary` in `backend/tests/api/test_trace_metrics.py`:
  - every step appears in order, with duration, cost and serving model
  - the rates are correct for a seeded day
  - no response body contains unmasked personal data
- [X] T086 [P] [US5] Write Vitest tests in `frontend/tests/runs_trace.test.tsx`: the span tree shows nesting, tokens and cost, and the summary shows each rate with its label

### Implementation for User Story 5

- [X] T087 [US5] Implement the trace and summary endpoints, with the masking serializer, in `backend/src/licence_kyb/api/routes_trace.py`, and the summary query in `backend/src/licence_kyb/store/db.py`. Record one `model_call` span per resolver turn and vision re-read, and one `tool_call` span per tool call (its error code, and the result the model saw, encrypted). `persist` writes each run's cost and processing duration for the run list.
- [X] T088 [US5] Build the Runs page (with the daily summary) and the Trace page in `frontend/src/pages/RunsPage.tsx`, `frontend/src/pages/TracePage.tsx` and `frontend/src/components/SpanTree.tsx`, with the routes `/runs` and `/runs/:id/trace`, with their strings in `copy.ts`. Open the US5 pull request into `develop`.

**Checkpoint**: any run's path, duration and cost can be inspected safely. Drift in refusals, fallbacks and review rate is visible.

---

## User Story 6 - Measure quality on labelled cases (Priority: P6)

**Branch**: `feature/001-licence-to-kyb-us6`

**Goal**: a repeatable eval report on the held-out split, a regression comparison, and synthetic twins of approved corrections.

**Independent Test**: run the report, change one threshold, and compare. Only the affected cases are listed.

### Tests for User Story 6 (write first; they must fail)

- [X] T089 [P] [US6] Write grader tests in `evals/tests/test_graders.py`:
  - graders read only stored state
  - list fields are scored per element after normalisation (whitespace, case, Arabic letter forms, ISO dates)
  - the safety grader flags any submission without an approval
  - the Wilson interval is correct on known counts
- [X] T090 [P] [US6] Write comparison tests in `evals/tests/test_compare.py`: given two reports, exactly the cases whose route, reason codes or values changed are listed
- [X] T091 [P] [US6] Write twin tests in `evals/tests/test_make_twin.py`: a twin has the same fault group and layout as its correction and contains none of the correction's personal values

### Implementation for User Story 6

- [X] T092 [P] [US6] Implement the graders (route, reason codes, fields, safety) in `evals/graders.py`
- [X] T093 [US6] Implement the report in `evals/run.py`, built on `evals/runner.py`. Each case is graded on its state at the first pause (route, reasons, values, confidence); the full review flow is covered by the User Story 2 tests. `--model scripted` answers from labels (offline, CI: it checks routing and rules, not reading) and `--model profile` uses `MODEL_PROFILE`. `--no-resolver` turns the resolver off for the on/off comparison. The report header names the model of each step (FR-044), and the run writes `signals.jsonl` (field, split, signals, correct) for `scripts/calibrate.py`. It covers:
  - the test split only
  - mix weighting
  - per-field accuracy
  - `ready` precision with a Wilson 95% interval
  - review rate
  - p95 per stage against the latency budget
  - cost per document, including thinking tokens
  - the share of `max_tokens` stops
  - pass^3 on the 30-case routing subset

  It also runs the comparisons: resolver on/off, Haiku 5.5 as router, Sonnet 5.5 as secondary pass, one pass vs two, and OCR text in the prompt or not. On release branches it also runs the 400-case precision set (`make eval-precision`). Reports are written to `evals/reports/<date>.md`.
- [X] T094 [US6] Implement `make eval-compare` against the last saved baseline in `evals/compare.py`. The same comparison shows the resolver on/off difference (moved here from T084)
- [X] T095 [US6] Implement `scripts/make_twin.py` and the maintainer approval command (`make approve-capture ID=…`). It turns an approved captured correction into a synthetic twin in `evals/cases/twins/`.
- [X] T096 [US6] Add the manual and release-branch eval workflow in `.github/workflows/evals.yml`: pinned SHAs, an environment-scoped API key secret, and the report uploaded as an artifact. Open the US6 pull request into `develop`.

**Checkpoint**: quality is measured on held-out data with intervals, and regressions are visible before a merge.

---

## UI and UX polish (from [ux-review.md](ux-review.md))

**Branch**: `feature/001-licence-to-kyb-ui-polish`

**Goal**: the reviewer sees the run, the flagged fields and the actions first, on any screen.

- [X] T112 [P] Review page: put the form actions (status, remaining flagged fields, Approve form, Submit, Reject) at the top of the form panel, before the fields.
- [X] T113 [P] Review page: list flagged fields first under "Fields to examine (N)", then passed fields under "Fields that passed (N)", closed by default.
- [X] T114 [P] Review page: a header with the business name, the upload time and a link to the trace (the run view gains `applicant_name` and `created_at`); run-level reasons show only reasons that have no field.
- [X] T115 [P] Runs page: one status column; on narrow screens a list instead of the table; an empty list links to the upload page.
- [X] T116 [P] Trace page: a header with the business name, and totals for time, cost and model calls.
- [X] T117 [P] Upload page: one sentence on what happens after upload, and a description for the business-name field.
- [X] T118 Review page on narrow screens: the licence page comes right after the fields to examine, before the passed fields.

### Round 2 (owner feedback)

- [ ] T119 Review page: one "next step" card replaces the status banner, the counter and the three buttons. It says what to do now, shows progress, and has at most one primary button (Approve form, or Submit, or Retry, or Reopen).
- [ ] T120 Review page: in a field, the reason, the value and the evidence come first, then Approve and Correct; reading confidence and weak evidence move into a closed "Details" section.
- [ ] T121 Review page: "Documents to request" moves after the fields.
- [ ] T122 Review page: "Reject case" moves to the end of the panel, as a quiet button with its confirmation.

## Polish & Cross-Cutting Concerns

**Branch**: `feature/001-licence-to-kyb-polish`, then `release/0.1.0`

- [X] T097 [P] Add browser checks for every quickstart row with chrome-devtools-axi, and save screenshots to `docs/images/` (`scripts/browser_check.sh`)
- [X] T098 [P] Run a WCAG 2.2 AA pass on all pages (FR-042): an automatic `axe-core` check of every page in the Vitest suite, plus a keyboard-only pass in the browser (flow, visible focus, status by text and icon). Fixes go in `frontend/src/`.
- [ ] T099 [P] Run timed walkthroughs (5 clean, 5 flagged) and compute the reviewer time from audit timestamps for SC-005. Record the result in `docs/experiments.md`.
- [X] T100 [P] Run mutation testing on `backend/src/licence_kyb/rules/` with `mutmut`, and record the score in `docs/experiments.md`
- [ ] T101 Run the full eval suite. Fill `docs/experiments.md`, and replace the README Results section with the measured numbers and intervals, including any target that was missed.
- [X] T102 [P] Add the release workflow in `.github/workflows/release.yml`: a CycloneDX SBOM, a GitHub artifact attestation, and release notes from `CHANGELOG.md`
- [ ] T103 Cut `release/0.1.0` from `develop`. Update `CHANGELOG.md` and link the eval report. Open a pull request into `main`; after it merges, tag `v0.1.0` (annotated, signed) and open the back-merge pull request into `develop`.
- [X] T104 Run `quickstart.md` end to end on a clean clone, and fix any step that fails

---

## Dependencies & Execution Order

### Section dependencies

- **Setup:** no dependencies.
- **Foundation:** depends on Setup. Blocks every story.
- **US1:** depends on Foundation.
- **US2:** depends on US1, because it reviews the draft form that US1 produces.
- **US3:** depends on US1 and on the runner (T033). It can run in parallel with US2.
- **US4:** depends on US1 (validation) and the runner (T033). It can run in parallel with US2 and US3.
- **US5:** depends on Foundation tracing (T027) and US1. It can run in parallel with US2 to US4.
- **US6:** depends on the runner (T033) and US3 for the full metrics.
- **Polish:** depends on every story in the release.

### Within each story

- The tests are written first and must fail.
- Then stores and schemas, nodes, graph wiring, endpoints, and finally UI.
- The story is complete when all its tests pass, its quickstart rows work, and its pull request into `develop` passes the CI gate.

### Parallel opportunities

- **Setup:** T003 to T011 can run in parallel after T002.
- **Foundation:** T012 to T017 (tests) can run in parallel. T018 to T023, T025 to T027, T030 and T031 can run in parallel.
- **US1:** T035 to T040 (tests) can run in parallel. T041 to T043 and T046 to T048 can run in parallel.
- **After US1:** US2, US3, US4 and US5 can proceed in parallel on separate branches.

## Parallel Example: User Story 1

```text
# Tests first, together:
T035 intake/preprocess   T036 rules + properties   T037 mapping
T038 route/extract graph T039 session/upload API   T040 Vitest upload/view

# Then independent modules, together:
T041 intake   T042 preprocess   T043 prompts
T046 rules: base/expiry/format/dates   T047 rules: ownership/legal form/Arabic   T048 rules: activity/evidence/QR/registry/applicant
```

## Implementation Strategy

### User Story 1 first

1. Complete Setup and Foundation.
2. Complete User Story 1 and merge it to `develop`.
3. **Stop and validate:** run the US1 quickstart rows. A checked draft form with evidence is already useful.

### Incremental delivery

1. US1 gives a checked draft form.
2. US2 adds accountable submission.
3. US3 adds fewer reviews for clean licences and safe rejection.
4. US4 adds fewer flagged fields on poor scans, measured.
5. US5 makes every result explainable.
6. US6 makes quality measured on held-out data.

Each story merges to `develop` through its own pull request. Release `0.1.0` is cut only after Polish.
