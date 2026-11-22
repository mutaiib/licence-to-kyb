<!--
Sync Impact Report
- Version change: 2.1.0 → 2.2.0 (MINOR: Technology Constraints add provider-neutral model calls)
- Earlier: 2.0.0 → 2.1.0 (MINOR: Development Workflow adds the per-story local visual check)
- Earlier: 1.1.0 → 2.0.0 (MAJOR: Principle X and the Branching and Releases rules were redefined)
- Modified principles: none
- Modified sections:
  - Technology Constraints: "the official anthropic SDK for every model call" becomes "one injectable client; Claude via the official SDK by default; other providers only through the OpenAI-compatible transport, chosen by configuration". Eval reports name the models they measured.
- Added sections: none
- Removed sections: none
- Templates and documents:
  ✅ .specify/templates/plan-template.md, spec-template.md, tasks-template.md: no provider-specific rule, no edit needed
  ✅ specs/001-licence-to-kyb/plan.md: Technical Context and Constitution Check X updated
  ✅ README.md: stack line updated
  ✅ docs/decisions/ADR-004: records the decision
- Deferred TODOs: none
-->

# licence-to-kyb Constitution

## Core Principles

### I. Workflow First, One Bounded Agent

- Steps that can be written down before the input is read MUST run as a fixed workflow, controlled by code.
- A model-driven agent MAY be used only for a step whose path depends on what it finds. In this project, that is repairing values that failed a check.
- The agent MUST have hard limits on steps, tokens, time and rounds, and code MUST stop it when a limit is reached.
- Adding a second agent requires a written reason: the work does not fit one context, needs different permissions, or gains from running in parallel.

**Rationale:** model steps multiply error rates. Code steps do not.

### II. Typed Contracts at Every Boundary

- Every hand-off between steps, every model output, every tool input and every API body MUST be a schema-validated object.
- Every closed list MUST include an escape value (`unclear`, `other` or `unknown`).
- Every extracted field MUST be able to state `not_present`.
- Every extracted value MUST carry the exact text it was copied from.
- A schema guarantees shape only. Value correctness MUST be checked separately (Principle IV).

### III. Untrusted Input Cannot Act

- Uploaded documents are untrusted.
- A step that reads document content MUST hold no tools, or only read-only tools.
- Only harness code MAY perform writes, such as recording a decision, an audit event or a submission.
- Every value that a model proposes MUST pass validation in code before it is used.
- Every write MUST carry an idempotency key.

### IV. Code Enforces Rules and Verifies Outcomes

- Business rules (expiry, formats, ownership, legal form, activity risk, grounding, cross-checks) MUST be plain code, never instructions to a model.
- A run is done only when stored state proves it. What a model says it did is never evidence.
- Guardrails MUST NOT block the path to human review.

### V. A Person Approves Every Submission

- No submission happens without a signed-in person approving the current form version.
- An approval applies to one exact form version.
- Every approval, correction, rejection and submission MUST write an audit event that names the person.
- Every correction MUST become a regression case.

### VI. Outcome-Based Tests Before Code (NON-NEGOTIABLE)

- Work proceeds spec → tests → code. A task is done when its acceptance scenarios pass.
- Tests MUST assert outcomes: the route, field values, form contents, whether and how many submissions exist, and audit contents.
- Tests MUST NOT assert internal function names, call order, prompt text or exact message wording.
- Test cases MUST be value-driven tables (input → expected outcome), plus property-based tests where a rule holds over a range.
- Test names describe behaviour.
- Tests use a fixed clock. Unit and graph tests MUST run without network access.

### VII. Evidence-Based Confidence, Measured by Evals

- Field confidence MUST combine checkable signals. A model's self-rating MAY add only a small weight.
- Thresholds MUST be calibrated on labelled cases.
- Any change to prompts, models, rules or thresholds MUST be measured with the eval suite. Graders read final state.
- The README reports measured results, including results that miss a target.

### VIII. Personal Data Protection

- Files and extracted personal data MUST be encrypted at rest.
- Logs, traces and trace API responses MUST mask personal data.
- Stored data MUST be deleted after a configured retention period.
- Masking MUST NOT alter the input to extraction.

### IX. Plain Interface Language (ASD-STE100)

- All interface text follows ASD-STE100 Simplified Technical English:
  - at most 20 words in an instruction and 25 in a description
  - one instruction per sentence
  - active voice
  - one word per meaning
  - no filler words or exclamation marks
- All strings live in one copy file, and a lint check enforces the rules.

### X. Simplicity

- Build only what an acceptance scenario needs.
- Prefer deterministic code to a model call, and one model to a cascade of models, unless an eval shows a gain.
- Do not describe scope with version numbers or with "MVP". Order work by user-story priority (P1, P2 and so on). Spec Kit's structural headings (Setup, Foundation, Polish) are allowed. Release versions follow the Branching and Releases section.

## Technology Constraints

- **Backend:** Python 3.12, LangGraph for orchestration, Pydantic, FastAPI, SQLite.
- **Model calls:** every call goes through one injectable client (`LLMClient`).
  - Claude through the official `anthropic` SDK is the default provider.
  - Other providers, including an open-weight model on the developer's machine, are allowed only through the OpenAI-compatible transport. They are chosen by configuration (model profiles), never by code changes in the nodes ([ADR-004](../../docs/decisions/ADR-004-provider-neutral-model-calls.md), FR-044).
  - Every eval report MUST name the models it measured. Numbers from one model are never reported as another model's.
- **Frontend:** React 19, Vite, TypeScript and the Astryx design system. API types are generated from the backend's OpenAPI schema.
- **Data:** only synthetic documents, plus one public licence that is downloaded at eval time and never committed. Real private documents are not permitted in the repository.

## Branching and Releases (GitFlow)

- The repository MUST follow GitFlow:
  - `main` holds tagged releases only.
  - `develop` is the integration branch.
  - Work happens on `feature/<NNN>-<name>` branches, created from `develop`. `<NNN>` matches the Spec Kit folder under `specs/`.
  - Specification work uses `feature/<NNN>-<name>`. Every later unit of work uses its own branch, `feature/<NNN>-<name>-<slug>`, where `<slug>` is `foundation`, `us<N>` (one user story) or `polish`.
  - Releases are stabilised on `release/<x.y.z>`.
  - Urgent fixes to a release use `hotfix/<x.y.z>`, created from `main`.
- Every change MUST reach `main` or `develop` through a pull request that passes the required checks.
  - A release or hotfix takes two pull requests: one into `main`, then a back-merge into `develop`.
  - Direct pushes, force pushes and branch deletion on `main` and `develop` are forbidden.
- Human review:
  - While the repository has one maintainer, required checks replace the approval rule. CODEOWNERS only requests reviewers; it is not a merge requirement.
  - Required approval rises to 1 as soon as a second maintainer joins.
- Commit messages and pull request titles MUST follow Conventional Commits.
- Releases MUST use:
  - Semantic Versioning
  - an annotated, signed tag `vX.Y.Z`
  - a Keep a Changelog entry
  - a linked eval report
- Versions label releases only. Scope and priority are never described by version numbers (Principle X).

## Engineering Standards

These standards are non-negotiable. The detail, tooling and sources are in `docs/engineering-practices.md`.

- **Quality:**
  - strict linting and formatting
  - `mypy --strict` for Python and `strict` TypeScript
  - lock files that CI installs exactly
  - typed settings from the environment
  - no secrets in code or config
- **CI gate before a merge** (the same list as docs/engineering-practices.md, section 4):
  - lint and format
  - type checks
  - backend offline tests
  - at least 90% line coverage on the deterministic core
  - frontend tests and build
  - OpenAPI type freshness
  - the copy check
  - a secret scan
  - a dependency audit
  - a Conventional Commit pull request title
- **Release gate:** the eval report meets the spec's success criteria, or the README states each gap and its reason.
- **Security:**
  - controls mapped to the OWASP Top 10 for LLM Applications
  - GitHub Actions pinned to commit SHAs, with least-privilege tokens
  - Dependabot
  - container images pinned by digest and run as a non-root user
  - an SBOM and build provenance on each release
  - `SECURITY.md` and `CODEOWNERS`
- **LLM engineering:**
  - Model IDs and prompts are versioned in files.
  - Every model call records its prompt hash, tokens and cost.
  - Every change that affects model behaviour ships with before and after eval numbers.
- **Documentation:**
  - ADRs for architecture decisions. An ADR becomes immutable once it merges to `develop`; after that, a new ADR supersedes it.
  - Spec Kit artifacts as the source of truth for each feature, updated in the same PR as the behaviour change
  - Mermaid diagrams
  - README, CONTRIBUTING, CHANGELOG, SECURITY and LICENSE files kept current

## Development Workflow

- Every feature uses the Spec Kit sequence: specify → clarify → plan → tasks → analyze → implement.
- The plan MUST pass the Constitution Check before research and again after design.
- Each user story is implemented and verified on its own. Stories start in priority order, and stories whose dependencies are met may run in parallel on separate branches.
- Each user story ends with a local visual check: its quickstart rows are run in a browser against the local demo (`make dev`), every defect found is fixed with a regression test, and screenshots of synthetic data are attached to the pull request.
- CI runs lint, the copy check and all offline tests. The eval suite runs on demand, because it uses the paid API.

## Governance

- This constitution overrides other practices in this repository.
- An amendment requires an edit to this file with a Sync Impact Report, a version change, and updates to every dependent template and document.
- Versioning follows semantic rules:
  - MAJOR: a principle is removed or redefined.
  - MINOR: a principle or section is added.
  - PATCH: wording only.
- Every plan and review MUST check compliance. A violation is allowed only with a written justification in the plan's Complexity Tracking table.

**Version**: 2.2.0 | **Ratified**: 2026-11-21 | **Last Amended**: 2026-11-22
