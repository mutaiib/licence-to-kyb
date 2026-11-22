# 14 — Model providers and local models

## In one minute

Put every model call behind one small interface, and choose the provider by configuration. Then the same code, tests and evals run on a paid API, a cheaper hosted model, or an open-weight model on your own machine. The interface most servers share is the OpenAI-compatible chat API, so one more transport covers almost all of them.

## Rules

- **One client, many transports.** Nodes call `LLMClient.call(request)`. A `Transport` turns that request into one provider's API and back. Retries, budgets and tracing live in the client, once ([ADR-004](../decisions/ADR-004-provider-neutral-model-calls.md)).
- **Choose by configuration, never by code.** A model profile names the provider, the model for each step, and what the model can do. `MODEL_PROFILE=local` switches everything.
- **Declare capabilities instead of hoping.**
  - `vision: false` means the transport leaves page images out; the OCR text is in every prompt anyway.
  - `price_per_mtok` makes cost honest: 0 for a local model, never a guessed price.
  - `deadline_seconds` and `resolver_seconds` give a slow model the time it needs.
- **Ask the server to enforce the schema.** `response_format: json_schema` makes llama.cpp and vLLM generate only valid JSON (a grammar). A reply that is still not JSON is a provider fault, so stop and send the run to a person.
- **Map stop reasons explicitly.** `length` is a cut-off (retry with more tokens), `content_filter` is a refusal, `tool_calls` is a tool turn.
- **Never report one model's numbers as another's.** Every eval report names the model of each step. Fit confidence thresholds per profile: a score means different things for different models.
- **A plug-in framework is optional.** LiteLLM can sit in front as a proxy (one more base URL). A library dependency is not needed for one small transport.

## In this project

| What | Where |
|---|---|
| The interface and the Anthropic transport | `backend/src/licence_kyb/llm/client.py` |
| The OpenAI-compatible transport (JSON schema, tools both ways, stop reasons) | `backend/src/licence_kyb/llm/openai_compatible.py` |
| Profiles: `anthropic` (default) and `local` | `backend/config/models.yaml` |
| Choosing the transport for the active profile | `backend/src/licence_kyb/llm/select.py` |
| A pinned llama.cpp server, and `make local-model` | `scripts/fetch_llama_server.sh`, `Makefile` |
| Per-profile thresholds | `backend/config/thresholds.<profile>.yaml` (written by `scripts/calibrate.py`) |

## Self-check

<details><summary>1. A local text-only model gets a request with three page images. What should happen?</summary>

The transport leaves the images out, because the profile says `vision: false`. The prompt already holds the OCR text. The resolver also does not offer the vision re-read tool to that model.
</details>

<details><summary>2. Why not reuse the Claude thresholds for a local model?</summary>

A confidence score combines signals whose meaning depends on the model: how often its two readings agree, how often its quotes match. Thresholds fitted on one model's readings do not hold for another, so each profile gets its own fit.
</details>

<details><summary>3. A local run shows a cost of $0.52. What is wrong?</summary>

The cost came from a default price table for a model that did not serve the call. A profile must state its own price (0 for a local model), and a demo or scripted run must cost 0.
</details>
