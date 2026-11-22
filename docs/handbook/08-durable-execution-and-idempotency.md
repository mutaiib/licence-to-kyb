# 08 — Durable execution and idempotency

## In one minute

Long-running runs with human pauses must survive restarts, retries and resumes, and must never write anything twice.

**LangGraph specifics:**
- A checkpointer saves state after every node.
- `interrupt()` pauses a run.
- `Command(resume=…)` continues it.
- **On resume, the interrupted node runs again from its start.** Any write inside that node happens twice, unless it is keyed.

## Rules

- **Collect in one node, write in another.** The node that interrupts only collects the human's input. Separate nodes after it do the writes.
- **Key every write:**
  - Field decisions are keyed by a client-generated `decision_id`.
  - Form-level actions (approve, reject, reopen, submit, retry) are keyed by a client-generated `action_id`.
  - System events are keyed by `run_id:node:checkpoint_id`.

  A repeat with the same key writes nothing new. A new action has a new key, so it is always recorded.
- **Uniqueness must not block legitimate repeats.** Found in review: a submission key of `run_id` made resubmission impossible after a failed read-back. The fix:
  - submissions are unique per approved form version
  - a verification failure raises the version
- **Verify the outcome, not the claim.**
  1. Write.
  2. Read back.
  3. Compare.
  4. Mark the run done only on a match.

  A missing record may mean "not yet", so do not repeat the write just because a read shows nothing.
- **Nothing stalls:**
  - Resume interrupted processing on startup.
  - Give each processing attempt a deadline, reset on retry.
  - Route every failure to a person with a reason code.
- **Background tasks are not durable on their own.** The checkpoint plus a startup resume is what makes them safe.

## In this repository

- **The rules for writes and resumption:** [data model, Writes and resumption](../../specs/001-licence-to-kyb/data-model.md#writes-and-resumption).
- **Run states and transitions,** including retry and reopen: [data model, Run](../../specs/001-licence-to-kyb/data-model.md).
- **The side-effect node design:** [research R6a](../../specs/001-licence-to-kyb/research.md).
- **Value-driven cases:**
  - resumed twice gives one audit event
  - reject, reopen, reject gives three events
  - resubmission after a failed verification works

  See [test cases](../../specs/001-licence-to-kyb/test-cases.md).

## Mistakes to avoid

- **Writing an audit event inside the node that calls `interrupt()`.** Found in review: every resume would have duplicated it.
- **A key that is too broad.** Found in review: `run_id:action:form_version` silently dropped a second rejection after a reopen.
- **A deadline set once at creation.** Found in review: every retry would have failed at once.

## Self-check

<details><summary>1. Why can a review decision not be written in the review node itself?</summary>

On resume, LangGraph runs the review node again from its start, so the write would happen twice. Writing in a later node, keyed by `decision_id`, makes the repeat harmless.
</details>

<details><summary>2. The stored submission does not match the approved form, and no value needs to change. How does the reviewer resubmit?</summary>

The verification failure raises the form version as a system change. The reviewer approves the new version, then submits it with a new `action_id`. The run is done when that submission's read-back matches.
</details>

<details><summary>3. What makes a FastAPI background task safe against a crash?</summary>

The task alone is not safe. Two things make it safe: the checkpoint after each node, and a startup job that resumes every run still in `received` or `processing`, with a fresh deadline.
</details>
