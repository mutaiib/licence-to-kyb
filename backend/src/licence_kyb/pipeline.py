"""The processing pipeline for one run (architecture §4; tasks T051).

Graph:
    preprocess → route → extract → validate → map_form → decide → persist
        → wait_for_reviewer → apply_action → (wait_for_reviewer | retry | END)

- ``route`` goes straight to ``decide`` when the file is not a trade licence.
- When extraction fails, ``map_form`` builds an empty form, so the reviewer can enter values.
- ``wait_for_reviewer`` only pauses (``interrupt``). LangGraph re-runs a paused node when the
  run resumes, so this node must have no side effects.
- ``apply_action`` applies one reviewer action (logic in ``nodes/review.py``). ``act`` checks
  the action before it resumes the run, so this node only sees valid actions.

Nodes are pure except ``persist`` and ``apply_action``, which write keyed, idempotent
records. Checkpoints are encrypted (EncryptedSerializer + the rotating Fernet cipher),
because the state holds personal data from the document.
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
from langgraph.types import Command, interrupt

from licence_kyb.clock import Clock, SystemClock
from licence_kyb.config import (
    APPLICANT_NAME_THRESHOLD,
    ModelsConfig,
    models_config,
    processing_deadline_seconds,
)
from licence_kyb.graph import thread_config
from licence_kyb.llm.client import LLMClient, ModelRequest, ModelResponse
from licence_kyb.llm.prompts import prompt_hash
from licence_kyb.nodes import review
from licence_kyb.nodes.extract import build_extract_request, extract_licence
from licence_kyb.nodes.intake import IntakeResult, IntakeService
from licence_kyb.nodes.map_form import SOURCES, build_form
from licence_kyb.nodes.preprocess import PageSet, Word, preprocess_file
from licence_kyb.nodes.route import build_route_request, route_document
from licence_kyb.ops import Operations
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
    deadline_seconds: float = field(default_factory=processing_deadline_seconds)

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
        self.ops = Operations(
            self.db, deps.clock, deadline_seconds=deps.deadline_seconds, files_dir=deps.files_dir
        )
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
        self.db.update_run(run_id, status="processing", deadline_at=self.ops.new_deadline())
        config = thread_config(run_id)
        if self.graph.get_state(config).next:
            # A restart stopped this run part way: continue after its last completed step.
            resumed: dict[str, Any] = self.graph.invoke(None, config)
            return resumed
        state: dict[str, Any] = self.graph.invoke(
            {"run_id": run_id, "applicant_name": applicant}, config
        )
        return state

    def mark_failed(self, run_id: str) -> None:
        """Send a run whose processing raised an error to review (FR-039).

        The run's graph also moves to the review pause, so the reviewer can retry it.
        """
        run = self.db.get_run(run_id)
        if run is None:
            return
        self.ops.send_to_review(run, event="processing_error", note="processing raised an error")
        updated = self.db.get_run(run_id) or run
        self.graph.update_state(
            thread_config(run_id),
            {
                "run_id": run_id,
                "applicant_name": self.deps.cipher.decrypt_text(run["applicant_name"]),
                "status": "awaiting_review",
                "reasons": json.loads(updated["reasons_json"]),
            },
            as_node="persist",  # the next node is wait_for_reviewer
        )

    def page_png(self, run_id: str, page: int) -> bytes:
        return self.deps.cipher.decrypt(
            (self.deps.files_dir / run_id / f"page-{page}.png.enc").read_bytes()
        )

    # ------------------------------------------------------------------ reviewer actions
    def state(self, run_id: str) -> dict[str, Any]:
        snapshot = self.graph.get_state(thread_config(run_id))
        return dict(snapshot.values) if snapshot and snapshot.values else {}

    def check(self, run_id: str, action: dict[str, Any]) -> None:
        """Refuse an invalid action with ``review.ActionRefused``. Changes nothing."""
        state = self.state(run_id)
        if action["action_id"] in state.get("applied_ids", []):
            return  # a repeated action is answered, not refused
        kind = action["kind"]
        if kind == "review":
            review.apply_review(state, action, self._rules_for(state))
        elif kind == "submit":
            approved = self.db.approval_for(run_id, action["form_version"]) is not None
            review.check_submit(state, action, approved=approved)
        elif kind == "reopen":
            review.check_reopen(state)
        elif kind == "retry":
            review.check_retry(state)

    def act(self, run_id: str, action: dict[str, Any]) -> dict[str, Any]:
        """Check one reviewer action, then resume the paused run with it."""
        self.check(run_id, action)
        if action["action_id"] in self.state(run_id).get("applied_ids", []):
            return self.state(run_id)
        if action["kind"] == "retry":
            self.db.update_run(run_id, status="processing", deadline_at=self.ops.new_deadline())
        result: dict[str, Any] = self.graph.invoke(Command(resume=action), thread_config(run_id))
        return result

    def submission_for(self, run_id: str, action: dict[str, Any]) -> dict[str, Any] | None:
        """The submission an earlier call made with this action or for this form version."""
        return self.db.find_submission(run_id, action["action_id"], action["form_version"])

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
            "extract", self._after_extract, {"validate": "validate", "map_form": "map_form"}
        )
        g.add_edge("validate", "map_form")
        g.add_edge("map_form", "decide")
        g.add_edge("decide", "persist")
        g.add_node("wait_for_reviewer", self._wait_for_reviewer)
        g.add_node("apply_action", self._apply_action)
        g.add_edge("persist", "wait_for_reviewer")
        g.add_edge("wait_for_reviewer", "apply_action")
        g.add_conditional_edges(
            "apply_action",
            self._after_action,
            {
                "wait": "wait_for_reviewer",
                "preprocess": "preprocess",
                "route": "route",
                "extract": "extract",
                "end": END,
            },
        )
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
            "extraction": (
                out.primary.model_dump(mode="json") if out.primary else review.empty_extraction()
            ),
            "secondary": out.secondary.model_dump(mode="json") if out.secondary else {},
            "agreement": out.agreement,
            "serving_models": out.serving_models,
            "reasons": reasons,
        }

    @staticmethod
    def _after_extract(state: RunState) -> Literal["validate", "map_form"]:
        failed = {r["code"] for r in state.get("reasons", [])} & review.RETRYABLE
        return "map_form" if failed else "validate"

    def _validate(self, state: RunState) -> dict[str, Any]:
        ex = TradeLicenceExtraction.model_validate(state["extraction"])
        with self.tracer.span("step", "validate", run_id=state["run_id"]):
            results = self._run_rules(state, ex)
        return {"rule_results": [r.model_dump(mode="json") for r in results]}

    def _run_rules(self, state: RunState, ex: TradeLicenceExtraction) -> list[RuleResult]:
        """Every rule on one extraction. Used after extraction and after each review."""
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
        return run_rules(ctx)

    def _map_form(self, state: RunState) -> dict[str, Any]:
        ex = TradeLicenceExtraction.model_validate(state["extraction"])
        results = [RuleResult.model_validate(r) for r in state.get("rule_results", [])]
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
        self._audit(
            state,
            f"{run_id}:persist:{status}:{version}",
            "status_change",
            actor="system",
            new=status,
        )
        return {"status": status}

    # ------------------------------------------------------------------ review nodes
    @staticmethod
    def _wait_for_reviewer(state: RunState) -> dict[str, Any]:
        action = interrupt({"run_id": state["run_id"], "status": state.get("status")})
        return {"action": action}

    @staticmethod
    def _after_action(
        state: RunState,
    ) -> Literal["wait", "preprocess", "route", "extract", "end"]:
        if state["status"] == "done":
            return "end"
        if state["status"] == "processing" and not state.get("pages"):
            return "preprocess"  # processing failed before the pages were read
        if state["status"] == "processing":  # retry: run the step that failed again
            return (
                "extract" if state.get("route", {}).get("doc_type") == "trade_licence" else "route"
            )
        return "wait"

    def _rules_for(self, state: dict[str, Any]) -> review.RunRules:
        return lambda ex: self._run_rules(state, ex)  # type: ignore[arg-type]

    def _apply_action(self, state: RunState) -> dict[str, Any]:
        action, run_id = state["action"], state["run_id"]
        if action["kind"] == "review":
            updates = self._apply_review(state, action)
        elif action["kind"] == "submit":
            updates = self._apply_submit(state, action)
        elif action["kind"] == "reopen":
            updates = self._apply_reopen(state, action)
        else:
            updates = self._apply_retry(state, action)
        form = updates.get("form", state.get("form", {}))
        reasons = updates.get("reasons", state.get("reasons", []))
        self.db.update_run(
            run_id,
            status=updates["status"],
            reasons_json=json.dumps(reasons),
            form_version=form.get("version", 0),
        )
        return updates

    def _audit(self, state: RunState, key: str, action: str, **fields: Any) -> None:
        """One audit event per key; values are encrypted (they can hold personal data)."""
        for name in ("old", "new"):
            if fields.get(name) is not None:
                fields[name] = self.deps.cipher.encrypt_text(str(fields[name]))
        self.db.record_audit(event_key=key, run_id=state["run_id"], action=action, **fields)

    def _apply_review(self, state: RunState, action: dict[str, Any]) -> dict[str, Any]:
        result = review.apply_review(dict(state), action, self._rules_for(dict(state)))
        if not result.state:
            return {"status": state["status"]}
        reviewer, run_id = action["reviewer"], state["run_id"]
        for d in result.new_decisions:
            self._record_decision(state, d, reviewer)
        form = result.state["form"]
        if result.approved_version is not None:
            self.db.record_approval(
                action_id=action["action_id"],
                run_id=run_id,
                form_version=form["version"],
                reviewer=reviewer,
            )
            self._audit(
                state, action["action_id"], "approve_form", actor=reviewer, new=form["version"]
            )
        if result.rejected:
            self._audit(
                state, action["action_id"], "reject", actor=reviewer, reason=action["reject_reason"]
            )
        return result.state

    def _record_decision(self, state: RunState, d: dict[str, Any], reviewer: str) -> None:
        """The audit event for one field decision, and a captured correction for a fix."""
        target = d.get("field") or d["rule_id"]
        old = None
        if d["action"] == "correct":
            old = state["extraction"].get(SOURCES[target], {}).get("value")
            self.db.record_capture(
                capture_key=d["decision_id"],
                run_id=state["run_id"],
                field=target,
                read_value_enc=self.deps.cipher.encrypt_text(str(old)),
                corrected_value_enc=self.deps.cipher.encrypt_text(d["value"]),
                fault_group=self._fault_of(state, target),
            )
        self._audit(
            state,
            d["decision_id"],
            d["action"],
            actor=reviewer,
            target=target,
            old=old,
            new=d.get("value"),
            reason=d.get("reason"),
        )

    @staticmethod
    def _fault_of(state: RunState, form_field: str) -> str:
        """The reason the field was flagged, to group captured corrections for the eval set."""
        source = SOURCES[form_field]
        for r in state.get("rule_results", []):
            rule = RuleResult.model_validate(r)
            if source in rule.fields and rule.counts_as_failed:
                return str(rule.reason_code)
        return "reviewer_correction"

    def _apply_submit(self, state: RunState, action: dict[str, Any]) -> dict[str, Any]:
        """Store the approved form once, read it back, and finish only when they match."""
        run_id, form, reviewer = state["run_id"], state["form"], action["reviewer"]
        approved = review.form_json(form)
        submission = self.db.record_submission(
            action_id=action["action_id"],
            run_id=run_id,
            form_version=form["version"],
            form_json=self.deps.cipher.encrypt_text(approved),
            approved_by=reviewer,
        )
        self._audit(state, action["action_id"], "submit", actor=reviewer, new=form["version"])
        stored = self.db.read_submission(submission.submission_id)
        verified = (
            stored is not None and self.deps.cipher.decrypt_text(stored["form_enc"]) == approved
        )
        self.db.set_submission_verified(submission.submission_id, verified)
        self._audit(
            state,
            f"{submission.submission_id}:verify",
            "verify",
            actor="system",
            new="matches" if verified else "differs",
        )
        applied = [*state.get("applied_ids", []), action["action_id"]]
        record = {"submission_id": submission.submission_id, "verified": verified}
        if verified:
            return {"status": "done", "submission": record, "applied_ids": applied}
        # The stored record differs: the run goes back to review with a new form version,
        # so the reviewer must approve again before the next submit (FR-028).
        reasons = [*state.get("reasons", []), reason_entry("verification_failed")]
        return {
            "status": "awaiting_review",
            "submission": record,
            "applied_ids": applied,
            "reasons": reasons,
            "form": {**form, "version": form["version"] + 1},
        }

    def _apply_reopen(self, state: RunState, action: dict[str, Any]) -> dict[str, Any]:
        self._audit(
            state, action["action_id"], "reopen", actor=action["reviewer"], reason=action["reason"]
        )
        reasons = [r for r in state.get("reasons", []) if r["code"] != "reviewer_rejected"]
        applied = [*state.get("applied_ids", []), action["action_id"]]
        return {"status": "awaiting_review", "reasons": reasons, "applied_ids": applied}

    def _apply_retry(self, state: RunState, action: dict[str, Any]) -> dict[str, Any]:
        """Start processing again from the step that failed, with no reviewer decisions."""
        self._audit(state, action["action_id"], "retry", actor=action["reviewer"])
        applied = [*state.get("applied_ids", []), action["action_id"]]
        return {
            "status": "processing",
            "reasons": [],
            "decisions": {},
            "read_extraction": {},
            "rule_results": [],
            "applied_ids": applied,
        }

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
