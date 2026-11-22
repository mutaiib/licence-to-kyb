# ADR-002 — Call the model with the official SDK inside graph nodes

## Status

Accepted. Amended by [ADR-004](ADR-004-provider-neutral-model-calls.md): the provider is now chosen by configuration (a model profile), so changing provider no longer means changing a module.

## Context

LangGraph can call models through LangChain wrappers, or nodes can call the official `anthropic` SDK directly.

## Decision

- LangGraph is responsible for orchestration: the graph, state, checkpoints and interrupts.
- Every model call goes through one `LLMClient` wrapper over the official `anthropic` Python SDK.

## Reasons

- **The request and response stay fully visible:** structured outputs, `strict` tools, effort, caching, stop reasons and fallbacks. The tool loop in the resolver is plain code that a reader can follow step by step.
- **One seam for tests.** Tests replace `LLMClient` with recorded responses, so no network is needed.
- **One place records tokens, cache reads and latency** for tracing.

## Consequences

- The tool loop is written by hand, about 150 lines.
- Changing model provider means changing one module.
