# Eval report: local-public

- Date: 2026-11-22T12:14:42+00:00
- Model profile: local
- Model, route: local-model
- Model, extract_primary: local-model
- Model, extract_secondary: local-model
- Model, resolve: local-model
- Resolver: on
- Split: test (1 cases, 0 errors)

| Metric | Value |
|---|---|
| Route accuracy | 100.0% |
| Reason-code accuracy | 100.0% |
| `ready` precision (critical fields) | 0/0, Wilson 95% [0.0, 1.0] |
| Review rate, realistic mix | 100.0% |
| Cost per document | $0.0000 |
| `max_tokens` stops | 0 of 6 calls |
| Safety violations | 0 |

| Field | Accuracy |
|---|---|
| activities | 0.0% |
| chamber_number | 0.0% |
| establishment_date | 0.0% |
| expiry_date | 100.0% |
| issue_date | 100.0% |
| issuing_authority | 100.0% |
| legal_form | 100.0% |
| licence_number | 100.0% |
| people | 0.0% |
| trade_name_en | 100.0% |

| Stage | p95 | Budget |
|---|---|---|
| preprocess | 212 ms | 8000 ms |
| route | 77085 ms | 4000 ms |
| extract | 1446177 ms | 18000 ms |
| validate | 2 ms | 1000 ms |
| resolve | 54020 ms | 45000 ms |
