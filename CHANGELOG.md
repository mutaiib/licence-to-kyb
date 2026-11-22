# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the
project uses [Semantic Versioning](https://semver.org/). Each release links its eval report.

## [Unreleased]

## [0.1.0] - 2026-11-22

Eval reports: offline baseline [`evals/reports/scripted-baseline/`](evals/reports/scripted-baseline/);
first real readings [`evals/reports/local-smoke/`](evals/reports/local-smoke/) and
[`evals/reports/local-public/`](evals/reports/local-public/) ([experiments](docs/experiments.md)).

### Added
- Feature 001 specification, plan, contracts, test cases and tasks (Spec Kit).
- Architecture, decision records, engineering practices, UI copy standard and handbook.
- Foundation: typed schemas, authority profiles, encrypted storage with keyed writes,
  model client with replay, tracing, operations, checkpointed graph skeleton, synthetic
  licence generator, labelled case catalogue and case runner.
- Repository standards: CI gate, pre-commit hooks, Dependabot, CODEOWNERS, templates.
- User Story 1: upload a licence and get a checked draft KYB form, each value linked to
  its evidence on the page; sign-in, upload with progress and a read-only review page.
- User Story 2: approve, correct, override, reject, reopen, retry and submit. A
  submission is stored once per approved form version and must read back the same.
- User Story 3: each read field gets a confidence score from six evidence signals; the
  gate routes each run to ready, needs review or reject. An expired licence is rejected
  only when the expiry is corroborated. `scripts/calibrate.py` fits thresholds on real
  readings; until then they are documented defaults (`fitted: false`).
- Model providers: any model step can run on an OpenAI-compatible server (llama.cpp,
  Ollama, vLLM, LM Studio, LiteLLM proxy) through model profiles; Claude stays the default.
- User Story 4: a bounded resolver agent re-reads values that failed a check, with five
  read-only tools and one structured error format; a proposal is kept only when no check
  that doubts the value fails.
- User Story 5: a trace of every step, model call and tool call, and today's refusal,
  fallback and examination rates, cost and remaining budget, with personal data hidden.
- User Story 6: an eval report on the held-out split (route, reasons, per-field accuracy,
  `ready` precision with a Wilson interval, mixed review rate, cost, p95 per stage), a
  report comparison, synthetic twins of approved corrections, and an eval workflow.
- Release workflow: CycloneDX SBOMs, a build-provenance attestation and release notes on
  a version tag. Mutation testing of the rules (`make mutation`).
- Handbook pages on model providers, UX for human review, and the bugs each check caught.
- Review page: one next step at a time, with at most one main button; reading confidence in a
  closed Details section; documents to request and Reject case after the fields.
- Eval options `--limit` and `--public`; the report counts runs that stopped in processing.
- First real readings with a local open-weight model (docs/experiments.md).

### Changed
- UI and UX: the review page leads with the business name, the status and the form
  actions, and lists the fields to examine first; the runs page reads well on a phone;
  the trace shows totals; automatic WCAG 2.2 AA checks on every page.
- Readability pass: one source for shared constants and types, all SQL in `Database`,
  shorter pipeline nodes, one typed shape for form field values.

### Fixed
- A `ready` run asked for submit before anyone approved the form.
- The evidence check: a date or identifier must appear exactly on the document, not
  only in the model's own quote.
- Dates in the wrong order reach the reviewer as `date_order`, not `processing_failed`.
- A run whose processing crashes goes to review and can be retried; an interrupted run
  continues after its last completed step.

[Unreleased]: https://github.com/mutaiib/licence-to-kyb/compare/v0.1.0...develop
[0.1.0]: https://github.com/mutaiib/licence-to-kyb/releases/tag/v0.1.0
