"""The processing pipeline for one run (architecture §4; tasks T051).

Graph (User Story 1 scope):
    preprocess → route → extract → validate → map_form → decide → persist
with short-cuts from route and extract to ``decide`` when there is nothing to extract.

Nodes are pure except ``persist``, which writes keyed, idempotent records. Checkpoints are
encrypted (EncryptedSerializer + the rotating Fernet cipher), because the state holds
personal data from the document.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from licence_kyb.clock import Clock, SystemClock
from licence_kyb.config import APPLICANT_NAME_THRESHOLD, ModelsConfig, models_config
from licence_kyb.graph import thread_config
from licence_kyb.llm.client import LLMClient, ModelRequest, ModelResponse
from licence_kyb.llm.prompts import prompt_hash
from licence_kyb.nodes.extract import build_extract_request, extract_licence
from licence_kyb.nodes.intake import IntakeResult, IntakeService
from licence_kyb.nodes.map_form import build_form
from licence_kyb.nodes.preprocess import PageSet, Word, preprocess_file
from licence_kyb.nodes.route import build_route_request, route_document
from licence_kyb.profiles import load_profile
from licence_kyb.registry import MockRegistry
from licence_kyb.rules import RuleContext, run_rules
from licence_kyb.schemas.licence import CriticalFields, TradeLicenceExtraction
from licence_kyb.schemas.results import FILE_REASONS, RuleResult, reason_entry
from licence_kyb.security import Cipher
from licence_kyb.state import RunState
from licence_kyb.store.db import Database
from licence_kyb.tracing import Span, Tracer

STATUS_FOR_ROUTE = {
    "reject": "rejected",
    "needs_review": "awaiting_review",
    "ready": "awaiting_submit",
}


class FernetCheckpointCipher:
    """Adapts the rotating Fernet cipher to LangGraph's CipherProtocol."""

    def __init__(self, cipher: Cipher) -> None:
        self.cipher = cipher

    def encrypt(self, plaintext: bytes) -> tuple[str, bytes]:
        return "fernet", self.cipher.encrypt(plaintext)

    def decrypt(self, ciphername: str, ciphertext: bytes) -> bytes:
        if ciphername != "fernet":
            raise ValueError(f"unknown checkpoint cipher {ciphername}")
        return self.cipher.decrypt(ciphertext)


@dataclass
class Deps:
    data_dir: Path
    cipher: Cipher
    llm: LLMClient
    clock: Clock = field(default_factory=SystemClock)
    registry: MockRegistry = field(default_factory=MockRegistry)
    models: ModelsConfig = field(default_factory=models_config)
    applicant_threshold: float = APPLICANT_NAME_THRESHOLD

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"


class Pipeline:
    def __init__(self, deps: Deps) -> None:
        self.deps = deps
        deps.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(deps.data_dir / "app.sqlite3")
        self.db.migrate()
        self.tracer = Tracer(self.db, deps.cipher)
        self.intake = IntakeService(self.db, deps.cipher, deps.files_dir)
        conn = sqlite3.connect(deps.data_dir / "checkpoints.sqlite3", check_same_thread=False)
        self.checkpointer = SqliteSaver(
            conn, serde=EncryptedSerializer(FernetCheckpointCipher(deps.cipher))
        )
        self.graph = self._build()

    # ------------------------------------------------------------------ public API
    def upload(self, data: bytes, *, applicant_name: str) -> IntakeResult:
        return self.intake.accept(data, applicant_name=applicant_name)

    def process(self, run_id: str) -> dict[str, Any]:
        run = self.db.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        applicant = self.deps.cipher.decrypt_text(run["applicant_name"])
        self.db.update_run(run_id, status="processing")
        state: dict[str, Any] = self.graph.invoke(
            {"run_id": run_id, "applicant_name": applicant}, thread_config(run_id)
        )
        return state

    def page_png(self, run_id: str, page: int) -> bytes:
        return self.deps.cipher.decrypt(
            (self.deps.files_dir / run_id / f"page-{page}.png.enc").read_bytes()
        )

    # ------------------------------------------------------------------ graph
    def _build(self) -> CompiledStateGraph[Any]:
        g: StateGraph[RunState] = StateGraph(RunState)
        g.add_node("preprocess", self._preprocess)
        g.add_node("route", self._route)
        g.add_node("extract", self._extract)
        g.add_node("validate", self._validate)
        g.add_node("map_form", self._map_form)
        g.add_node("decide", self._decide)
        g.add_node("persist", self._persist)
        g.add_edge(START, "preprocess")
        g.add_edge("preprocess", "route")
        g.add_conditional_edges(
            "route", self._after_route, {"extract": "extract", "decide": "decide"}
        )
        g.add_conditional_edges(
            "extract", self._after_extract, {"validate": "validate", "decide": "decide"}
        )
        g.add_edge("validate", "map_form")
        g.add_edge("map_form", "decide")
        g.add_edge("decide", "persist")
        g.add_edge("persist", END)
        return g.compile(checkpointer=self.checkpointer)

    def _preprocess(self, state: RunState) -> dict[str, Any]:
        run_id = state["run_id"]
        with self.tracer.span("step", "preprocess", run_id=run_id):
            data = self.intake.read_original(run_id)
            pages = preprocess_file(data, self.db.file_mime(run_id))
            folder = self.deps.files_dir / run_id
            for n, png in enumerate(pages.images, start=1):
                (folder / f"page-{n}.png.enc").write_bytes(self.deps.cipher.encrypt(png))
        return {
            "pages": {
                "page_count": pages.page_count,
                "qr_payload": pages.qr_payload,
                "source": pages.source,
                "words": [asdict(w) for w in pages.words],
            }
        }

    def _pages(self, state: RunState) -> PageSet:
        stored = state["pages"]
        return PageSet(
            page_count=stored["page_count"],
            words=[Word.from_dict(w) for w in stored["words"]],
            qr_payload=stored["qr_payload"],
        )

    def _route(self, state: RunState) -> dict[str, Any]:
        run_id = state["run_id"]
        pages = self._pages(state)
        request = build_route_request(self.page_png(run_id, 1), pages.text, self.deps.models.route)
        with self.tracer.span("step", "route", run_id=run_id) as step:
            outcome = route_document(self.deps.llm, request, pages.text)
            if outcome.response is not None:
                self._trace_call(run_id, step, request, outcome.response)
        return {
            "route": {"doc_type": outcome.doc_type, "authority": outcome.authority},
            "reasons": [reason_entry(code) for code in outcome.reasons],
        }

    @staticmethod
    def _after_route(state: RunState) -> Literal["extract", "decide"]:
        return "extract" if state["route"]["doc_type"] == "trade_licence" else "decide"

    def _extract(self, state: RunState) -> dict[str, Any]:
        run_id = state["run_id"]
        pages = self._pages(state)
        authority = state["route"]["authority"]
        profile = load_profile(authority)
        images = [self.page_png(run_id, n) for n in range(1, pages.page_count + 1)]
        primary = build_extract_request(
            step="extract_primary",
            output=TradeLicenceExtraction,
            pages_png=images,
            ocr_text=pages.text,
            profile=profile,
            cfg=self.deps.models.extract_primary,
        )
        secondary = build_extract_request(
            step="extract_secondary",
            output=CriticalFields,
            pages_png=images,
            ocr_text=pages.text,
            profile=profile,
            cfg=self.deps.models.extract_secondary,
        )
        with self.tracer.span("step", "extract", run_id=run_id) as step:
            out = extract_licence(self.deps.llm, primary, secondary)
            for req, resp in out.responses:
                self._trace_call(run_id, step, req, resp)
        reasons = list(state.get("reasons", []))
        for code in out.reasons:
            reasons.append(reason_entry(code))
        return {
            "extraction": out.primary.model_dump(mode="json") if out.primary else {},
            "secondary": out.secondary.model_dump(mode="json") if out.secondary else {},
            "agreement": out.agreement,
            "serving_models": out.serving_models,
            "reasons": reasons,
        }

    @staticmethod
    def _after_extract(state: RunState) -> Literal["validate", "decide"]:
        return "validate" if state.get("extraction") else "decide"

    def _validate(self, state: RunState) -> dict[str, Any]:
        ex = TradeLicenceExtraction.model_validate(state["extraction"])
        pages = self._pages(state)
        ctx = RuleContext(
            extraction=ex,
            authority=state["route"]["authority"],
            today=self.deps.clock.today(),
            ocr_text=pages.text,
            qr_payload=pages.qr_payload,
            registry=self.deps.registry.lookup,
            applicant_name=state["applicant_name"],
            applicant_threshold=self.deps.applicant_threshold,
        )
        with self.tracer.span("step", "validate", run_id=state["run_id"]):
            results = run_rules(ctx)
        return {"rule_results": [r.model_dump(mode="json") for r in results]}

    def _map_form(self, state: RunState) -> dict[str, Any]:
        ex = TradeLicenceExtraction.model_validate(state["extraction"])
        results = [RuleResult.model_validate(r) for r in state["rule_results"]]
        form = build_form(ex, results, authority=state["route"]["authority"], version=1)
        return {"form": form.model_dump(mode="json")}

    @staticmethod
    def _decide(state: RunState) -> dict[str, Any]:
        """User Story 1 routing: file and corroborated out-of-scope reasons reject; any other
        reason or failed rule goes to review; otherwise ready. US3 adds confidence."""
        reasons = list(state.get("reasons", []))
        results = [RuleResult.model_validate(r) for r in state.get("rule_results", [])]
        for result in results:
            if not result.counts_as_failed:
                continue
            assert result.reason_code is not None  # noqa: S101 - a failed rule always has a code
            # One reason per field, so the review page can show it next to each field.
            # A rule about the whole document (no fields) gives one reason with no field.
            fields: list[str | None] = list(result.fields) or [None]
            for field_name in fields:
                reasons.append(
                    reason_entry(
                        result.reason_code,
                        field=field_name,
                        rule_id=result.rule_id,
                        detail=result.detail,
                    )
                )
        codes = {r["code"] for r in reasons}
        if codes & (FILE_REASONS | {"out_of_scope"}):
            route = "reject"
        elif reasons:
            route = "needs_review"
        else:
            route = "ready"
        return {"decision": {"route": route}, "reasons": reasons}

    def _persist(self, state: RunState) -> dict[str, Any]:
        run_id = state["run_id"]
        route = state["decision"]["route"]
        status = STATUS_FOR_ROUTE[route]
        version = state.get("form", {}).get("version", 0)
        self.db.update_run(
            run_id,
            status=status,
            route=route,
            reasons_json=json.dumps(state.get("reasons", [])),
            form_version=version,
        )
        self.db.record_audit(
            event_key=f"{run_id}:persist:{status}:{version}",
            run_id=run_id,
            action="status_change",
            actor="system",
            new=status,
        )
        return {"status": status}

    def _trace_call(
        self, run_id: str, parent: Span, req: ModelRequest, resp: ModelResponse
    ) -> None:
        with self.tracer.span("model_call", req.step, run_id=run_id, parent=parent) as span:
            span.requested_model = req.model
            span.serving_model = resp.serving_model
            span.effort = req.effort
            span.input_tokens = resp.usage.input_tokens
            span.output_tokens = resp.usage.output_tokens
            span.thinking_tokens = resp.usage.thinking_tokens
            span.cache_read_tokens = resp.usage.cache_read_tokens
            span.cost_usd = resp.cost_usd()
            # A retry uses the prompt of the step it retries ("extract_primary_retry").
            span.prompt_hash = prompt_hash(req.step.removesuffix("_retry"))
