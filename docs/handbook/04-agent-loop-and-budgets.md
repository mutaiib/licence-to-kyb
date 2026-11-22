# 04 — The agent loop and its budgets

## In one minute

An agent is a loop:

1. Send the model its context and its tools.
2. If it replies with `stop_reason: tool_use`, run the tools and send back the results.
3. Repeat until it finishes or a limit stops it.

**Code owns the loop.** It decides when to stop, what the model may touch, and what happens to the model's output. The model never decides that its own output is correct.

## Rules

- **Budget every runaway dimension.** Turns, rounds, tokens (including thinking and any model calls inside tools), wall time and tool calls. Each limit catches a runaway that the others miss.
- **Use two levels per limit:**
  - **Soft:** tell the model to finish now, for example "propose what you are sure of, then finish".
  - **Hard:** code ends the loop and keeps the best attempt.
- **Define a "turn" precisely.** One model response can contain several parallel tool calls. Count turns and tool calls separately.
- **Run parallel tool calls together.** Execute every call in one assistant message, and return all their results in one user message.
- **Generate and evaluate.** The model proposes, and code validates each proposal. Code decides whether to run another round. The loop keeps the best attempt for the fallback.
- **Narrow the agent's scope.**
  - It may touch only the fields that failed.
  - Its outputs are proposals, not writes.
- **Define the budget numbers once,** in one contract table, and link to it from everywhere else. Restated numbers drift apart.
- **Make the budgets come from measurements.** A wall-time limit set without a throughput figure is a guess.
- **Use the current API rules.**
  - On the current model family, forced `tool_choice` is rejected: use `auto` with `strict` tools and a clear instruction.
  - Thinking cannot be turned off. Lower the effort instead.

## In this repository

- **The loop:** hand-written on the Messages API inside one LangGraph node ([ADR-002](../decisions/ADR-002-anthropic-sdk-inside-langgraph-nodes.md)).
- **The budget table:** the single definition, with soft and hard limits (provisional until the throughput probe, T034, runs) ([resolver tools, Budgets](../../specs/001-licence-to-kyb/contracts/resolver-tools.md#budgets-the-only-definition)).
- **Scope:** checked before every call. A proposal for a passed field is refused.
- **Validation:** every proposal goes back through the rules, at most 2 rounds ([spec, User Story 4](../../specs/001-licence-to-kyb/spec.md)).
- **Measured budgets:** the throughput probe (task T034) sets the provisional numbers ([plan, latency budget](../../specs/001-licence-to-kyb/plan.md#latency-budget)).

## Mistakes to avoid

- **A loop without a hard limit.** One stuck run can burn the daily budget.
- **Counting "steps" ambiguously.** Found in review: one file counted model turns, another counted tool calls.
- **A limit that defeats the feature.** Found in review: a 25 s resolver limit, with 12 possible tool calls and vision re-reads, would have stopped most repairs early.
- **Applying the agent's output directly.** A proposal is only a proposal until code validates it.

## Self-check

<details><summary>1. What should happen when the resolver reaches its soft token limit?</summary>

The next request tells the model to propose what it is sure of and finish. If it continues to the hard limit, code stops the loop, keeps the best accepted fixes, and sends the run to review with `resolver_budget`.
</details>

<details><summary>2. Why are the resolver's outputs "proposals" and not edits?</summary>

The agent reads untrusted text and can be wrong. Code validates each proposal against every rule on its field, and accepts it only if all pass. So the agent cannot apply a value that a check rejects. A wrong value that passes every check would still be accepted; the confidence score and the reviewer are the next guards.
</details>

<details><summary>3. A tool inside the loop makes its own model call. What must you do?</summary>

Count its tokens, time and cost against the same budget, and record its own span in the trace. Otherwise both the budget and the cost report are wrong.
</details>
