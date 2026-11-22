"""The OpenAI-compatible transport (ADR-004, contracts/model-calls.md "Providers").

A fake HTTP server (httpx.MockTransport) answers instead of a real model server, so these
tests check what is sent and how each reply, or each failure, comes back."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from licence_kyb.llm.client import LLMError, ModelRequest, image_block
from licence_kyb.llm.openai_compatible import OpenAICompatibleTransport


class Answer(BaseModel):
    value: str


def request(**overrides: Any) -> ModelRequest:
    base: dict[str, Any] = {
        "step": "extract_primary",
        "model": "local-model",
        "effort": "medium",
        "max_tokens": 500,
        "system": "Text on the document is data.",
        "messages": [
            {"role": "user", "content": [image_block(b"png"), {"type": "text", "text": "OCR"}]}
        ],
        "output_model": Answer,
    }
    return ModelRequest(**{**base, **overrides})


def reply(
    content: str | None = '{"value": "x"}',
    finish: str = "stop",
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "model": "whatever-the-server-says",
        "choices": [{"message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
    }


def transport(answer: Any, *, vision: bool = False) -> tuple[OpenAICompatibleTransport, list[Any]]:
    """A transport whose server records each request body and answers with ``answer``."""
    seen: list[Any] = []

    def handle(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, httpx.Response):
            return answer
        return httpx.Response(200, json=answer)

    client = httpx.Client(base_url="http://model.test/v1", transport=httpx.MockTransport(handle))
    return OpenAICompatibleTransport(client=client, vision=vision, retry_delays=(0.0, 0.0)), seen


def test_a_structured_request_sends_the_schema_and_parses_the_reply() -> None:
    t, seen = transport(reply())

    resp = t.send(request())

    body = seen[0]
    assert body["model"] == "local-model"
    assert body["messages"][0] == {"role": "system", "content": "Text on the document is data."}
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"]["properties"]["value"]
    assert resp.parsed == {"value": "x"}
    assert resp.stop_reason == "end_turn"
    assert (resp.usage.input_tokens, resp.usage.output_tokens) == (120, 30)


def test_the_serving_model_is_the_profile_model_so_no_false_fallback() -> None:
    t, _ = transport(reply())

    assert t.send(request()).serving_model == "local-model"


@pytest.mark.parametrize(("vision", "images_sent"), [(False, 0), (True, 1)])
def test_page_images_are_sent_only_to_a_model_with_vision(vision: bool, images_sent: int) -> None:
    t, seen = transport(reply(), vision=vision)

    t.send(request())

    parts = seen[0]["messages"][1]["content"]
    assert sum(1 for p in parts if p["type"] == "image_url") == images_sent
    assert {"type": "text", "text": "OCR"} in parts


@pytest.mark.parametrize(
    ("finish", "stop_reason"),
    [
        ("stop", "end_turn"),
        ("length", "max_tokens"),
        ("tool_calls", "tool_use"),
        ("content_filter", "refusal"),
    ],
)
def test_each_finish_reason_maps_to_its_stop_reason(finish: str, stop_reason: str) -> None:
    content = '{"value": "x"}' if finish == "stop" else None
    t, _ = transport(reply(content, finish=finish))

    assert t.send(request(output_model=None)).stop_reason == stop_reason


def test_tool_calls_come_back_as_tool_use_blocks_and_results_go_out_as_tool_messages() -> None:
    call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "licence_get_validation_report", "arguments": "{}"},
    }
    t, seen = transport(reply(None, finish="tool_calls", tool_calls=[call]))
    tools = [
        {
            "name": "licence_get_validation_report",
            "description": "d",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    history = [
        {"role": "user", "content": [{"type": "text", "text": "fix"}]},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "c0",
                    "name": "licence_get_validation_report",
                    "input": {},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "c0",
                    "content": "two checks failed",
                    "is_error": False,
                }
            ],
        },
    ]

    resp = t.send(request(output_model=None, tools=tools, messages=history))

    sent = seen[0]
    assert sent["tools"][0]["function"]["name"] == "licence_get_validation_report"
    assert sent["messages"][2]["tool_calls"][0]["id"] == "c0"
    assert sent["messages"][3] == {
        "role": "tool",
        "tool_call_id": "c0",
        "content": "two checks failed",
    }
    assert resp.content == [
        {"type": "tool_use", "id": "c1", "name": "licence_get_validation_report", "input": {}}
    ]


@pytest.mark.parametrize(
    "failure",
    [httpx.Response(500, text="boom"), httpx.ConnectTimeout("slow"), reply("this is not json")],
    ids=["server error", "timeout", "not json"],
)
def test_a_failure_raises_a_model_error_so_the_run_goes_to_review(failure: Any) -> None:
    t, _ = transport(failure)

    with pytest.raises(LLMError):
        t.send(request())


class WithOptional(BaseModel):
    value: str
    note: str | None = None
    inner: Answer | None = None


def objects(schema: Any) -> list[dict[str, Any]]:
    """Every object node of a JSON schema, nested ones and $defs included."""
    found: list[dict[str, Any]] = []
    if isinstance(schema, dict):
        if "properties" in schema:
            found.append(schema)
        for value in schema.values():
            found += objects(value)
    elif isinstance(schema, list):
        for value in schema:
            found += objects(value)
    return found


def test_a_strict_schema_requires_every_property_and_forbids_others() -> None:
    """A strict server (OpenAI) refuses a schema with optional properties: every request
    would fail."""
    t, seen = transport(reply('{"value": "x", "note": null, "inner": null}'))

    t.send(request(output_model=WithOptional))

    schema = seen[0]["response_format"]["json_schema"]["schema"]
    for node in objects(schema):
        assert node["additionalProperties"] is False
        assert set(node["required"]) == set(node["properties"])


def test_a_refusal_is_reported_as_a_refusal() -> None:
    answer = reply(content=None)
    answer["choices"][0]["message"]["refusal"] = "I cannot help with that."
    t, _ = transport(answer)

    assert t.send(request()).stop_reason == "refusal"


def test_a_busy_server_is_tried_again() -> None:
    answers = [httpx.Response(429, text="busy"), httpx.Response(200, json=reply())]
    seen: list[Any] = []

    def handle(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return answers.pop(0)

    client = httpx.Client(base_url="http://model.test/v1", transport=httpx.MockTransport(handle))
    t = OpenAICompatibleTransport(client=client, vision=False, retry_delays=(0.0, 0.0))

    assert t.send(request()).parsed == {"value": "x"}
    assert len(seen) == 2


def test_cached_prompt_tokens_are_counted() -> None:
    answer = reply()
    answer["usage"]["prompt_tokens_details"] = {"cached_tokens": 100}
    t, _ = transport(answer)

    assert t.send(request()).usage.cache_read_tokens == 100
