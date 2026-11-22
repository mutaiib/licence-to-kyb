# Eval report: scripted-baseline

- Date: 2026-11-22T14:58:34+00:00
- Model profile: scripted
- Model, all steps: scripted (labels): checks routing and rules, not reading
- Resolver: on
- Split: test (50 cases, 0 errors)

| Metric | Value |
|---|---|
| Route accuracy | 100.0% |
| Reason-code accuracy | 100.0% |
| `ready` precision (critical fields) | 14/14, Wilson 95% [0.7847, 1.0] |
| Review rate, realistic mix | 27.7% |
| Cost per document | $0.0000 |
| Processing time per document, p95 | 2439 ms |
| `max_tokens` stops | 0 of 300 calls |
| Bad documents routed `ready` (SC-004) | 0 |
| Submits without approval (none happen before the first pause) | 0 |
| Runs stopped in processing | 0 |

| Field | Accuracy |
|---|---|
| activities | 100.0% |
| address | 100.0% |
| chamber_number | 100.0% |
| establishment_date | 100.0% |
| expiry_date | 100.0% |
| issue_date | 100.0% |
| issuing_authority | 100.0% |
| legal_form | 100.0% |
| licence_number | 100.0% |
| people | 100.0% |
| trade_name_ar | 100.0% |
| trade_name_en | 100.0% |

| Stage | p95 | Budget |
|---|---|---|
| preprocess | 2419 ms | 8000 ms |
| route | 3 ms | 4000 ms |
| extract | 8 ms | 18000 ms |
| validate | 3 ms | 1000 ms |
| resolve | 24 ms | 45000 ms |
