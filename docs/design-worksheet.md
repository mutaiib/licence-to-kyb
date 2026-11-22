# Design worksheet

Nine questions that every agent design must answer, answered for `licence-to-kyb`.

- Each answer is a decision that a second engineer can test against the running system.
- "None" is a decision. A blank would mean "not decided yet".
- The method behind these rows is in the [agent design framework](agent-design-framework.md).

| Row | Decision | How to test it |
|---|---|---|
| **Goal and done condition** | Turn one trade licence into an approved, submitted KYB form. Done means three things are true in stored state: a `Submission` exists, its values equal the approved form, and the audit log names the approver. | Make the submission store fail. The run must not be marked done, whatever the model reports. |
| **Autonomy per action** | Reads, OCR, registry and activity lookups run silently. A status change to review runs and is recorded as a `system` audit event. The resolver can only propose fixes. Approve, correct, override (only for a check that could not run), reject and reopen are actions for a person only. **Submit always needs a person's click.** Automatic rejection needs a corroborated expiry. | List the actions from the code. Each has exactly one level in config. Submit cannot run without an authenticated approval of the current form version. |
| **Tools, marked read or write** | Read: `licence_reread_region`, `licence_ocr_region`, `licence_lookup_registry`, `licence_lookup_activity`, `licence_get_validation_report`. Output only: `propose_fix`, `finish`. Write, in harness code only, in dedicated nodes, each with an idempotency key: review decisions (`decision_id`), approvals and submissions (client `action_id`, unique per `run_id` and `form_version`), audit events (`event_key`) and captured corrections (`capture_key`). | Resume the review node twice and submit twice. Exactly one audit event per decision and one submission exist. |
| **Context and memory** | Each call contains the system prompt, the authority profile, the page images and the OCR text. The resolver also gets the failed fields and the validation report. **Memory between runs: none.** Each run uses only its own document. Reviewer corrections stay encrypted with their run. After maintainer approval, they join the eval set as synthetic twins, never as model memory. | Run the same document twice after a correction on a different run. The output depends only on this document. |
| **Topology** | A workflow (LangGraph) with **one bounded agent**, the resolver, used only when a fixable check fails. There is no reason for a second agent: one context is enough, one permission set is enough, and the steps gain nothing from running in parallel. | Ask which of those three reasons applies. The answer is none. |
| **Guardrails and security audit** | Input checks: file type from its bytes, size, pages, duplicates. Tool-call checks: budget, field scope, argument validation. Output checks: the form uses only validated or approved values. Deadline (120 s), daily token budget and fallback model all route to review, never to a dead end. Router and extractor have no tools, so the untrusted document can only reach read-only tools. | An injected document has the same outcome as its clean twin. An expired licence is never `ready`. |
| **Identity** | Each reviewer signs in with their own account (argon2id hash, CSRF-protected session that expires after 8 hours). Every decision and action writes exactly one `AuditEvent` with run, target, old value, new value, reason, actor and time. | Pick any submission. Find the person responsible from the audit log alone. |
| **Evals** | About 100 labelled cases, split 50/50 into calibration and test. They cover synthetic clean and noisy licences in two layouts per authority, edge cases, injected text, non-licence documents and one public real licence. Graders read final state (route, reason codes, field values, submission exists). Metrics come from the test split with 95% intervals, weighted to a 70/20/10 mix. Routing reports pass^3 on a 30-case subset. | Change one line of a prompt and run the suite. The report lists which cases changed. |
| **Cost** | Estimates before measurement, with thinking billed as output: route ≈ 3k in / 0.8k out, extract ≈ 2 × 10k in / 6k out, so a typical run without the resolver costs about $0.23. The resolver adds at most 40k tokens. The target is below $0.40 on average. Cheaper configurations are measured experiments. | Compare the tokens recorded in traces with these figures. Correct the estimate when they differ. |

## Rows that one change affects

Adding a write tool, such as "send the form to the provider's API", would change these rows:

| Row | Change |
|---|---|
| Tools | A new write, with an idempotency key. |
| Autonomy | A new level, which must be "confirm". |
| Guardrails | A new risk: a wrong form reaches an external system. |
| Identity | Whose credentials the call uses. |
| Evals | New cases in which the send must not happen. |
| Cost | The tokens added by the tool description on every call. |

Before merging a change, review which rows it touches.
