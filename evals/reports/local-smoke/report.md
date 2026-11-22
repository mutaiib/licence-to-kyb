# Eval report: local-smoke

- Date: 2026-11-22T11:47:50+00:00
- Model profile: local
- Model, route: local-model
- Model, extract_primary: local-model
- Model, extract_secondary: local-model
- Model, resolve: local-model
- Resolver: on
- Split: test (1 cases, 0 errors)

| Metric | Value |
|---|---|
| Route accuracy | 0.0% |
| Reason-code accuracy | 100.0% |
| `ready` precision (critical fields) | 0/0, Wilson 95% [0.0, 1.0] |
| Review rate, realistic mix | 100.0% |
| Cost per document | $0.0000 |
| `max_tokens` stops | 0 of 5 calls |
| Safety violations | 0 |

| Field | Accuracy |
|---|---|
| activities | 0.0% |
| address | 100.0% |
| chamber_number | 100.0% |
| establishment_date | 100.0% |
| expiry_date | 100.0% |
| issue_date | 100.0% |
| issuing_authority | 0.0% |
| legal_form | 100.0% |
| licence_number | 100.0% |
| people | 100.0% |
| trade_name_ar | 0.0% |
| trade_name_en | 100.0% |

| Stage | p95 | Budget |
|---|---|---|
| preprocess | 305 ms | 8000 ms |
| route | 47407 ms | 4000 ms |
| extract | 2924785 ms | 18000 ms |
| validate | 0 ms | 1000 ms |
| resolve | 0 ms | 45000 ms |
