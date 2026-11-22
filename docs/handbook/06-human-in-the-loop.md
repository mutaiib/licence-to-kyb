# 06 — Human in the loop

## In one minute

Decide autonomy **per action**, not per system. For each action, the choice is one of: act silently, act and report, ask first, or suggest only.

- **Escalation** hands a whole case to a person.
- **An approval** asks about one exact action.
- **A good review screen** shows what changed, the evidence, and how to undo it. It labels model text as model output.

## Rules

- **Rate each action by risk:** how hard it is to undo, and how far its effect reaches. Code rates it. A model may raise a rating but never lower it.
- **An approval covers one exact thing.** In this repo, that is one form version. Any later change needs a new approval.
- **There are four escalation triggers:**
  - retries are used up
  - the action is above the risk level
  - the request is out of scope
  - calibrated confidence is below the threshold

  Both code and the model must be able to escalate.
- **Design against approval fatigue:**
  - Expand only the flagged fields.
  - Require one decision per flagged field.
  - Allow no "approve all" while a decision is missing.
  - Seed known-bad cases to measure whether reviewers still catch errors.
- **Overrides are narrow and audited.** Here, only a check that *could not run* can be overridden, and only with a written reason. A failed check can never be overridden.
- **Never leave a person stuck.** Provide reopen (after a reject), retry (after a processing failure), and manual entry.
- **Capture feedback as a side effect of the work.** Every correction is recorded. It becomes a regression case, never model memory.
- **Every action has one accountable person.** Use individual accounts, never a shared one, and write one audit event per action.

## In this repository

- **Autonomy per action:** [architecture §10](../architecture.md#10-trust-boundaries-and-safety), [design worksheet](../design-worksheet.md).
- **Review rules:** FR-022 to FR-028, FR-038 and FR-043 ([spec](../../specs/001-licence-to-kyb/spec.md)).
- **Overrides:** the clarification answer recorded in the spec.
- **Feedback capture as synthetic twins:** [data model, CapturedCorrection](../../specs/001-licence-to-kyb/data-model.md).
- **The review screen's words:** [UI copy](../ui-copy.md).
- **Timing the reviewer:** timed walkthroughs, measured from audit timestamps (SC-005).

## Mistakes to avoid

- **A shared reviewer account.** It makes "the approver is identifiable" true but meaningless.
- **Approving a form, then letting it change.** Bind each approval to a version.
- **Measuring reviewers by approval rate.** Careful and careless reviewers can produce the same number.
- **Putting corrections into the model's memory.** A memory entry must never grant authority or carry personal data.

## Self-check

<details><summary>1. The registry is down. The reviewer has checked the licence another way. What can they do?</summary>

Override the `could_not_run` registry check with a written reason. The audit records the override, the reason and the reviewer. If the registry had returned "no record", no override would be possible.
</details>

<details><summary>2. Why does approving the whole form not raise the version, while a field approval does?</summary>

A field approval changes the form's content (a field state). Approving the whole form records a decision about the current content. Binding approvals to content versions means any content change needs a new approval.
</details>

<details><summary>3. How do you know reviewers still read what they approve?</summary>

Seed known-bad cases and measure the catch rate. A falling catch rate means the design must change, for example with fewer, better-targeted requests.
</details>
