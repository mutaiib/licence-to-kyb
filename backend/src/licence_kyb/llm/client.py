"""The single seam for every model call (ADR-002, contracts/model-calls.md).

``LLMClient`` adds the cross-cutting rules on top of a transport:
- the daily token budget is checked before every call (FR-040);
- ``refusal`` raises ``ModelRefusedError``; ``max_tokens`` is retried once with a doubled limit;
- usage, serving model and cost are returned for tracing and the budget.

Transports: ``AnthropicTransport`` (the official SDK), ``ReplayTransport`` (recorded
responses, used by every offline test) and ``RecordingTransport`` (records live calls).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from licence_kyb.schemas.results import ReasonCode

# USD per million tokens (input, output, cache read). Thinking tokens bill as output and are
# already included in ``output_tokens``.
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    reason_code: ReasonCode = "processing_failed"


class BudgetExhaustedError(LLMError):
    reason_code: ReasonCode = "budget_exhausted"


class ModelRefusedError(LLMError):
    reason_code: ReasonCode = "processing_failed"


class OutputTruncatedError(LLMError):
    reason_code: ReasonCode = "processing_failed"


class MissingRecordingError(LLMError):
    def __init__(self, request_hash: str) -> None:
        super().__init__(f"no recorded response for request {request_hash}")
        self.request_hash = request_hash


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def billed_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ModelRequest:
    step: str
    model: str
    effort: str
    max_tokens: int
    system: str
    messages: list[dict[str, Any]]
    output_model: type[BaseModel] | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    cache_system: bool = True


@dataclass(frozen=True)
class ModelResponse:
    content: list[dict[str, Any]]
    parsed: dict[str, Any] | None
    stop_reason: str
    serving_model: str
    usage: Usage
    latency_ms: int = 0

    def parsed_as[M: BaseModel](self, model: type[M]) -> M:
        if self.parsed is None:
            raise ValueError("the response has no parsed output")
        return model.model_validate(self.parsed)

    def cost_usd(self) -> float:
        price_in, price_out, price_cache = PRICES.get(self.serving_model, PRICES["claude-opus-5-5"])
        uncached = max(self.usage.input_tokens - self.usage.cache_read_tokens, 0)
        return (
            uncached * price_in
            + self.usage.output_tokens * price_out
            + self.usage.cache_read_tokens * price_cache
        ) / 1_000_000


def is_fallback(req: ModelRequest, resp: ModelResponse) -> bool:
    """A server-side fallback served the call (FR-041): the run cannot be ``ready``."""
    return bool(resp.serving_model) and resp.serving_model != req.model


def request_hash(req: ModelRequest) -> str:
    """Stable hash of everything that can change the answer."""
    body = {
        "model": req.model,
        "effort": req.effort,
        "max_tokens": req.max_tokens,
        "system": req.system,
        "messages": req.messages,
        "tools": req.tools,
        "output": None if req.output_model is None else req.output_model.model_json_schema(),
    }
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class Transport(Protocol):
    def send(self, req: ModelRequest) -> ModelResponse: ...


class DailyBudget:
    """Counts billed tokens for the current day. Thread-safe."""

    def __init__(self, limit_tokens: int) -> None:
        self.limit_tokens = limit_tokens
        self.used_tokens = 0
        self._lock = threading.Lock()

    @property
    def remaining(self) -> int:
        return max(self.limit_tokens - self.used_tokens, 0)

    def check(self, needed: int) -> None:
        if needed > self.remaining:
            raise BudgetExhaustedError("the daily token budget is used")

    def charge(self, tokens: int) -> None:
        with self._lock:
            self.used_tokens += tokens

    def reset(self) -> None:
        with self._lock:
            self.used_tokens = 0


class LLMClient:
    def __init__(self, transport: Transport, budget: DailyBudget) -> None:
        self.transport = transport
        self.budget = budget

    def call(self, req: ModelRequest) -> ModelResponse:
        result = self._send(req)
        if result.stop_reason == "max_tokens":
            result = self._send(replace(req, max_tokens=req.max_tokens * 2))
            if result.stop_reason == "max_tokens":
                raise OutputTruncatedError("the reply was cut off twice at the token limit")
        if result.stop_reason == "refusal":
            raise ModelRefusedError("the model declined the request")
        return result

    def _send(self, req: ModelRequest) -> ModelResponse:
        # Pre-check with a conservative estimate; the exact usage is charged afterwards.
        self.budget.check(req.max_tokens // 4)
        started = time.monotonic()
        result = self.transport.send(req)
        self.budget.charge(result.usage.billed_tokens)
        if not result.latency_ms:
            result = replace(result, latency_ms=int((time.monotonic() - started) * 1000))
        return result


class ReplayTransport:
    """Recorded responses keyed by request hash. Never touches the network."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, req: ModelRequest) -> Path:
        return self.directory / f"{req.step}-{request_hash(req)[:24]}.json"

    def save(self, req: ModelRequest, resp: ModelResponse) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {
            "request_hash": request_hash(req),
            "step": req.step,
            "content": resp.content,
            "parsed": resp.parsed,
            "stop_reason": resp.stop_reason,
            "serving_model": resp.serving_model,
            "usage": resp.usage.__dict__,
            "latency_ms": resp.latency_ms,
        }
        self.path_for(req).write_text(json.dumps(record, ensure_ascii=False, indent=2), "utf-8")

    def send(self, req: ModelRequest) -> ModelResponse:
        path = self.path_for(req)
        if not path.exists():
            raise MissingRecordingError(request_hash(req))
        record = json.loads(path.read_text("utf-8"))
        return ModelResponse(
            content=record["content"],
            parsed=record["parsed"],
            stop_reason=record["stop_reason"],
            serving_model=record["serving_model"],
            usage=Usage(**record["usage"]),
            latency_ms=record.get("latency_ms", 0),
        )


class RecordingTransport:
    """Sends live, then stores the response for replay. Only for synthetic documents."""

    def __init__(self, live: Transport, replay: ReplayTransport) -> None:
        self.live = live
        self.replay = replay

    def send(self, req: ModelRequest) -> ModelResponse:
        resp = self.live.send(req)
        self.replay.save(req, resp)
        return resp


class AnthropicTransport:
    """The official SDK (``client.beta.messages``), with server-side refusal fallback."""

    def __init__(self, api_key: str | None = None) -> None:
        import anthropic  # noqa: PLC0415 - lazy: offline tests never import the live SDK path

        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def send(self, req: ModelRequest) -> ModelResponse:
        system: list[dict[str, Any]] = [{"type": "text", "text": req.system}]
        if req.cache_system:
            system[0]["cache_control"] = {"type": "ephemeral"}
        kwargs: dict[str, Any] = {
            "model": req.model,
            "max_tokens": req.max_tokens,
            "system": system,
            "messages": req.messages,
            "output_config": {"effort": req.effort},
            "betas": [FALLBACK_BETA],
            "fallbacks": "default",
        }
        started = time.monotonic()
        if req.output_model is not None:
            msg = self._client.beta.messages.parse(output_format=req.output_model, **kwargs)
            parsed_obj = getattr(msg, "parsed_output", None)
            parsed = parsed_obj.model_dump(mode="json") if parsed_obj is not None else None
        else:
            if req.tools:
                kwargs["tools"] = req.tools
                kwargs["tool_choice"] = {"type": "auto"}
            msg = self._client.beta.messages.create(**kwargs)
            parsed = None
        latency = int((time.monotonic() - started) * 1000)
        usage = msg.usage
        details = getattr(usage, "output_tokens_details", None)
        return ModelResponse(
            content=[block.model_dump(mode="json") for block in msg.content],
            parsed=parsed,
            stop_reason=str(msg.stop_reason),
            serving_model=str(msg.model),
            usage=Usage(
                input_tokens=usage.input_tokens + (usage.cache_read_input_tokens or 0),
                output_tokens=usage.output_tokens,
                thinking_tokens=getattr(details, "thinking_tokens", 0) or 0,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
            ),
            latency_ms=latency,
        )
