"""Model calls to any OpenAI-compatible chat server (ADR-004; contracts/model-calls.md,
"Providers").

llama.cpp's ``llama-server``, Ollama, vLLM, LM Studio and a LiteLLM proxy all serve
``POST /v1/chat/completions``. This transport turns our requests (Anthropic-style content
blocks) into that format and turns the reply back, so ``LLMClient`` and the nodes do not
change.

Reading order: ``send`` builds the body (``_body``), posts it, and reads the reply
(``_response``). Each conversion is one small function.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from licence_kyb.llm.client import LLMError, ModelRequest, ModelResponse, Usage

FINISH_TO_STOP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "refusal",
}
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
"""A busy or failing server: tried again after a short wait."""


class OpenAICompatibleTransport:
    def __init__(
        self,
        *,
        client: httpx.Client,
        vision: bool,
        prices: tuple[float, float, float] = (0.0, 0.0, 0.0),
        retry_delays: tuple[float, ...] = (1.0, 4.0),
    ) -> None:
        """``client`` carries the base URL (ending in ``/v1``), any API key header and the
        timeout. ``vision``: whether the model reads images; if not, page images are left
        out (the OCR text is in every prompt). ``prices``: USD per million input, output and
        cached tokens. ``retry_delays``: seconds to wait before each new try after a busy or
        failing server; one try more than there are delays."""
        self._client = client
        self._vision = vision
        self._prices = prices
        self._retry_delays = retry_delays

    @classmethod
    def for_url(
        cls,
        base_url: str,
        *,
        vision: bool,
        api_key: str | None = None,
        timeout_seconds: float = 900.0,
        prices: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> OpenAICompatibleTransport:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout_seconds)
        return cls(client=client, vision=vision, prices=prices)

    def send(self, req: ModelRequest) -> ModelResponse:
        body = self._body(req)
        for delay in (*self._retry_delays, None):
            try:
                http = self._client.post("/chat/completions", json=body)
                if http.status_code in RETRY_STATUSES and delay is not None:
                    time.sleep(delay)
                    continue
                http.raise_for_status()
            except httpx.HTTPError as exc:
                raise LLMError(f"the model server failed: {exc}") from exc
            return self._response(req, http.json())
        raise AssertionError("unreachable: the last try returns or raises")

    # ------------------------------------------------------------------ request
    def _body(self, req: ModelRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": req.system}]
        for message in req.messages:
            messages.extend(self._messages(message))
        body: dict[str, Any] = {
            "model": req.model,
            "max_tokens": req.max_tokens,
            "messages": messages,
        }
        if req.output_model is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": req.output_model.__name__,
                    "schema": strict_schema(req.output_model.model_json_schema()),
                    "strict": True,
                },
            }
        if req.tools:
            body["tools"] = [_tool(t) for t in req.tools]
            body["tool_choice"] = "auto"
        return body

    def _messages(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """One of our messages becomes one or more OpenAI messages: tool results are
        separate ``tool`` messages, and tool calls ride on the assistant message."""
        content = message["content"]
        if isinstance(content, str):
            return [{"role": message["role"], "content": content}]
        parts: list[dict[str, Any]] = []
        calls: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        for block in content:
            kind = block["type"]
            if kind == "text":
                parts.append({"type": "text", "text": block["text"]})
            elif kind == "image" and self._vision:
                source = block["source"]
                url = f"data:{source['media_type']};base64,{source['data']}"
                parts.append({"type": "image_url", "image_url": {"url": url}})
            elif kind == "tool_use":
                calls.append(
                    {
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    }
                )
            elif kind == "tool_result":
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": _text_of(block["content"]),
                    }
                )
        out: list[dict[str, Any]] = []
        if parts or calls:
            entry: dict[str, Any] = {"role": message["role"], "content": parts or None}
            if calls:
                entry["tool_calls"] = calls
            out.append(entry)
        return out + results

    # ------------------------------------------------------------------ reply
    def _response(self, req: ModelRequest, data: dict[str, Any]) -> ModelResponse:
        choice = data["choices"][0]
        message = choice["message"]
        stop_reason = FINISH_TO_STOP.get(choice.get("finish_reason") or "stop", "end_turn")
        if message.get("refusal"):  # the model declined: a refusal, not a broken reply
            stop_reason = "refusal"
        text = message.get("content") or ""
        content: list[dict[str, Any]] = [{"type": "text", "text": text}] if text else []
        for call in message.get("tool_calls") or []:
            content.append(
                {
                    "type": "tool_use",
                    "id": call["id"],
                    "name": call["function"]["name"],
                    "input": json.loads(call["function"]["arguments"] or "{}"),
                }
            )
        parsed = None
        if req.output_model is not None and stop_reason == "end_turn":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                # The server enforces the schema while it generates, so a complete reply
                # that is not JSON means the server is not doing that: stop, do not guess.
                raise LLMError("the model reply is not JSON") from exc
        usage = data.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        return ModelResponse(
            content=content,
            parsed=parsed,
            stop_reason=stop_reason,
            serving_model=req.model,  # the profile's name; the server's label is a file path
            usage=Usage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                cache_read_tokens=int(cached or 0),
            ),
            prices=self._prices,
        )


def strict_schema(schema: Any) -> Any:
    """The schema as a strict server needs it: every object lists all its properties as
    required and allows no others. An optional property already allows null, so making it
    required changes nothing for our replies. Defaults are dropped (strict mode rejects them)."""
    if isinstance(schema, list):
        return [strict_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: strict_schema(v) for k, v in schema.items() if k != "default"}
    if "properties" in out:
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    return out


def _tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


def _text_of(content: Any) -> str:
    """A tool result is a string or a list of text blocks."""
    if isinstance(content, str):
        return content
    return "\n".join(block.get("text", "") for block in content)
