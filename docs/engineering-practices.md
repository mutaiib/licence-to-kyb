# Engineering practices

These are the standards that every change to this repository follows. The [constitution](../.specify/memory/constitution.md) holds the non-negotiable rules. This document gives the detail, the tooling and the sources.

Each practice is listed with how it is enforced. A practice that nothing enforces is a wish, not a standard.

---

## 1. Branching and releases: GitFlow

| Branch | Created from | Merges into | Purpose |
|---|---|---|---|
| `main` | — | — | Released code only. Every commit on `main` is a tagged release. |
| `develop` | `main` (once) | — | Integration branch for the next release. |
| `feature/<NNN>-<name>` | `develop` | `develop` | Specification work for one Spec Kit feature, for example `feature/001-licence-to-kyb`. |
| `feature/<NNN>-<name>-<slug>` | `develop` | `develop` | One unit of work for that feature. `<slug>` is `foundation`, `us<N>` (one user story), `polish`, or a short maintenance slug such as `ci-docker`, for example `feature/001-licence-to-kyb-us2`. |
| `release/<x.y.z>` | `develop` | `main` (pull request), then back-merged into `develop` (pull request) | Stabilisation only: version bump, changelog, eval report, fixes. No new features. |
| `hotfix/<x.y.z>` | `main` | `main` (pull request), then back-merged into `develop` (pull request) | An urgent fix to a released version. |

**Rules:**
- **Every merge is a pull request.** Nobody pushes directly to `main` or `develop`. A release or hotfix takes two pull requests: one into `main`, then a back-merge into `develop`.
- **One branch per unit of work.** A squash-merged branch is never reused. The next story starts from an updated `develop`.
- **Merge style:**
  - Feature branches squash-merge into `develop`, with a Conventional Commit title.
  - Release, hotfix and back-merge pull requests use a merge commit, so the history shows each release.
  - There is no linear-history rule on `develop`, because back-merges are merge commits.
- **Tags:** a release is tagged `vX.Y.Z` on `main` with an annotated, signed tag.
- **Spec Kit:**
  - Run `git switch develop && git pull` before you create a branch, because the branch hook branches from the current HEAD.
  - Then run the `speckit-git-feature` hook with `GIT_BRANCH_NAME=feature/<NNN>-<name>[-<slug>]`.
  - Spec Kit strips the `feature/` prefix when it validates the branch, and reads the feature folder from `.specify/feature.json`.
- **Branch protection (GitHub rulesets) on `main` and `develop`:**
  - pull request required
  - the required status checks in section 4
  - signed commits
  - no force pushes
  - no deletion
- **Approvals:**
  - While the repository has one maintainer, required approvals are 0, because GitHub does not let an author approve their own pull request. The required checks are the gate.
  - CODEOWNERS only requests reviewers automatically. "Require review from code owners" stays off until a second maintainer joins.
  - Required approvals rise to 1 when a second maintainer joins.

**Why GitFlow here:** releases are explicit and versioned, and the eval report is published per release. GitFlow gives each release a branch where the measured numbers are frozen before tagging.

## 2. Commits, versions and changelog

- **Commit messages: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).**
  - Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `eval`.
  - The scope is the component, for example `feat(rules): add QR mismatch check`.
  - A breaking change uses `!` or a `BREAKING CHANGE:` footer.
  - Enforced by `commitlint` in a `commit-msg` hook and on the PR title in CI.
- **Versioning: [Semantic Versioning 2.0.0](https://semver.org/).**
  - MAJOR: an API contract or schema change that breaks clients.
  - MINOR: a new capability.
  - PATCH: a fix.
- **Changelog: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)** format in `CHANGELOG.md`.
  - It is updated on every release branch.
  - Each release entry links its eval report.
- **Signed commits:** SSH or GPG signing, required by branch protection.

## 3. Code quality

| Area | Standard | Enforced by |
|---|---|---|
| Python style and lint | `ruff format`, plus `ruff check` with a strict rule set (pyflakes, pycodestyle, isort, bugbear, pyupgrade, simplify, bandit-style security rules) | pre-commit, CI |
| Python types | `mypy --strict` on `backend/src`. No untyped definitions, and no `Any` at public boundaries. | CI |
| TypeScript | `strict: true`, `noUncheckedIndexedAccess`, ESLint and Prettier | pre-commit, CI |
| Dependencies | `uv.lock` and `package-lock.json` are committed. CI installs from the lock files only. Dependabot pull requests are reviewed like any other: a runtime major version (Python, Node) is a planned change, recorded as an ignore rule with its reason in `.github/dependabot.yml`. | CI (`uv sync --frozen`, `npm ci`), Docker build job |
| Docstrings | Public modules and functions state their contract: inputs, outputs, failure behaviour | review |
| Complexity | A function with more than about 40 lines or a cyclomatic complexity above 10 needs a reason in review | ruff `C901`, review |
| Configuration | [Twelve-Factor](https://12factor.net/config) style. Settings come from environment variables, validated by a typed settings model. No secrets in the code or in config files. | settings validation at startup |
| Errors | Typed exceptions at each boundary. No bare `except`. User-facing errors follow the [UI copy](ui-copy.md) rules. | ruff, review |

## 4. Testing and the CI gate

The constitution's Principle VI applies: tests assert outcomes and values, never names or strings.

| Layer | Tooling | Runs |
|---|---|---|
| Unit: schemas, rules, mapping, confidence, gate | `pytest`, `hypothesis` | every push |
| Graph: end-to-end with recorded model responses | `pytest`, recorded fixtures | every push |
| API | `pytest` with the FastAPI test client | every push |
| Frontend | Vitest and Testing Library | every push |
| Browser | chrome-devtools-axi against the running stack | release branches |
| Evals: real API, labelled cases | `evals/run.py` | manual workflow dispatch, and every release branch |

**Required status checks before a merge:**
1. lint and format
2. type checks
3. unit, graph and API tests
4. coverage of at least 90% lines on `rules/`, `nodes/confidence.py`, `nodes/gate.py` and `nodes/map_form.py`, the deterministic core
5. frontend tests and build
6. the OpenAPI types are up to date
7. the UI copy check
8. secret scan
9. dependency audit
10. Conventional Commit PR title

**Eval gate for releases.** A release branch merges only if its eval report meets the targets in the spec, or the README states the gap and the reason. Regressions against the previous release report are listed in the PR.

**Mutation testing.** `mutmut` runs on `rules/` once per release, to show that the rule tests detect changes in behaviour.

## 5. Security

### Application security for an LLM system

The controls are mapped to the [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/):

| Risk | Control in this project |
|---|---|
| LLM01 Prompt injection | The steps that read the document have no tools, or read-only tools. Writes exist only in code. Injected-text cases in the eval set must have the same outcome as their clean twins. |
| LLM02 Sensitive information disclosure | Personal data is encrypted at rest and masked in logs, traces and trace API responses, with a retention period. Prompts contain no secrets. |
| LLM03 Supply chain | Lock files, a dependency audit, pinned GitHub Actions and Docker base image digests, Dependabot, and an SBOM per release. |
| LLM04 Data and model poisoning | No fine-tuning and no shared memory. Captured cases are reviewed before they join the eval set. |
| LLM05 Improper output handling | Every model output is schema-validated and then checked by rules. Model text is never executed. It is rendered as plain text in the UI. |
| LLM06 Excessive agency | One agent, with read-only tools, a field scope and hard budgets. A person approves every submission. |
| LLM07 System prompt leakage | Prompts hold no secrets or authority. Every control is in code, so a leaked prompt grants nothing. |
| LLM08 Vector and embedding weaknesses | Not applicable: no retrieval store. |
| LLM09 Misinformation | Grounding checks against the OCR text, two-pass agreement, calibrated confidence, and human review of flagged fields. |
| LLM10 Unbounded consumption | Per-run step, token and time limits, a daily token cap, file size and page limits, and duplicate detection. |

The OWASP GenAI project also publishes a newer edition of the list. When a release adopts it, this table is reviewed against that edition.

### Web application and data security

- **Authentication:**
  - Reviewer accounts come from configuration, with argon2id password hashes. Each reviewer has their own identity; no shared account.
  - Session cookies are `HttpOnly`, `Secure` and `SameSite=Strict`, with an 8-hour expiry and an explicit logout.
- **Login:** after more than 5 failed attempts in 1 minute for an account or an IP, the API returns `429`.
- **CSRF:** a double-submit token is required on every state-changing request.
- **Encryption keys:** Fernet keys come from the environment, never from files in the repository. `MultiFernet` supports rotation: new data uses the first key, and old data still decrypts with the older keys.
- **Upload hardening:**
  - The type is read from the file's magic bytes.
  - Limits: 10 MB, 5 pages, at most 50 megapixels per rendered page, and a PDF page-size cap. These stop decompression bombs.
  - Rendering runs with a time limit.
- **QR payloads are untrusted input.** They are parsed as data, validated against the authority's number pattern, and never fetched or opened as a URL.
- **External processing:** page images and text are sent to the model provider's API.
  - For production use, this needs a data processing agreement, a provider retention setting that fits the retention policy, and a check of data residency.
  - The demo uses only synthetic and public documents.

### Repository and pipeline security

Checks follow the [OpenSSF Scorecard](https://securityscorecards.dev):

- **Branch protection:** as in section 1.
- **GitHub Actions:**
  - Actions are pinned to full commit SHAs.
  - The default `GITHUB_TOKEN` permission is `contents: read`, raised per job only where needed.
  - Workflows never run `pull_request_target` on untrusted code.
- **Secrets:**
  - `gitleaks` runs in pre-commit and CI.
  - The model API key exists only as an Actions secret for the eval workflow, scoped to that environment.
- **Dependencies:**
  - Dependabot covers pip, npm, GitHub Actions and Docker.
  - `pip-audit` and `npm audit --audit-level=high` run in CI.
- **Containers:**
  - Multi-stage builds, base images pinned by digest, a non-root user and a read-only filesystem where possible.
  - A health check on each service.
- **Releases:**
  - Annotated signed tags.
  - An SBOM (CycloneDX) attached to each GitHub release.
  - Build provenance through GitHub artifact attestations.
- **Policy files:**
  - `SECURITY.md` describes how to report a vulnerability.
  - `CODEOWNERS` covers `rules/`, `security.py` and the workflows.

## 6. LLM engineering

| Practice | Implementation |
|---|---|
| Model pinning | The model ID and effort per step are in `config/models.yaml`. A change is a PR with an eval report. |
| Prompt versioning | Prompts are files in `llm/prompts/`. Every model-call span records the prompt hash, and the eval report lists the hashes used. |
| Deterministic tests | Unit and graph tests replay recorded responses. A missing recording fails the test, and the test never calls the network. |
| Evaluation as the change gate | Every change to prompts, models, rules, thresholds or tools includes before and after eval numbers in the PR. |
| Calibration | Thresholds are refitted when prompts or models change, and the fit is committed with the report. |
| Cost visibility | Every span records its tokens and cost. The run list and the eval report show the cost per document. |
| Failure handling | Refusal and `max_tokens` stop reasons, typed SDK errors, SDK retries for temporary errors, and a fallback model setting. |
| Tool design | Descriptions state what, when, when not, and failure. Strict schemas use fixed lists. Results are written in words. |
| Tool errors | Every failed call returns a structured, model-directing error: `error_code`, `what_failed`, `why`, `state`, `retryable`, `next_action`, `allowed` and `message`. Code retries temporary failures first. A failure never ends the run. Errors are counted by code in the eval report, and tested by structure. |
| Fallback awareness | Every span records the model that actually served the call. If a fallback model served an extract call, the run cannot be `ready`, because the thresholds were calibrated on the primary model. Recorded fixtures store the serving model. |
| Operational signals | `GET /api/metrics/summary` reports refusal rate, fallback rate, review rate, cost per day and the remaining daily cap. The eval report shows the same rates. |
| Observability | Spans follow the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) for attribute names, so a later export to an OpenTelemetry backend needs no renaming. |

## 7. Documentation

- **Architecture decisions** are recorded as ADRs in `docs/decisions/`, in [Michael Nygard's format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions): context, decision, reasons, consequences. An ADR becomes immutable once it merges to `develop`. After that, a new ADR supersedes it.
- **Spec Kit artifacts** under `specs/<NNN>-<name>/` are the source of truth for each feature's requirements, plan, contracts and tasks. Code changes that alter behaviour update the spec in the same PR.
- **Diagrams** are Mermaid in Markdown, so they render on GitHub and change in review like code.
- **Repository files:**
  - `README.md` (purpose, how to run it, measured results)
  - `CONTRIBUTING.md` (workflow, commit rules, how to run checks)
  - `CHANGELOG.md`
  - `SECURITY.md`
  - `LICENSE` (MIT)
  - `CODEOWNERS`
  - pull request and issue templates

## 8. Pull requests and review

- **The PR template asks for:**
  - the linked spec and tasks
  - what changed and why
  - the test evidence
  - eval numbers, for model-affecting changes
  - the design worksheet rows that changed (see the [design worksheet](design-worksheet.md))
  - screenshots, for UI changes
- **Review checks, following [Google's code review guidance](https://google.github.io/eng-practices/review/):**
  - design
  - functionality
  - complexity
  - tests
  - naming
  - comments
  - documentation
  - compliance with the constitution
- **Size:** a PR stays small enough to review in one sitting. A large feature is split along its user stories.

## 9. Operations

- **Health:** `/healthz` (process up) and `/readyz` (database and checkpointer reachable).
- **Logs:** structured JSON logs, with the run ID on every line and personal data masked.
- **Retention:** a daily job deletes runs, files and personal data older than the retention period. It writes a count to the log.
- **Backups:** the SQLite databases are copied on release and before each migration.
- **Schema migrations:** they are versioned, forward-only, and tested on a copy of the previous release's database.
