# Quickstart: Trade Licence to KYB Onboarding Form

How to run the system and check each user story by hand. Commands are run from the repository root.

## Prerequisites

- Docker with Compose, **or**:
  - Python 3.12 and `uv`
  - Node 22
  - Tesseract with the `eng` and `ara` language packs
- An Anthropic API key. It is needed only for live runs and evals. Offline tests do not need it.

## Set up

```bash
cp .env.example .env              # set ANTHROPIC_API_KEY, FERNET_KEYS, REVIEWER_ACCOUNTS (argon2id hashes), DAILY_TOKEN_BUDGET
make setup                        # uv sync --frozen; npm ci; pre-commit install
make data                         # generate synthetic licences and ground truth (fixed seed)
```

## Run the checks

```bash
make lint                         # ruff, mypy --strict, eslint, tsc, copy check, gitleaks
make test                         # unit, graph and API tests, offline, with a fixed clock
make eval                         # live: every labelled case, report in evals/reports/
```

## Run the app

```bash
make demo                         # docker compose up; UI on http://localhost:5173, API on :8000
```

## Check each story

| Story | Steps | Expected result |
|---|---|---|
| US1 | Upload `data/generated/clean_001.pdf` with the business name from its ground truth. | The form shows every value from `det_clean_001.json`, each with its evidence text. |
| US1 | Upload `data/generated/injected_001.pdf`. | Same values and route as `det_clean_001`. |
| US2 | Upload `data/generated/near_expiry_001.pdf`. Correct the expiry date, approve, and submit. | One submission, marked as verified. The audit shows the correction and the reviewer. |
| US2 | Click Submit again. | Same submission ID. No second submission. |
| US2 | Stop the stack while a run waits for review, start it again, and open the run. | Same flagged fields. |
| US3 | Upload `data/generated/expired_001.pdf` (expiry corroborated). | Route "reject", reason code `expired`. |
| US3 | Upload `data/generated/expired_uncertain_001.pdf`. | Route "needs review", reason code `expiry_uncertain`. |
| Providers | `make local-model`, then `MODEL_PROFILE=local make dev`. Upload `data/generated/clean_001.pdf`. | The run finishes with real readings from the local model; the trace names the local model; the cost is 0. |
| US2 | Reopen the rejected run with a reason. | Status "awaiting review". The audit shows the reopen event and its reason. |
| US4 | Upload `data/generated/scans_003.jpg`. | The trace shows a resolver span, and the expiry date matches the ground truth. |
| US5 | Open a trace and the daily summary, and search each page for an owner's name. | The name is masked. The summary shows the refusal, fallback and review rates. |
| US6 | Run `make eval`, change one threshold, then run `make eval-compare`. | The comparison lists only the cases whose route changed. |

## Branching

Work follows GitFlow (see `docs/engineering-practices.md`).
- The specification is on `feature/001-licence-to-kyb`.
- Setup and Foundation are on `feature/001-licence-to-kyb-foundation`, each user story on `feature/001-licence-to-kyb-us<N>`, and Polish on `feature/001-licence-to-kyb-polish`.
- Every branch is created from an updated `develop`.
- Each branch merges to `develop` by pull request.
