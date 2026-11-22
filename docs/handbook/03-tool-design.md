# 03 — Tool design: requests, results and errors

## In one minute

A tool's name, description and schema are the model's whole interface to it. A vague tool produces wrong calls, not errors.

A tool call is a cycle of four parts:
1. **The request:** the model emits `tool_use` with arguments.
2. **Execution:** code checks the budget, the scope and the arguments, then runs the tool.
3. **The result:** a `tool_result` that contains what the next decision needs.
4. **The decision:** the model chooses its next step.

**When a call fails, the result must direct the model.** It says what failed, why, what is still true, whether a retry can help, one concrete next action, and the allowed values.

## Rules

**The description** states four things:
- what the tool does
- when to use it
- when not to use it
- what failure looks like

**The schema** makes mistakes hard:
- fixed lists instead of free text
- `strict: true` with `additionalProperties: false`
- no fields for values that code already knows

**Granularity:**
- Merge operations that share one job and one risk level.
- Split operations that differ in risk, because approval is decided per tool.
- Use a shared prefix (`licence_…`) when tools overlap.

**Read vs. write:**
- Mark each tool by what it does, not by its name.
- Every write carries an idempotency key.
- Prefer actions that can be undone.

**Results:**
- Use names and words, not internal IDs and codes.
- State absence clearly ("no record for licence 1234561").
- Keep results small, because each one is re-sent on every later turn.

**Errors:** structured, and they direct the model. The fields are:
- `error_code`
- `what_failed`, `why`
- `state`
- `retryable`
- `next_action`
- `allowed`
- `message`

Never send a stack trace. A failed call never ends the run.

**Who retries:** code retries temporary failures (timeouts, 5xx) first. The model hears about a failure only when a decision is left for it.

**Repeats:** a repeated identical call returns the earlier result and says so (`duplicate_call`), so the loop does not spin.

**Permission:** offering a tool is not permission. The tool's own code checks scope and authority.

## In this repository

- **Request → execute → return,** with example JSON: [architecture §7](../architecture.md#7-how-a-tool-call-works).
- **The contract for every tool, and the error responses with their 12 error codes:** [resolver tools](../../specs/001-licence-to-kyb/contracts/resolver-tools.md#error-responses).
- **Value-driven tests for error responses,** checked by structure, never by wording: [test cases](../../specs/001-licence-to-kyb/test-cases.md).
- **No write tools for the model.** Writes exist only in harness code, in dedicated nodes ([architecture §10](../architecture.md#10-trust-boundaries-and-safety)).

## Mistakes to avoid

- **Raw exceptions as results.** They waste tokens and teach the model nothing.
- **"An error occurred."** It gives the model no next step, so it retries blindly.
- **An error result with no allowed values.** The model then guesses the correction.
- **Telling the model to use a parameter the tool does not have.** Found in review: an error said "propose with low self-confidence", but `propose_fix` had no confidence input.
- **A tool that silently makes a model call.** `licence_reread_region` calls the vision model, so its tokens must count against the budget and appear in the trace.

## Self-check

<details><summary>1. The registry times out. What does the model see, and what has code already done?</summary>

Code has already retried twice with backoff. The model sees an error:
- `error_code: registry_unavailable`, `retryable: false`
- `state`: the registry check is now `could_not_run`
- `next_action`: do not call the registry again in this run; use the document evidence
</details>

<details><summary>2. The model asks to re-read page 3 of a 1-page document. What happens?</summary>

The tool does not run. The result is a `page_not_found` error with `allowed: [1]` and a next action: call again with page 1.
</details>

<details><summary>3. Why merge or split tools by risk level?</summary>

Approval and autonomy are decided per tool. A tool that mixes a safe read with a risky write forces the strictest approval onto both, or lets the risky write run at the safe level.
</details>
