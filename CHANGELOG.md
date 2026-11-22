# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the
project uses [Semantic Versioning](https://semver.org/). Each release links its eval report.

## [Unreleased]

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

### Changed
- Readability pass: one source for shared constants and types, all SQL in `Database`,
  shorter pipeline nodes, one typed shape for form field values.

### Fixed
- Dates in the wrong order reach the reviewer as `date_order`, not `processing_failed`.
- A run whose processing crashes goes to review and can be retried; an interrupted run
  continues after its last completed step.
