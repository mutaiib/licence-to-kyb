# ADR-001 — A workflow with one bounded agent

## Status

Accepted.

## Context

The system must turn a trade licence into a validated KYB form. We considered three designs:

1. one agent with every tool
2. several cooperating agents
3. a fixed workflow

## Decision

Use a fixed workflow in LangGraph. It has one agent node, the resolver, that runs only when a value fails a check that reading again can fix.

## Reasons

- **The steps are known before the document is read:** check, read, classify, extract, validate, decide, review, fill, submit. A workflow encodes known steps directly, and each step's output can be tested.
- **Reliability multiplies across model steps.** At 95% per step, ten model steps succeed about 60% of the time. Every decision moved into code removes one factor.
- **The only step that cannot be scripted is how to investigate a failed value.** That step gets the agent.
- **No condition for several agents applies.** The work fits in one context, it needs one permission set, and it gains nothing from running in parallel.

## Consequences

- Cost and latency stay predictable for most runs. The agent adds cost only to runs with fixable failures.
- The eval suite measures the agent's contribution (resolver on vs. off) and the second extraction pass's contribution (one pass vs. two). Any part whose measured contribution does not justify its cost is removed.
