# Contract: Resolver tools

The resolver is a tool loop on the Messages API, with `tool_choice: auto` and `strict: true` on every tool. Every tool input schema sets `additionalProperties: false`.

## Budgets (the only definition)

Every other document links here rather than restating these numbers.

**Definitions:**
- A **turn** is one model response in the resolver loop. One turn may contain several parallel tool calls.
- A **round** is one loop of turns followed by one pass through validation.
- A `licence_reread_region` call makes its own vision model call. Its tokens, time and cost count against the same budget, and it records its own span.

| Limit | Soft (the model is told to finish) | Hard (code stops the loop) | Scope |
|---|---|---|---|
| Turns | 5 | 6 | per round |
| Rounds | — | 2 | per run |
| Tokens (input + output + thinking, including vision re-reads) | 32,000 | 40,000 | per run |
| Wall time | 35 s | 45 s | per run, for the resolver only |
| Tool calls | — | 12 | per run |

**Processing deadline.** Each processing attempt has a deadline of 120 s, reset on retry (FR-039). The p95 targets are 60 s without the resolver and 90 s with it (SC-006). The latency budget for each stage is in [plan.md](../plan.md#latency-budget).

**Per model profile.** A model profile may set `resolver_seconds: {soft, hard}` for a slower model (ADR-004); a model on a CPU needs minutes per call. The turn, round, token and tool-call limits are the same for every profile.

**These numbers are provisional.** The Foundation throughput measurement (task T034) records output tokens per second and the latency of each call on synthetic documents. The limits are then set from those figures, and this table is updated in the same pull request.

## When the resolver runs

The graph is `validate → resolve → validate` (at most 2 rounds) `→ confidence`. The resolver runs only when a check that a second reading can fix has failed:

| Reason code | Why a re-read can help |
|---|---|
| `evidence_mismatch` | the value is not in its quote: likely a misread |
| `number_format` | a misread character breaks the format |
| `date_order` | a misread date |
| `qr_mismatch` | the printed number may be misread |
| `expiry_uncertain` | the two readings disagree |
| `registry_not_found` | the number looked up may be misread |
| `low_confidence` from the `required` check | the value was not readable |

**Applying proposals:** the resolve node applies each proposal to a copy of the extraction, re-runs every rule, and keeps the proposal only if no blocking check and no re-readable check (the table above) fails on its field (FR-016). A business warning that is true of the corrected value, such as `near_expiry`, does not block it: it is not a doubt about the reading, and it stays flagged for the reviewer. A kept value has origin `read` and the proposal's evidence quote, so the evidence check applies to it as to any read value.

**Text-only models:** a profile with `vision: false` does not get `licence_reread_region`; `licence_ocr_region` reads the same regions from the OCR words.

**Unknown tool names:** a call to a tool that is not in the list (for example `submit_form`, written on a document) returns `invalid_arguments`, with `allowed` listing the tool names. Nothing runs.

## Loop contract

1. **Request:** the system prompt, the failed fields with their rule messages, the current values and quotes, and the tool list below.
2. **Per `tool_use` block, before execution, code checks:**
   - **Budget:** turns, tokens, time and tool calls (see the Budgets table). When a soft limit is reached, the next request includes "Finish now: call propose_fix for any field you are sure of, then finish."
   - **Scope:** `field` must be in the failed list. Otherwise the tool does not run, and the result is a `field_out_of_scope` error that lists the allowed fields.
   - **Arguments:** validated against the schema again in code. A failure returns an `invalid_arguments` error that names each invalid argument and its valid range.
   - **Repeats:** a call with the same tool and arguments as an earlier call returns the earlier result with `duplicate_call`, and does not run again.
3. **Execution:**
   - All tool calls in one assistant message run, and their results return in one user message.
   - Temporary failures (timeouts, 5xx) are retried twice in code before the model sees an error.
4. **End:** the loop ends on `finish`, at a hard limit, or on any stop reason other than `tool_use`.
5. **After the loop:** each `propose_fix` goes through validation. It is accepted only if every rule on its field passes.
6. **Rounds:** at most 2 rounds through validation.

## Result rules

- **A result says what the next decision needs,** in words: what was read, where, and how it compares with the current value.
- **A failed call always returns a detailed error result** that tells the model what to do next. See [Error responses](#error-responses). The loop never ends silently on a tool failure, and the model never sees a raw exception.
- **Maximum result size:** 1,500 characters. A longer result is truncated with a note saying what was left out.

## Error responses

**Every failed tool call returns a `tool_result` with `is_error: true`.** Its content is a JSON object. The `message` gives the model what it needs to decide its next action, in words. The other fields let code and tests check the error's structure without depending on the wording.

```json
{
  "error_code": "registry_unavailable",
  "what_failed": "licence_lookup_registry for licence 1234567, authority DET",
  "why": "The DET register did not answer after 2 retries (timeout 5 s each).",
  "state": "Nothing changed. The registry check is now could_not_run.",
  "retryable": false,
  "next_action": "Do not call licence_lookup_registry again in this run. Use the document evidence. If you propose a fix for licence_number, set self_confidence to low.",
  "allowed": null,
  "message": "Registry lookup failed: the DET register did not answer after 2 retries. The registry check could not run. Do not call this tool again in this run. Use the document evidence, and set self_confidence to low in your proposal."
}
```

| Field | Content |
|---|---|
| `error_code` | One value from the closed list below. |
| `what_failed` | The tool and the arguments it was called with, in words. |
| `why` | The cause, in words. Never a stack trace, file path or internal exception name. |
| `state` | What is true now. For example: nothing changed, a check is now `could_not_run`, or a proposal was not recorded. |
| `retryable` | Whether calling again with the same arguments can succeed. Code has already retried temporary failures before the model sees any error. |
| `next_action` | One concrete instruction: what to call instead, how to correct the arguments, or to finish. |
| `allowed` | The valid values, when the error is about a value: allowed fields, page range, regions or enum members. Otherwise `null`. |
| `message` | `why`, `state` and `next_action` in one short paragraph, which is the text the model reads first. |

**Error codes.** The harness and the tools produce these codes:

| `error_code` | When | `next_action` tells the model to |
|---|---|---|
| `invalid_arguments` | Code re-validation of the arguments failed: a type, a range or a missing field. | Call again with the listed correction. `allowed` names each invalid argument and its valid range. |
| `field_out_of_scope` | The `field` is not in the failed list. | Use one of the fields in `allowed`, or finish. |
| `page_not_found` | The page is outside the document. | Use a page in `allowed` (for example `[1]`). |
| `region_unreadable` | The region contains no readable text at 400 DPI. | Try a neighbouring region from `allowed`, or propose nothing for this field. |
| `registry_unavailable` | The register did not answer after code retries. | Stop calling the registry in this run, and rely on document evidence. |
| `registry_not_applicable` | The authority has no register lookup in this deployment (`is_error: false`; this is an answer, not a failure). | Stop calling the registry for this authority. |
| `vision_call_failed` | The vision re-read failed after code retries, or the model refused it. | Use `licence_ocr_region` for the same region instead. |
| `proposal_refused` | `propose_fix` targeted a field that passed, or `new_value` cannot be parsed to the field's type. | Propose only for fields in `allowed`, in the format stated. |
| `duplicate_call` | The same tool and arguments were already called in this run. The earlier result is returned again. | Use the earlier result. Do not repeat the call. |
| `budget_soft_limit` | A soft limit was reached. This is returned with the next tool result, not instead of it. | Call `propose_fix` for any field you are sure of, then call `finish`. |
| `budget_hard_limit` | A hard limit was reached. No tool runs; the loop ends after this turn. | None. Code stops the loop and keeps the best accepted fixes. |
| `tool_internal_error` | Any unexpected failure inside a tool. The exception is logged and traced, never shown to the model. | Continue with other tools or finish. Do not retry this tool with the same arguments. |

**Rules:**
- **A failed call never ends the run.** The run always continues to validation and the gate. A failure that matters for routing (for example, `registry_unavailable`) also sets its check to `could_not_run`.
- **Code retries temporary failures first.** Timeouts and 5xx responses are retried twice with backoff. The model sees an error only when a decision is left for it.
- **An error tells the model what is still allowed.** When the problem is a value, `allowed` lists the valid ones, so the next call can be correct.
- **Errors are traced.** Each error result is stored in the tool-call span with the raw exception (masked), the content the model saw, and the error code. The eval report counts errors by code.
- **Errors are tested by structure, never by wording.** A test checks `is_error`, `error_code`, that `next_action` and `allowed` are present where the table requires them, the size limit, and the absence of a stack trace.

## Tools

### licence_reread_region (read)

| Item | Value |
|---|---|
| Description | Re-read one region of a licence page at high resolution. Use it when a field failed grounding, or when the two reading passes disagree. Do not use it for fields that passed. Returns the text found, or states that the region has no readable text. |
| Input | `page` (int, 1 to 5), `field` (enum of failed-field names), `region` (`top_left \| top_right \| middle \| bottom_left \| bottom_right \| full_page`) |
| Result example | "Page 1, top-right region, read at 400 DPI. Text found: 'Expiry Date 25/12/2026 تاريخ الانتهاء'. 25/12/2026 is a valid DD/MM/YYYY date. The first reading gave 25/12/2028." |
| Error example | `page_not_found`: "Re-read failed: page 3 does not exist. The document has 1 page. Call this tool again with page 1." (`allowed: [1]`) |

### licence_ocr_region (read)

| Item | Value |
|---|---|
| Description | Return the OCR words and their confidence for one region. Use it to check the reading quality before you propose a value. Do not use it to search the whole document. |
| Input | `page` (int), `region` (same enum) |
| Result example | "Page 1, top-right: 'Expiry' (0.96), 'Date' (0.95), '25/12/2026' (0.71). Mean confidence 0.87." |

### licence_lookup_registry (read)

| Item | Value |
|---|---|
| Description | Look up a licence number in the issuing authority's public register (mock). Use it when the licence number or expiry date is in doubt. Returns status and expiry, or states that no record exists. |
| Input | `licence_number` (str, 1 to 30), `authority` (`DET \| ADDED \| DMCC \| IFZA \| unknown`) |
| Result example | "Registry DET: licence 1234567 is active. Expiry 25/12/2026. Trade name 'Acme General Trading LLC'." |
| Absence example | "Registry DET: no record for licence 1234561. Check the number against the QR code and the printed text." |
| Not applicable example | `registry_not_applicable` (`is_error: false`): "Registry IFZA: the demo register does not cover this authority. The registry check is not applicable. Do not call this tool again for IFZA." |
| Error example | `registry_unavailable`: "Registry lookup failed: the DET register did not answer after 2 retries. The registry check could not run. Do not call this tool again in this run. Use the document evidence." |

### licence_lookup_activity (read)

| Item | Value |
|---|---|
| Description | Search the activity catalogue by code or by words. Use it when an activity code or description is unclear. |
| Input | `query` (str, 1 to 100) |
| Result example | "2 matches: 4690.01 General Trading (high risk); 4690.02 Foodstuff Trading." |

### licence_get_validation_report (read)

| Item | Value |
|---|---|
| Description | Return the current results of all checks. Use it after proposing fixes to see what still fails. |
| Input | none (empty object) |
| Result example | "2 checks fail: expiry_date (grounding, warn): value not in its quote. activities (high-risk, warn): General Trading." |

### propose_fix (output only)

| Item | Value |
|---|---|
| Description | Propose a corrected value for one failed field. The value is not applied until all checks pass. Call it once per field. |
| Input | `field` (enum of failed fields), `new_value` (str), `evidence_quote` (str), `self_confidence` (`high \| medium \| low \| unknown`), `rationale` (str, ≤ 300 characters) |
| Result | "Proposal recorded for expiry_date. It will be checked after you finish." |
| Error | `proposal_refused`: "Proposal refused: trade_name_en passed all checks and cannot be changed. Propose only for expiry_date or licence_number." (`allowed: ["expiry_date", "licence_number"]`) |

### finish (output only)

| Item | Value |
|---|---|
| Description | End the investigation. Call it after your proposals, or when nothing more can be found. |
| Input | `summary` (str, ≤ 500 characters) |

## Not available to the model

The model never receives a write tool. Status changes, audit events, submissions and captured corrections are made only by harness code, after the resolver ends.

## Module mapping

| Tool | Module |
|---|---|
| `licence_reread_region` | `tools/reread_region.py` |
| `licence_ocr_region` | `tools/ocr_region.py` |
| `licence_lookup_registry` | `tools/registry_mock.py` |
| `licence_lookup_activity` | `tools/activity_lookup.py` |
| `licence_get_validation_report` | `tools/validation_report.py` |
| `propose_fix`, `finish` | `nodes/resolve.py` |
