# Contributing

## Workflow: Spec Kit and GitFlow

1. **Specify before you build.** New behaviour goes through Spec Kit: `speckit-specify`,
   `speckit-clarify`, `speckit-plan`, `speckit-tasks`, `speckit-analyze`, then
   `speckit-implement`. The rules are in the [constitution](.specify/memory/constitution.md).
2. **Branch from an updated `develop`:**
   ```bash
   git switch develop && git pull
   git switch -c feature/<NNN>-<name>-<slug>   # slug: foundation, us<N> or polish
   ```
3. **Tests first.** Write the tests from the acceptance scenarios and
   [test cases](specs/001-licence-to-kyb/test-cases.md), see them fail, then write the code.
   Tests assert outcomes and codes, never wording or internals.
4. **Open a pull request into `develop`.** Feature branches squash-merge. Releases go through
   `release/x.y.z` into `main`, then a back-merge into `develop`, each by pull request.

## Commits

- [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):
  `feat(rules): add QR mismatch check`. Types: feat, fix, docs, test, refactor, perf,
  build, ci, chore, style, revert, eval.
- Signed commits (SSH or GPG). Branch protection requires them.

## Local setup and checks

```bash
make setup          # uv sync, npm ci, pre-commit hooks, Tesseract data
make data           # synthetic licences and labelled cases (deterministic)
make lint           # ruff, mypy --strict, eslint, tsc, prettier, copy check
make test           # offline backend, eval-harness and frontend tests
```

`make eval` calls the paid model API. Run it only when a change affects model behaviour, and
attach the report to the pull request.

## Data rules

Never commit real documents or personal data. Use `make data` for test documents. The one
public licence is fetched at eval time and is gitignored.

## Dependency note

`frontend/package.json` overrides `@babel/plugin-transform-runtime`. It resolves an
optional-peer conflict between `@vitejs/plugin-react` and `@astryxdesign/cli`; neither
package is installed. Remove the override when either upstream changes.
