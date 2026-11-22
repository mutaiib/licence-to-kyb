"""Spans for every step, model call and tool call (architecture §12).

Eval runs and app runs write the same span format. Attribute names follow the
OpenTelemetry GenAI semantic conventions, so a later OTLP export needs no renaming.
Raw tool results and the text the model saw are both kept, encrypted when a cipher is set.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

from licence_kyb.security import Cipher
from licence_kyb.store.db import Database

# "tool_call" is used from User Story 4 (the resolver's tools).
SpanKind = Literal["step", "model_call", "tool_call"]


@dataclass
class Span:
    span_id: str
    run_id: str | None
    kind: SpanKind
    name: str
    parent_id: str | None = None
    requested_model: str | None = None
    serving_model: str | None = None
    effort: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    prompt_hash: str | None = None
    error_code: str | None = None
    # Used from User Story 4: raw tool results and the text the model saw.
    raw_result: Any = None
    model_view: Any = None
    latency_ms: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)

    # Used from User Story 5 (the trace page) and a later OTLP export.
    def otel_attributes(self) -> dict[str, Any]:
        """The span as OpenTelemetry GenAI attributes."""
        attrs: dict[str, Any] = {
            "licence_kyb.span.kind": self.kind,
            "licence_kyb.run_id": self.run_id,
        }
        if self.kind == "model_call":
            attrs |= {
                "gen_ai.system": "anthropic",
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": self.requested_model,
                "gen_ai.response.model": self.serving_model,
                "gen_ai.usage.input_tokens": self.input_tokens,
                "gen_ai.usage.output_tokens": self.output_tokens,
            }
        if self.kind == "tool_call":
            attrs |= {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": self.name}
        if self.error_code:
            attrs["error.type"] = self.error_code
        return attrs | self.attributes


class Tracer:
    def __init__(self, db: Database, cipher: Cipher | None = None) -> None:
        self.db = db
        self.cipher = cipher

    @contextmanager
    def span(
        self, kind: SpanKind, name: str, *, run_id: str | None, parent: Span | None = None
    ) -> Iterator[Span]:
        span = Span(
            span_id=str(uuid.uuid4()),
            run_id=run_id,
            kind=kind,
            name=name,
            parent_id=parent.span_id if parent else None,
        )
        started = time.monotonic()
        try:
            yield span
        except Exception as exc:
            span.error_code = span.error_code or type(exc).__name__
            raise
        finally:
            span.latency_ms = int((time.monotonic() - started) * 1000)
            self._write(span)

    def _write(self, span: Span) -> None:
        def seal(value: Any) -> str | None:
            if value is None:
                return None
            text = json.dumps(value, ensure_ascii=False, default=str)
            return self.cipher.encrypt_text(text) if self.cipher else text

        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO spans (span_id, parent_id, run_id, kind, name, requested_model, "
                "serving_model, effort, input_tokens, output_tokens, thinking_tokens, "
                "cache_read_tokens, latency_ms, cost_usd, prompt_hash, error_code, "
                "raw_result_enc, model_view_enc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    span.span_id,
                    span.parent_id,
                    span.run_id,
                    span.kind,
                    span.name,
                    span.requested_model,
                    span.serving_model,
                    span.effort,
                    span.input_tokens,
                    span.output_tokens,
                    span.thinking_tokens,
                    span.cache_read_tokens,
                    span.latency_ms,
                    span.cost_usd,
                    span.prompt_hash,
                    span.error_code,
                    seal(span.raw_result),
                    seal(span.model_view),
                ),
            )

    # Used from User Story 5 (the trace API).
    def spans_for(self, run_id: str) -> list[dict[str, Any]]:
        """Spans for the trace API. Only non-personal columns are selected; raw tool results and
        model views are never returned, so the response cannot contain personal data."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT span_id, parent_id, kind, name, requested_model, serving_model, effort, "
                "input_tokens, output_tokens, thinking_tokens, cache_read_tokens, latency_ms, "
                "cost_usd, error_code, started_at FROM spans WHERE run_id = ? ORDER BY started_at",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]
