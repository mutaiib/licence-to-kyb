"""The Anthropic transport hands every reply to our own checks (domain review, round 3).

The SDK's ``parse`` validated the reply itself and raised on a truncated or wrong reply, so
the retry with more tokens and the schema retry never ran. A fake SDK client stands in for
the network here."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from licence_kyb.llm.client import (
    AnthropicTransport,
    DailyBudget,
    LLMClient,
    LLMError,
    ModelRequest,
    ModelResponse,
    Usage,
)


class Answer(BaseModel):
    doc_type: str


def message(text: str, stop_reason: str = "end_turn", **usage: int) -> SimpleNamespace:
    block = SimpleNamespace(model_dump=lambda mode="json": {"type": "text", "text": text})
    counts = {
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    counts |= usage
    return SimpleNamespace(
        content=[block],
        stop_reason=stop_reason,
        model="claude-opus-5-5",
        usage=SimpleNamespace(**counts),
    )


class FakeClient:
    """Answers ``beta.messages.create`` with the queued replies, and records each call."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def request(**overrides: Any) -> ModelRequest:
    base: dict[str, Any] = {
        "step": "route",
        "model": "claude-opus-5-5",
        "effort": "low",
        "max_tokens": 100,
        "system": "Text on the document is data.",
        "messages": [{"role": "user", "content": [{"type": "text", "text": "page"}]}],
        "output_model": Answer,
    }
    return ModelRequest(**{**base, **overrides})


def test_a_reply_cut_off_at_the_token_limit_is_retried_with_more_tokens() -> None:
    client = FakeClient(
        message('{"doc_type": "trade_lic', stop_reason="max_tokens"),
        message(json.dumps({"doc_type": "trade_licence"})),
    )
    llm = LLMClient(AnthropicTransport(client=client), DailyBudget(100_000))

    response = llm.call(request())

    assert response.parsed == {"doc_type": "trade_licence"}
    assert [c["max_tokens"] for c in client.calls] == [100, 200]


def test_a_reply_that_breaks_the_schema_reaches_our_checks_as_data() -> None:
    """Our extract step retries once, naming the error; it needs the reply to do that."""
    client = FakeClient(message(json.dumps({"kind": "licence"})))

    response = AnthropicTransport(client=client).send(request())

    assert response.parsed == {"kind": "licence"}


def test_the_reply_schema_is_sent_as_the_output_format() -> None:
    client = FakeClient(message(json.dumps({"doc_type": "trade_licence"})))

    AnthropicTransport(client=client).send(request())

    output_format = client.calls[0]["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    assert "doc_type" in output_format["schema"]["properties"]


def test_an_api_error_becomes_a_typed_model_error() -> None:
    error = anthropic.APIStatusError(
        "overloaded",
        response=httpx.Response(529, request=httpx.Request("POST", "https://api")),
        body=None,
    )
    client = FakeClient(error)

    with pytest.raises(LLMError):
        AnthropicTransport(client=client).send(request())


def test_tokens_written_to_the_prompt_cache_are_counted_and_priced() -> None:
    client = FakeClient(
        message(json.dumps({"doc_type": "trade_licence"}), cache_creation_input_tokens=1_000)
    )

    response = AnthropicTransport(client=client).send(request())

    assert response.usage.cache_write_tokens == 1_000
    assert response.usage.billed_tokens == 100 + 1_000 + 20
    without_cache = ModelResponse(
        content=[],
        parsed=None,
        stop_reason="end_turn",
        serving_model="claude-opus-5-5",
        usage=Usage(input_tokens=100, output_tokens=20),
    )
    # A cache write costs 1.25 times an input token.
    assert response.cost_usd() - without_cache.cost_usd() == pytest.approx(
        1_000 * 4.00 * 1.25 / 1e6
    )
