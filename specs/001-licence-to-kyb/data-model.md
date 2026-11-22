# Data Model: Trade Licence to KYB Onboarding Form

The types are Pydantic models in `backend/src/licence_kyb/schemas/`.
- **PII** marks fields that are encrypted at rest and masked in logs, traces and trace API responses.
- **Every closed list has an escape value** (`unclear`, `other` or `unknown`), as Constitution Principle II requires.

## Field[T]

The wrapper for every extracted value, list fields included.

| Attribute | Type | Rule |
|---|---|---|
| `value` | `T \| None` | `None` when `status != present` |
| `status` | `present \| not_present \| unclear` | Required. |
| `origin` | `read \| entered_by_reviewer` | `entered_by_reviewer` skips the evidence check only (FR-024). |
| `evidence_quote` | `str \| None` | Required when `status = present` and `origin = read`. Exact text from the document. |
| `page` | `int \| None` | 1 to 5. Required with `evidence_quote`. |
| `self_confidence` | `high \| medium \| low \| unknown` | Required. Has a small weight in scoring. |

## RouteResult

| Attribute | Type |
|---|---|
| `doc_type` | `trade_licence \| moa \| emirates_id \| passport \| other \| unclear` |
| `authority` | `DET \| ADDED \| DMCC \| IFZA \| other \| unknown` |
| `has_arabic` | `true \| false \| unknown` |

**Code rules applied after the model call:**
- If the licence number in the OCR text matches the pattern of a different authority, `authority` becomes `unknown`.
- `moa`, `emirates_id`, `passport` and `other` go to `reject` with reason code `out_of_scope` **only when code corroborates the label**: the OCR text contains no **labelled** licence number and no licence title ("Trade Licence", "Commercial Licence", "رخصة"). A licence number counts as labelled when an authority pattern matches as a whole token on the same line as, and within 40 characters of, a licence-number label ("Licence No", "License No", "رقم الرخصة"). Digit runs inside other identifiers, such as an Emirates ID (784-YYYY-NNNNNNN-N), do not count. Otherwise they go to `needs_review` with `unclear_document`.
- `unclear` goes to `needs_review` with reason code `unclear_document` (FR-006).

## TradeLicenceExtraction

| Attribute | Type | PII | Notes |
|---|---|---|---|
| `licence_number` | `Field[str]` | yes | critical |
| `unified_licence_number` | `Field[str]` | yes | |
| `register_number` | `Field[str]` | yes | |
| `chamber_number` | `Field[str]` | | |
| `trade_name_en` | `Field[str]` | | critical |
| `trade_name_ar` | `Field[str]` | | critical |
| `legal_form` | `Field[LegalForm]` | | critical. `LegalForm` is one of `llc`, `llc_single_owner`, `sole_establishment`, `civil_company`, `branch`, `fze`, `fzco`, `fz_llc`, `public_joint_stock`, `private_joint_stock` or `other` |
| `licence_category` | `Field[commercial \| professional \| industrial \| tourism \| other]` | | |
| `licence_type` | `Field[str]` | | |
| `issuing_authority` | `Field[str]` | | |
| `establishment_date` | `Field[date]` | | parsed from DD/MM/YYYY |
| `issue_date` | `Field[date]` | | |
| `expiry_date` | `Field[date]` | | critical |
| `activities` | `Field[list[Activity]]` | | `Activity{code: Field[str], description_en: Field[str], description_ar: Field[str]}` |
| `people` | `Field[list[Person]]` | yes | critical. `Person{name: Field[str], nationality: Field[str], role: Field[owner \| partner \| manager \| shareholder \| representative \| other], share_pct: Field[float]}` |
| `address` | `Field[str]` | yes | |

**Validation inside the model:**
- `0 <= share_pct <= 100`.
- Every `Field` obeys its own rules.
- **An unreadable owners table is `people.status = unclear`, never an empty list.**

Date order (`issue_date < expiry_date`, `establishment_date <= issue_date`) is not checked inside the model. It is the `date_order` business rule, so a licence with dates in the wrong order reaches a reviewer with that reason code instead of failing validation.

## ExtractionPasses

| Attribute | Type |
|---|---|
| `primary` | `TradeLicenceExtraction` |
| `secondary` | `CriticalFields` (the critical fields only, from an independent pass) |
| `agreement` | `dict[field_path, bool]`. List fields are compared element by element after normalisation. |
| `serving_models` | `list[str]`, the models that served the calls |

## RuleResult

| Attribute | Type |
|---|---|
| `rule_id` | `str` |
| `fields` | `list[field_path]`. Never empty unless `outcome` is `passed` or `not_applicable`. |
| `severity` | `block \| warn` |
| `outcome` | `passed \| failed \| could_not_run \| not_applicable` |
| `reason_code` | `ReasonCode \| None` |
| `overridable` | `bool`. True only when `outcome = could_not_run`. |

**Effect on the route:**
- `could_not_run` counts as failed for routing, until a reviewer overrides it.
- `not_applicable` never counts as failed.

## Error codes (API)

`ErrorCode` is the closed list of codes in API error bodies. The UI maps each one to one string in `copy.ts`.

| Status | Codes |
|---|---|
| 401 | `invalid_credentials` (sign-in), `session_expired` |
| 403 | `forbidden` (CSRF) |
| 404 | `not_found` (no such run or page) |
| 409 | `blocking_rule_failed`, `not_overridable`, `undecided_fields`, `stale_version`, `reason_required`, `not_approved`, `not_awaiting_submit`, `not_rejected`, `not_retryable`, `no_form` |
| 422 | the file reason codes (`reason_code`): `invalid_type`, `too_large`, `too_many_pages`, `image_too_large`, `unreadable_file`; or `invalid_request` (`code`) when a request field is missing or out of range |
| 429 | `rate_limited` |

`network` is client-side only: the UI uses it when the server cannot be reached or answers with something that is not data.

## Reason codes

`ReasonCode` is a closed list. The UI maps each code to one string in `copy.ts`. Tests and API clients assert codes, never text.

| Group | Codes |
|---|---|
| File | `invalid_type`, `too_large`, `too_many_pages`, `image_too_large`, `unreadable_file` |
| Document | `out_of_scope`, `unclear_document`, `unknown_authority` |
| Expiry | `expired`, `expiry_uncertain`, `near_expiry` |
| Values | `number_format`, `date_order`, `shares_total`, `sole_owner_count`, `legal_form_not_allowed`, `arabic_name_missing`, `high_risk_activity`, `evidence_mismatch`, `qr_mismatch`, `registry_not_found`, `registry_expiry_mismatch`, `registry_unavailable`, `applicant_name_mismatch`, `owners_unclear`, `ubo_needs_examination`, `low_confidence` |
| Process | `processing_failed`, `budget_exhausted`, `fallback_model`, `resolver_budget`, `verification_failed`, `reviewer_rejected` |
| Escape | `other` |

## ProposedFix

| Attribute | Type |
|---|---|
| `field` | `field_path`. It must be one of the failed fields. |
| `new_value` | `str`, parsed to the field's type during validation |
| `evidence_quote` | `str` |
| `self_confidence` | `high \| medium \| low \| unknown` |
| `rationale` | `str`, shown as model output |
| `accepted` | `bool`, set by code after re-validation |

## FieldConfidence

| Attribute | Type |
|---|---|
| `score` | `float`, 0 to 1 |
| `signals` | `{agreement?, grounding, rules, ocr, corroboration?, self_rating}`. Each is 0 to 1, or absent. `self_rating` is the model's own rating, with a small fitted weight (plan A7); the other five are the FR-019 signals. |
| (score rule) | Weighted average of the signals that are present: a missing signal is left out, not counted as 0. Weights are non-negative, so raising a signal never lowers the score. |
| (which fields) | Every required form field has a threshold in `config/thresholds.yaml`. |
| `threshold` | `float`, from `config/thresholds.yaml` |

## Decision (routing)

| Attribute | Type |
|---|---|
| `route` | `ready \| needs_review \| reject` |
| `reasons` | `list[Reason{code: ReasonCode, field: field_path \| None, rule_id: str \| None}]`. Empty only when `route = ready`. |

**Reject conditions (FR-037):**
- a file reason code
- `out_of_scope`
- `expired`, and only when it is corroborated: both passes agree **and** grounding passes, **or** the QR code or registry confirms the expiry

An uncorroborated expiry produces `expiry_uncertain`, which routes to `needs_review`.

## KYBOnboardingForm

The form is built as a **draft** right after the gate, before review. It is rebuilt after every applied reviewer decision. **Its `version` increases whenever its content changes**: any value, or any field state, including a field approval. Approving the whole form does not change the content, so it does not change the version. A `verification_failed` result **does** raise the version, as a `system` change. This makes a new approval and a new submission possible even when no value changes.

| Attribute | Source |
|---|---|
| `version` | `int`. Starts at 1. |
| `legal_name_en`, `legal_name_ar` | `trade_name_en`, `trade_name_ar` |
| `legal_form` | `legal_form` |
| `licence_number` (PII), `issuing_authority` | same names |
| `issue_date`, `expiry_date` | ISO dates |
| `activities` | list of `{code, description}` |
| `registered_address` (PII) | `address` |
| `beneficial_owners` (PII) | people with `share_pct >= 25`. If no shares are printed: empty, with state `needs_examination` and reason code `ubo_needs_examination`. |
| `controllers` (PII) | all managers plus all beneficial owners. Merged only when the normalised name **and** nationality match. |
| `chamber_number` | `chamber_number` |
| `required_documents` | derived (see below) |
| `field_states` | `dict[form_field, passed \| flagged \| approved \| corrected \| overridden \| needs_examination]` |

**Required documents:**

| Condition | Document |
|---|---|
| `llc`, `llc_single_owner`, `fzco`, `fz_llc`, or no shares printed | Memorandum of association |
| Each beneficial owner and each controller | Identity document (Emirates ID or passport) |
| DET | Registered tenancy contract (Ejari) |
| ADDED | Registered tenancy contract (Tawtheeq) |
| DMCC, IFZA | Free-zone lease agreement |
| `branch` | Parent company registration |

## Run

| Attribute | Type |
|---|---|
| `run_id` | UUID |
| `file_sha256` | `str`, unique |
| `status` | see the state transitions below |
| `applicant_name` | `str` |
| `route`, `reasons` | from the routing `Decision` |
| `deadline_at` | timestamp: the start of the current processing attempt + 120 s. It resets on every attempt, including a retry. |
| `created_at`, `updated_at` | timestamps |
| `cost_usd`, `duration_ms` | totals from the spans |

**State transitions:**

```
received → processing
processing → rejected | awaiting_review | awaiting_submit
processing → awaiting_review            (processing_failed, budget_exhausted, deadline passed)
awaiting_review → awaiting_submit | rejected
awaiting_submit → awaiting_review       (form changed after approval)
awaiting_submit → submitted → done
submitted → awaiting_review             (verification_failed; a new approval and submission are needed)
awaiting_review → processing            (retry processing, after processing_failed or budget_exhausted)
rejected → awaiting_review              (reopened by a reviewer, with a reason)
```

**After a restart:** on startup, every run in `received` or `processing` resumes from its last checkpoint. A run past its `deadline_at` moves to `awaiting_review` with reason code `processing_failed`.

## ReviewDecision

| Attribute | Type |
|---|---|
| `decision_id` | UUID, generated by the client. Unique, and the idempotency key. |
| `run_id` | UUID |
| `form_version` | `int`, the version the decision was made on |
| `target` | `field_path` or `rule_id` |
| `action` | `approve \| correct \| override` |
| `value` | `str \| None` (PII, encrypted), for `correct` |
| `reason` | `str \| None`. Required for `override`. |
| `reviewer` | `str` |
| `ts` | timestamp |

## Approval

| Attribute | Type |
|---|---|
| `approval_id` | UUID. The idempotency key is `action_id`, which is client-generated and unique. `(run_id, form_version)` is also unique. |
| `run_id` | UUID |
| `form_version` | `int`. It must equal the current form version when Submit runs. |
| `reviewer` | `str` |
| `ts` | timestamp |

## Submission

| Attribute | Type |
|---|---|
| `submission_id` | UUID |
| `idempotency_key` | `action_id`, client-generated and unique. `(run_id, form_version)` is also unique, so each approved form version has at most one submission. |
| `form_version` | `int` |
| `form` | `KYBOnboardingForm`, encrypted |
| `approved_by` | `str` |
| `verified` | `bool`, set after the read-back comparison. A run is `done` when its latest submission is verified. |

## AuditEvent

| Attribute | Type |
|---|---|
| `event_key` | `str`, unique. A repeated write with the same key is ignored. The key is:<br>• the `decision_id`, for field decisions<br>• the client-generated `action_id`, for reject, reopen, approve-form, submit and retry<br>• `run_id:node:checkpoint_id`, for `system` events, which is unique for each step execution |
| `run_id` | UUID |
| `action` | `approve \| correct \| override \| reject \| reopen \| approve_form \| submit \| verify \| retry \| status_change \| other` |
| `target` | `field_path \| rule_id \| None` |
| `old`, `new` | `str \| None` (PII, encrypted) |
| `reason` | `str \| None`. Required for `override`, `reject` and `reopen`. |
| `actor` | `str` (a reviewer account, or `system`) |
| `ts` | timestamp |

## CapturedCorrection

| Attribute | Type |
|---|---|
| `capture_key` | `decision_id`, unique |
| `run_id` | UUID |
| `field` | `field_path` |
| `read_value`, `corrected_value` | `str` (PII, encrypted) |
| `fault_group` | catalogue group, for example `blur_date` or `misread_number` |
| `status` | `pending \| approved_for_eval \| discarded` |
| `retention` | deleted with its run |

A captured correction never leaves the database as is. When a maintainer approves it, `scripts/make_twin.py` generates a synthetic licence with the same layout and the same fault, and adds it as a `LabelledCase`.

## Span

| Attribute | Type |
|---|---|
| `span_id`, `parent_id`, `run_id` | identifiers |
| `kind` | `step \| model_call \| tool_call` |
| `name` | `str` |
| `requested_model`, `serving_model`, `effort` | for model calls |
| `input_tokens`, `output_tokens`, `thinking_tokens`, `cache_read_tokens` | `int` |
| `latency_ms`, `cost_usd` | numbers |
| `prompt_hash` | `str` |
| `raw_result`, `model_view` | `str`, for tool calls. Masked when read. |
| `error_code` | `str \| None`, for failed tool calls (see the resolver contract's error codes) |

## LabelledCase

| Attribute | Type |
|---|---|
| `case_id` | `str` |
| `source` | `synthetic \| public \| synthetic_twin` |
| `document` | a path, or a download reference |
| `applicant_name` | `str` |
| `expected_route` | route |
| `expected_reason_codes` | `list[ReasonCode]` |
| `expected_values` | `dict[field_path, value]` |
| `group` | catalogue group |
| `split` | `calibration \| test \| precision`. Calibration and test are assigned per group with a fixed seed, 50/50. `precision` holds the release-only precision set, which is never used for calibration. |
| `mix_weight` | `float`, the weight of its group in the realistic mix |

## Writes and resumption

LangGraph runs a node again from its start when the node resumes after `interrupt()`. Two design rules follow:

1. **Side effects happen only in dedicated nodes after the interrupt.** These include writing decisions, audit events, captured corrections, form versions and submissions. The review node only collects the decision payload.
2. **Every write is keyed and idempotent.** Each write uses the unique key listed above (`decision_id`, `action_id`, `event_key`, `capture_key`), so running a node twice writes nothing new. A new user action, such as a second reject after a reopen, has a new `action_id`, so it is always recorded.
