# Research: Trade Licence to KYB Onboarding Form

The Technical Context has no open questions. This file records each technical decision, why it was made, and what else was considered. Domain facts (licence layouts, verification services, KYB requirements) are in [`docs/research.md`](../../docs/research.md).

## R1. Orchestration

- **Decision:** a LangGraph `StateGraph`, with a SQLite checkpointer and `interrupt()` for the review and submit pauses.
- **Rationale:** the steps are fixed. The checkpointer lets a paused run survive a restart (FR-030), and `Command(resume=…)` delivers the reviewer's decision.
- **Alternatives considered:**
  - Plain Python with a hand-written state machine: more code for persistence and resumption.
  - A single agent with every tool: unpredictable paths and multiplied error rates.
  - Several agents: no reason applies ([ADR-001](../../docs/decisions/ADR-001-workflow-with-one-agent.md)).

## R2. Model access

- **Decision:** the official `anthropic` SDK, called through one injectable `LLMClient`.
  - `claude-opus-5-5` for route (effort `low`), extract (`medium`) and resolve (`medium`).
  - Structured outputs through `client.messages.parse(output_format=Model)`.
  - `strict` tools with `tool_choice: auto`.
  - Server-side refusal fallback enabled.
- **Rationale:**
  - The request and response stay visible and testable.
  - Forced `tool_choice` is not available on this model, so `strict` tools with `auto` plus clear prompt instructions are used.
  - Effort defaults to `medium`, so it is always set explicitly.
- **Alternatives considered:**
  - LangChain model wrappers: they hide request details ([ADR-002](../../docs/decisions/ADR-002-anthropic-sdk-inside-langgraph-nodes.md)).
  - A cascade with a smaller router model: measured as an experiment, not adopted without data.

## R3. Evidence for values

- **Decision:** `evidence_quote` and `page` are schema fields on every value. Code checks the quote against the OCR text with `rapidfuzz` (partial ratio ≥ 85) and checks that the value appears in the quote.
- **Rationale:** the API's citations feature cannot be combined with structured outputs in one request.
- **Alternatives considered:** a second request with citations enabled. It doubles cost and loses the schema guarantee.

## R4. OCR and rendering

- **Decision:**
  - `pypdfium2` renders pages at 200 DPI.
  - `pdfplumber` reads the text layer when one exists.
  - Otherwise, Tesseract with `eng+ara` gives words, boxes and confidences.
  - OpenCV handles QR decoding and deskewing.
- **Rationale:** these tools are free and run locally. Word boxes support evidence highlighting in the review page and the `licence_ocr_region` tool.
- **Alternatives considered:**
  - Cloud OCR services: cost, an external dependency, and personal data leaving the machine.
  - Vision-only extraction with no OCR: no independent text to ground quotes against.

## R5. Confidence and thresholds

- **Decision:** a weighted sum of checkable signals. Weights and per-field thresholds are fitted by `scripts/calibrate.py`, which maximises `ready` coverage subject to ≥ 99% critical-field precision ([ADR-003](../../docs/decisions/ADR-003-confidence-from-evidence.md)).
- **Rationale:** the score is transparent and can be shown on the review page, and it fits a small labelled set.
- **Alternatives considered:**
  - The model's self-rating alone: uncalibrated.
  - A learned classifier: too little data, and opaque.

## R6. Resolver loop

- **Decision:** a hand-written Messages API tool loop inside one graph node.
  - Budgets: defined once, in [contracts/resolver-tools.md](contracts/resolver-tools.md#budgets-the-only-definition).
  - Scope check: only failed fields.
  - Proposals are applied only after validation.
- **Rationale:** each step is visible in the trace, and the budget and scope checks run before every tool call.
- **Alternatives considered:**
  - The SDK tool runner: less control over the per-step checks.
  - Managed agents: hosted state does not fit a local, checkpointed workflow.

## R6a. Side effects and resumption

- **Decision:** the review node only collects the decision payload. Separate nodes apply the decisions, write the audit events, captured corrections and form versions, and submit.
  - Every write is keyed: `decision_id`, `(run_id, form_version)`, `run_id`.
  - A startup task resumes runs in `received` or `processing`.
  - A sweep moves runs past their deadline to review.
- **Rationale:** LangGraph runs a node again from its start when it resumes after `interrupt()`. Keyed writes in dedicated nodes make a repeat harmless. Background tasks are not durable on their own, so the checkpoint plus the startup resume covers crashes.
- **Alternatives considered:**
  - Writes inside the interrupting node: they are duplicated on resume.
  - An external job queue (Celery, RQ): too heavy at this scale. The checkpointer already stores the progress.

**Simplified for US2 (2026-11-22):** one `wait_for_reviewer` node (interrupt only) and one `apply_action` node (all reviewer actions, keyed writes). Actions are checked by pure functions in `nodes/review.py` (through `Pipeline.check`) before the run resumes, so 409 answers are immediate and the graph only sees valid actions. A run whose processing crashes is moved to the same pause (`Pipeline.mark_failed`), so a retry works on it too.

## R7. Persistence and security

- **Decision:**
  - SQLite for the application data and, in a separate file, the checkpoints.
  - Fernet encryption for files and for personal-data columns.
  - A logging filter and a trace serializer that mask personal-data fields.
  - A retention job, with a default of 30 days.
  - Reviewer accounts from configuration, with argon2id hashes.
  - `HttpOnly`, `Secure`, `SameSite=Strict` session cookies with an 8-hour expiry.
  - Double-submit CSRF tokens, and login rate limiting.
  - `MultiFernet` for key rotation.
- **Rationale:** this is demo scale, with no external services. It meets FR-004, FR-022, FR-032 and FR-036.
- **Alternatives considered:** PostgreSQL. It is unnecessary at this scale; the data access layer keeps a later switch simple.

## R8. Frontend

- **Decision:**
  - React 19, Vite and TypeScript, with Astryx (`@astryxdesign/core`, `theme-neutral`).
  - Layouts start from `astryx template`, and props come from `astryx component <Name>`.
  - API types are generated with `openapi-typescript`.
  - All strings live in `copy.ts`.
- **Rationale:** the user's choice of design system. Generated types prevent drift between frontend and backend. A single copy file makes the ASD-STE100 rules enforceable.
- **Alternatives considered:**
  - Server-rendered HTMX: does not use Astryx.
  - Streamlit: looks like a prototype.

## R8a. Statistics of the eval

- **Decision:**
  - About 100 labelled cases, split 50/50 by group with a fixed seed: calibration fits the thresholds, and test reports the metrics.
  - Precision of `ready` is reported with a Wilson 95% interval.
  - The review rate is weighted to the realistic mix: 70% clean, 20% scans and photos, 10% problem cases.
  - List fields are scored per element after normalisation.
  - pass^3 is run on a 30-case routing subset to limit cost.
- **Rationale:** a 99% precision claim on 20 cases means nothing without an interval, and calibrating on the reporting set overfits.
- **Alternatives considered:** reporting on the full set. Rejected, because it is optimistically biased.

## R9. Test data

- **Decision:**
  - Synthetic bilingual licences are generated from Jinja2 templates with WeasyPrint. Each has a ground-truth JSON, a fixed seed, degradations, a "SPECIMEN — SYNTHETIC" watermark and generic logos.
  - There are at least two layout variants per authority, built from different public descriptions, so the extractor is not measured on a single template.
  - One public licence is downloaded at eval time, used only in the live eval, and only its labels are committed.
  - Reviewer corrections return as synthetic twins (`scripts/make_twin.py`).
- **Rationale:** no public dataset of trade licences exists, and private documents are not allowed.
- **Alternatives considered:** scraping licences found online. They contain private personal data, so this was rejected.

## R9a. Rendering and OCR without system packages (amended 2026-11-22)

- **Decision:**
  - Synthetic licences are drawn with `reportlab`, using `arabic-reshaper` and `python-bidi` for correct Arabic shaping, instead of Jinja2 and WeasyPrint. The result is a PDF with a real text layer.
  - Scans and photos are made by rasterising that PDF with `pypdfium2` and applying degradations with Pillow and OpenCV.
  - Fonts: Noto Naskh Arabic and Noto Sans. The path is configurable, and the Docker image installs `fonts-noto`.
  - Tesseract language data (`eng`, `ara`) is fetched by `scripts/fetch_tessdata.sh` into `var/tessdata` (gitignored), pinned by SHA-256, and selected with `TESSDATA_PREFIX`. The Docker image installs `tesseract-ocr-ara` instead.
- **Rationale:** WeasyPrint needs Pango and Cairo system libraries, and Tesseract's Arabic data is a system package. Neither can be assumed on a developer machine or in CI. The pure-Python route gives the same outputs: a text-layer PDF, plus scan images.
- **Alternatives considered:**
  - WeasyPrint in Docker only: it would split the local and CI paths.
  - Headless Chrome printing: a heavy dependency for test-data generation.

## R10a. Scripted model responses for offline graph tests (amended 2026-11-22)

- **Decision:** offline graph tests use a `ScriptedTransport`. It answers each model call with a response written from the case's labelled ground truth, plus explicit fault variants: a malformed reply, a refusal, `max_tokens`, a fallback serving model, and injected text. Live recordings (`RecordingTransport`, `make record`) are added when an API key is available, and are stored next to the scripted fixtures.
- **Rationale:**
  - Graph tests check the pipeline's logic: routing, validation, corroboration, form mapping and writes. Model quality is measured by the live eval, not by unit tests.
  - Scripted responses make every fault path testable on purpose, and keep CI free and deterministic.
- **Demo mode:** the same answers power a local demo mode (`DEMO_ANSWERS_DIR`), so the app can be run and checked visually without a model key. It is opt-in, logs a warning at startup, and is never used in production or in evals.
- **Alternatives considered:**
  - Recording every response live: it needs a paid key in CI, and it cannot produce a refusal or a fallback on demand.

## R10. Testing approach

- **Decision:**
  - Tests are parametrised over the value tables in [test-cases.md](test-cases.md), with Hypothesis for rule properties.
  - Graph tests use recorded model responses keyed by a prompt and input hash.
  - Every test that involves dates uses a fixed clock (2026-06-01).
  - Assertions only on outcomes: route, values, form, submissions, audit.
- **Rationale:** Constitution Principle VI. Tests survive refactors and prompt changes.
- **Alternatives considered:** snapshot tests of prompts or messages. They break on wording changes without any behaviour change, so this was rejected.
