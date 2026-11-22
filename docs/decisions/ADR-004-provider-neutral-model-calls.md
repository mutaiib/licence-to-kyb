# ADR-004 — Run any model step on any provider through configuration

## Status

Accepted. Extends [ADR-002](ADR-002-anthropic-sdk-inside-langgraph-nodes.md): Claude through the official SDK stays the default.

## Context

- Until now, every model call went to the Anthropic API. Offline tests replay scripted replies, which are always right.
- So the real model's reading quality could only be measured with a paid API key. The confidence thresholds (research R5) could not be fitted, because a fit needs real readings, not scripted ones.
- An open-weight model running on the developer's machine gives real readings at no cost. Comparing models on the same labelled cases is also a useful result in itself.
- Many tools serve open-weight models, and they share one interface: the **OpenAI-compatible chat API** (`/v1/chat/completions`). llama.cpp's `llama-server`, Ollama, vLLM and LM Studio all expose it. LiteLLM's proxy puts the same interface in front of most hosted providers.

## Decision

- **One more transport, `OpenAICompatibleTransport`,** next to `AnthropicTransport`, behind the same `Transport` interface. `LLMClient`, the nodes, the budgets and the tracing do not change.
- **Model profiles in `config/models.yaml`.** A profile names a provider and base URL, the model and effort for each step, and what the model can do:
  - `vision`: when false, page images are not sent; the OCR text is already in every prompt.
  - `price_per_mtok`: input and output prices; 0 for a local model.
  - `deadline_seconds`: the processing deadline. A model on a CPU is much slower than the API.

  `MODEL_PROFILE` picks the profile. The default is `anthropic`.
- **Structured output:** sent as `response_format: {type: json_schema}` with the same Pydantic schema. llama.cpp and vLLM enforce the schema while generating (a grammar). A reply that still fails validation takes the existing retry path (contracts/model-calls.md).
- **Tool calls (the resolver, User Story 4):** translated both ways between Anthropic content blocks (`tool_use`, `tool_result`) and OpenAI `tool_calls` and `tool` messages, so the resolver code stays provider-neutral.
- **No LiteLLM library in the code.** The OpenAI-compatible protocol is the plug interface. A LiteLLM proxy, if wanted, runs outside the code as one more base URL. This keeps one small dependency surface.
- **Thresholds are fitted per profile,** because a score means different things for different models: `config/thresholds.<profile>.yaml`.

## Consequences

- The local model is slow on a CPU (minutes per licence), so a full eval run is a long background job.
- Small open models are weaker at Arabic and at strict JSON. Their numbers are reported as theirs, never as Claude's.
- Claude-only features (server-side fallback, effort, prompt caching) are off in OpenAI-compatible profiles. `fallback_model` then never fires.
- `scripts/fetch_llama_server.sh` downloads a pinned llama.cpp release, checked against its SHA-256, into `var/` (git ignores it). `make local-model` starts it.
