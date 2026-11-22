# 10 — Observability, cost and latency

## In one minute

A trace is a tree of spans, one per step, model call and tool call. A bad result is debugged by following it to the span that caused it.

Cost and latency are design inputs:
- Count tokens before you apply a price.
- Budget time per stage.
- Measure before you set limits.

## Rules

- **Record a span for each call,** with:
  - the step
  - the requested and serving model, and the effort
  - input, output, thinking and cache-read tokens
  - latency and cost
  - the prompt hash
  - for tools: the raw result **and** the text the model saw, plus the error code
- **Use one trace format** for eval runs and app runs. Use the OpenTelemetry GenAI attribute names, so exporting later needs no renaming.
- **Watch for drift with aggregate signals:** refusal rate, fallback rate, review rate, cost per day and the remaining budget. No single trace shows drift.
- **Cost arithmetic.** Here, thinking cannot be turned off and bills as output.
  - Example: 10k input × $4/M plus 4k output × $20/M ≈ $0.12 for one extract pass.
  - State the worst case as a true upper bound.
- **Caching:**
  - Put the stable prefix (system prompt, profile, schema) first, marked with `cache_control`, and the document after it.
  - Check `cache_read_input_tokens` to confirm the cache works.
- **Model choice:** before you build a cascade of models, measure the strong model at lower effort. Then measure cheaper models only where quality holds.
- **Latency:**
  - Give each stage a budget.
  - Measure throughput (tokens per second) before you set any time limit.
  - Mark the limits provisional until then.
- **Fallbacks:** record the model that actually served each call. A fallback can change behaviour that the thresholds were calibrated on.

## In this repository

- **Spans and the daily summary:** [architecture §12](../architecture.md#12-tracing), and `GET /api/metrics/summary` ([HTTP contract](../../specs/001-licence-to-kyb/contracts/http-api.md)).
- **The cost estimate and latency budget:** [plan](../../specs/001-licence-to-kyb/plan.md#cost-estimate).
- **The throughput probe:** task T034. The experiments list cheaper configurations ([experiments](../experiments.md)).
- **Fallback handling:** FR-041, and the `fallback_model` reason.

## Mistakes to avoid

- **A cost target that the design's own estimate already misses.** Found in review: the $0.15 target ignored thinking tokens. It was re-estimated at about $0.23 for a typical run, with a target below $0.40.
- **A per-stage time budget that needs an impossible throughput.** Found in review: an 18 s extract stage needed about 220 tokens per second.
- **Recording only one copy of a tool result.** The difference between the raw result and what the model saw often explains a failure.

## Self-check

<details><summary>1. A tool call fails in production. Which fields in the trace help you most?</summary>

- the tool-call span's `error_code`
- the raw result, with the exception masked
- what the model saw
- the next model span, to see whether the model followed `next_action`
</details>

<details><summary>2. Why do cache reads stay at zero, and how do you fix it?</summary>

Something in the prefix changes on each request, such as a timestamp, unsorted JSON or a changing tool list. Move every changing part after the last `cache_control` breakpoint.
</details>

<details><summary>3. How do you set the resolver's wall-time limit responsibly?</summary>

Measure output throughput and per-call latency with a probe first. Then size the limit to the expected number of turns and vision re-reads, and check it against the overall p95 target.
</details>
