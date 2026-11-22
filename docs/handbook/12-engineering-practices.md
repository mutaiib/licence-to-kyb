# 12 — Engineering practices

## In one minute

A repository looks mature when its standards are **enforced**: branch rules, a CI gate, pinned dependencies, security checks, recorded decisions and honest release notes. A standard that nothing enforces is a wish.

## Rules

### Branching: GitFlow

- `main` holds releases only. `develop` integrates them.
- Work happens on `feature/<NNN>-<name>-<slug>`, created from an updated `develop`. The slug is `foundation`, `us<N>` or `polish`.
- Releases are stabilised on `release/x.y.z`, and urgent fixes go on `hotfix/x.y.z`.
- Every merge is a pull request.
  - A release takes two: one into `main`, then a back-merge into `develop`.
  - Feature branches squash-merge. Release branches use merge commits, so `develop` has no linear-history rule.
- With a single maintainer, required checks are the gate, because GitHub does not let authors approve their own pull requests. CODEOWNERS only requests reviewers.

### Commits and releases

- Conventional Commits, checked by `scripts/check_commit_msg.py` (commit-msg hook) and on the pull-request title in CI.
- Semantic Versioning, with annotated, signed tags.
- A Keep a Changelog entry that links the eval report.

### The CI gate

- lint and types: `ruff`, `mypy --strict`, strict TypeScript
- offline tests, with ≥ 90% coverage on the deterministic core
- frontend tests and build
- OpenAPI type freshness
- the copy check
- the secret scan
- the dependency audit
- the pull request title check

### Supply chain

- Actions are pinned to commit SHAs, with least-privilege tokens.
- Lock files are committed, and CI installs from them exactly.
- Dependabot keeps dependencies current.
- Base images are pinned by digest, and containers run as a non-root user.
- Each release ships an SBOM and an artifact attestation.

### Decisions and documentation

- ADRs become immutable once merged. A new ADR supersedes an old one.
- Diagrams are Mermaid, so they change in review like code.
- The README reports measured results, including any target that was missed.

### LLM-specific practice

- Model IDs and prompts live in versioned files.
- Every call records its prompt hash.
- Any change that affects model behaviour ships with eval numbers from before and after.

## In this repository

- **The rules:** [constitution](../../.specify/memory/constitution.md), Branching and Engineering Standards sections.
- **The detail, tooling and sources:** [engineering practices](../engineering-practices.md).
- **The setup tasks that enforce it:** T001 to T011 ([tasks](../../specs/001-licence-to-kyb/tasks.md)).

## Mistakes to avoid

- **A rule that cannot hold with your process.** Found in review: linear history on `develop` conflicted with `--no-ff` back-merges.
- **Required approval with one maintainer.** Every merge would have been blocked.
- **Reusing a squash-merged branch.** It causes conflicts. Use one branch per unit of work.
- **Long lists of practices with no enforcement.** Each item here has a check, a file or a task.

## Self-check

<details><summary>1. How does a release reach `main` under GitFlow here?</summary>

1. Cut `release/x.y.z` from `develop`.
2. Stabilise it: version, changelog, eval report.
3. Merge it into `main` by pull request, and tag `vX.Y.Z` (signed).
4. Back-merge into `develop` by a second pull request.
</details>

<details><summary>2. Why pin GitHub Actions to commit SHAs instead of version tags?</summary>

A tag can be moved to point at different code. A SHA cannot. Pinning protects the pipeline, and the secrets it holds, from a compromised action release.
</details>

<details><summary>3. What should a pull request that changes a prompt contain?</summary>

- the linked spec and task
- the test evidence
- eval numbers before and after, including the list of changed cases
- cost and latency effects
- any design worksheet rows the change touches
</details>
