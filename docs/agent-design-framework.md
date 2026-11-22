# Agent design framework

A method for designing any LLM system, from a single model call to several agents. Work through the steps in order. Write each answer down, and make it testable.

**The test for a good answer:** a second engineer can check it against the running system.
- "Medium autonomy" fails the test.
- "Refund: confirm. Lookups: run silently." passes it.

---

## Step 0 — Choose the simplest option that works

Go up this list only when the option below it cannot do the job:

1. **Plain code.**
2. **One model call.** Classification, extraction, summarising.
3. **A workflow.** A fixed sequence of model calls and code, where code controls the order.
4. **One agent.** A model that chooses its own tool calls in a loop.
5. **Several agents.**

**The deciding question is:** *Can I write the steps down before I see the input?* If yes, build a workflow. Use an agent only for the parts where the next step depends on what was just found.

**A second agent needs a stated reason.** The valid reasons are:
- the work does not fit in one context
- it needs different permissions
- it gains from running in parallel

Several agents multiply token use and add hand-offs that can fail.

**Do the reliability arithmetic.** At 95% per model step, 10 chained steps succeed about 60% of the time. Each step moved into code removes one factor from that product.

## Step 1 — Goal and done condition

- State what the system is for in one sentence.
- **State "done" as a fact you can read outside the model,** such as a record that exists, a status that is closed, or a file that passes a check.
- "The model reports success" is not a done condition. Every later step depends on this one, because verification and evals need a fact to check.

## Step 2 — Inputs and trust

- List every input: user text, uploaded files, web pages, tool results, other agents, memory.
- **Mark each input as trusted or untrusted.** Untrusted text can contain instructions.
- **A part that reads untrusted text should hold as few tools as possible.** If it can read private data, read untrusted text and change state in the same session, it needs supervision.

## Step 3 — The shape of the flow

Choose one pattern, or combine several:

| Pattern | Use when |
|---|---|
| **Chain** | Fixed steps. Put a code check before any step that is expensive to repeat or undo. |
| **Route** | Inputs fall into categories that each need different instructions or tools. Include `unclear` and a fallback path. |
| **Parallel: split** | Independent parts of one job can run at the same time. |
| **Parallel: vote** | The same question asked more than once, with the answers compared for agreement. |
| **Generate and evaluate** | One call produces, another scores against stated criteria, and code decides whether to repeat. |
| **Lead and workers** | The subtasks are unknown until the input is read. |

## Step 4 — Typed boundaries

- **Every hand-off carries a schema-checked object.** Code reads a named field more reliably than it searches prose.
- **Every closed list needs an escape value** such as `unclear` or `other`, and every field needs a way to say "not present". Without them, the schema pushes the model to invent answers.
- **A schema guarantees shape, not truth.** Add value checks in code, and a meaning check where code cannot decide.
- **Code supplies facts it already knows,** such as IDs, the date and the user's identity. The model supplies only what it must work out.
- **A retry states what failed.** A reply cut off at the token limit needs a higher limit, not the same call again.

## Step 5 — Tools

- **Mark each tool read or write** by what it does, not by its name. Keep the two kinds separate.
- **A description states four things:** what the tool does, when to use it, when not to use it, and what failure looks like.
- **The schema makes mistakes hard.** Use fixed lists, and leave out fields that code already knows.
- **Choose the right size.** Merge operations that share a job and a risk level. Split operations that differ in risk, because approval is decided per tool. Use a shared prefix when tools overlap.
- **A result contains what the next decision needs:** names rather than IDs, words rather than codes, and a clear statement when something is absent. Keep results small, because each result is re-sent on every later step.
- **A failed call returns a detailed error that directs the model.** Include:
  - an error code
  - what failed, and why
  - what is still true
  - whether a retry can help
  - one concrete next action
  - the allowed values, when the problem is a value

  Never return a stack trace. A write that timed out has an unknown outcome, so tell the model to read before it retries. Keep the fields structured, so tests can check them without depending on wording.
- **Code retries temporary failures.** The model hears about a failure only when a decision remains.
- **Every write carries an idempotency key** made from the run and the step. Prefer actions that can be undone.
- **Offering a tool is not permission.** The tool's own code checks authority.

## Step 6 — Autonomy for each action

- For each action, choose one level: **act silently**, **act and report**, **ask first**, or **suggest only**.
- **Rate risk by two things:** how hard the action is to undo, and how far its effect reaches. Code decides the rating. A model may raise a rating but never lower it.
- **An approval screen shows** the action, its effect and how to undo it. It labels code facts and model explanations separately.
- **An approval applies to one exact call.** An expired request counts as a decline.
- **Hand-off triggers** (send the whole case to a person):
  - retries are used up
  - the action is above the agent's risk level
  - the request is out of scope
  - calibrated confidence is below the threshold

  Both the model and the code must be able to trigger a hand-off.
- **Plan for approval fatigue.** Remove low-risk approvals with thresholds and easy undo. Never batch expensive actions. Seed known-bad cases to measure whether reviewers still catch them.

## Step 7 — Guardrails in code

Check at three points:

| Point | What it decides |
|---|---|
| **Input** | Whether the run happens at all. |
| **Before a tool call** | Whether the action happens. Rules that must always hold belong here, in code. |
| **Output** | What the reader sees. |

**Budgets.** Cap steps, tokens, time and money. Give each a soft limit, where the model is told to finish, and a hard limit, where code stops the run. Add caps per day and per account.

**Verify the outcome.** After an action, read the result from the real system. The agent must not be able to change the evidence.

**Ground claims.** Tie each factual claim to a source, check that the quote exists in the source, and refuse claims that have no support.

**Never let a guardrail block the path to a person.**

## Step 8 — Context and memory

- State what goes into each call. The context window is a budget.
- **State what is stored between runs,** who can delete it, and when it is loaded. Write "none" when nothing is stored.
- Facts that have a source of truth stay in that source. Read them through tools; do not copy them into memory.
- A memory entry never grants authority.

## Step 9 — Identity and audit

- **State whose authority each write uses,** with what scope and for how long.
- **State what the audit line records:** the run, the action, the values, and the person who approved.
- A shared service account cannot show who is responsible.

## Step 10 — Evals before scale

- **Start with 20 to 50 tasks drawn from real failures.** Keep a few examples of each kind of failure.
- **Balance the set.** Include tasks where the system should act and tasks where it should refuse. A set of only "should act" tasks rewards an agent that always acts.
- **Give each task a reference solution.** This proves the task is solvable and the grader works.
- **Use the cheapest grader that can answer the question:**
  1. code that checks the final state
  2. a model grader with a narrow rubric and an "unknown" answer
  3. sampled human review
- **Grade the outcome, not the path.** Do not require one specific sequence of steps.
- **Report pass^k when every run must succeed:** a task passes only if all k trials pass.
- **Run each trial from a clean environment,** with fresh data and a fixed clock.

## Step 11 — Cost and latency

- **Count tokens before you apply a price.** Estimate a typical run and a run at the hard limit.
- **Use caching first:** put the stable prefix before the parts that change.
- **Choose models by measurement.** Try the strong model at lower effort before you build a cascade of models.
- **Compare the estimates with the traces.** A large difference means an input to the estimate is wrong.

## Step 12 — Observe and improve

- **Record a trace for every run.** Each span holds the model and tool calls, tokens, latency and versions. Keep the raw tool result and the text the model saw.
- **Keep all flagged runs and a random sample of the rest.**
- **Every human correction becomes a regression case.**
- **Change one thing at a time,** run the evals, and keep the change only if the measured result improves.

---

## The worksheet

Record the answers in nine rows:

1. Goal and done condition
2. Autonomy per action
3. Tools, marked read or write
4. Context and memory
5. Topology
6. Guardrails and security audit
7. Identity
8. Evals
9. Cost

[`design-worksheet.md`](design-worksheet.md) shows the worksheet filled in for this project.

**When a change is proposed, list the rows it touches** and update each one.
