# 01 — Choosing the architecture

## In one minute

Choose the simplest design that does the job. In order:

1. plain code
2. one model call
3. a **workflow**: fixed steps, controlled by code
4. one **agent**: a model that chooses its own tool calls in a loop
5. several agents

**The deciding question:** *can I write the steps down before I see the input?* If yes, build a workflow, and use an agent only for the part whose next step depends on what was just found.

**Reliability multiplies.** At 95% per model step, 10 chained steps succeed about 60% of the time (0.95¹⁰). Each decision moved into code removes one factor.

## Rules

- Unstructured input alone needs a model, not an agent.
- **A workflow's cost and paths are fixed. An agent's are bounded only by its limits.** An agent earns its place only on inputs that no fixed branch handles.
- **A second agent needs a stated reason:**
  - the work does not fit one context
  - it needs different permissions
  - it gains from running in parallel

  Several agents multiply tokens and hand-offs.
- **Decide per task.** One product can mix a workflow and an agent.
- **Make every expensive part prove its value.** Measure the system with and without it, and remove it if the gain is not worth the cost.

## In this repository

- **Design:** a fixed LangGraph workflow. Three steps use a model: route, extract and resolve. Only resolve is an agent ([architecture §3](../architecture.md#3-why-a-workflow-with-one-agent), [ADR-001](../decisions/ADR-001-workflow-with-one-agent.md)).
- **The agent's job:** it repairs values that failed a check. That is the only step where the investigation cannot be scripted ([spec, User Story 4](../../specs/001-licence-to-kyb/spec.md)).
- **Proof of value:** experiments will measure the resolver on vs. off, and one reading vs. two, once real readings exist (T101, [experiments](../experiments.md)).
- **Design record:** all nine worksheet rows, including topology "one agent, no reason for more" ([design worksheet](../design-worksheet.md)).

## Mistakes to avoid

- **Choosing an agent because it is the impressive option.** Choosing a workflow, and saying why, shows more judgement.
- **One "medium autonomy" level for the whole system.** Autonomy is decided per action (see [06](06-human-in-the-loop.md)).
- **Assuming the agent helps without measuring it.**

## Self-check

<details><summary>1. A task extracts 20 fields from an invoice and checks them. Workflow or agent?</summary>

A workflow. The steps (read, extract, validate, decide) are known before the input is read. The input being unstructured only means a model call is needed.
</details>

<details><summary>2. When does a single agent become two?</summary>

Only when one of three things is true: the work does not fit one context, it needs different permissions, or it gains from running in parallel. Otherwise, a second agent adds tokens and hand-off failures.
</details>

<details><summary>3. Why does moving a decision into code beat adding a retry?</summary>

A retry fixes only the errors a detector notices, and it costs tokens. Code is deterministic, so that step leaves the product of per-step success rates altogether.
</details>
