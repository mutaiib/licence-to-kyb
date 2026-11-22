"""Review, submission and verification (User Story 2), one test per row of the US2 table
in specs/001-licence-to-kyb/test-cases.md. Every test checks outcomes: the run view, the
stored submissions, the audit log and the captured corrections."""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from licence_kyb.api.app import create_app
from licence_kyb.clock import FixedClock
from licence_kyb.config import Settings
from licence_kyb.llm.client import DailyBudget, LLMClient
from licence_kyb.pipeline import Deps, Pipeline
from licence_kyb.registry import MockRegistry
from licence_kyb.security import Cipher
from licence_kyb.testdata.answers import ScriptedTransport
from licence_kyb.testdata.catalogue import GROUPS, build

PASSWORD = "correct horse battery staple"  # noqa: S105 - test-only reviewer account
KEY = Fernet.generate_key().decode()


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    wanted = {"clean", "near_expiry", "registry_not_found"}
    groups = tuple(replace(g, count=1) for g in GROUPS if g.name in wanted)
    return root, build(root, seed=7, groups=groups).cases


def case_of(catalogue: tuple[Path, list[dict[str, Any]]], group: str) -> dict[str, Any]:
    return next(c for c in catalogue[1] if c["group"] == group)


# ------------------------------------------------------------------ a small test harness
@dataclass
class Reviewer:
    """One signed-in reviewer with one uploaded run."""

    client: TestClient
    csrf: str
    run_id: str
    transport: ScriptedTransport

    @property
    def pipeline(self) -> Pipeline:
        pipeline: Pipeline = self.client.app.state.pipeline  # type: ignore[attr-defined]
        return pipeline

    def view(self) -> dict[str, Any]:
        view: dict[str, Any] = self.client.get(f"/api/runs/{self.run_id}").json()
        return view

    def post(self, path: str, body: dict[str, Any], *, csrf: bool = True) -> Any:
        headers = {"X-CSRF-Token": self.csrf} if csrf else {}
        return self.client.post(f"/api/runs/{self.run_id}/{path}", json=body, headers=headers)

    def review(self, *decisions: dict[str, Any], **form_action: Any) -> Any:
        body = {
            "form_version": form_action.pop("version", self.view()["form"]["version"]),
            "decisions": list(decisions),
            "action_id": form_action.pop("action_id", new_id()),
            **form_action,
        }
        return self.post("review", body)

    def submit(self, *, version: int | None = None, action_id: str | None = None) -> Any:
        version = self.view()["form"]["version"] if version is None else version
        return self.post("submit", {"action_id": action_id or new_id(), "form_version": version})

    def audit(self, action: str | None = None) -> list[dict[str, Any]]:
        cipher = self.pipeline.deps.cipher
        events = []
        for row in self.pipeline.db.audit_events(self.run_id):
            event = dict(row)
            for key in ("old_enc", "new_enc"):
                event[key.removesuffix("_enc")] = (
                    cipher.decrypt_text(row[key]) if row[key] else None
                )
            events.append(event)
        return [e for e in events if action is None or e["action"] == action]

    def count(self, table: str) -> int:
        return self.pipeline.db.count(table)


def new_id() -> str:
    return str(uuid.uuid4())


def decision(
    field: str,
    action: str,
    value: str | None = None,
    reason: str | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {"decision_id": decision_id or new_id(), "action": action}
    d["rule_id" if action == "override" else "field"] = field
    if value is not None:
        d["value"] = value
    if reason is not None:
        d["reason"] = reason
    return d


def make_client(
    data_dir: Path, root: Path, transport: ScriptedTransport, *, registry_down: bool = False
) -> TestClient:
    settings = Settings(
        reviewer_accounts={"reviewer1": PasswordHasher().hash(PASSWORD)},  # type: ignore[dict-item]
        session_secret="s" * 32,  # type: ignore[arg-type]
        cookie_secure=False,
    )
    deps = Deps(
        data_dir=data_dir,
        cipher=Cipher([KEY]),
        llm=LLMClient(transport, DailyBudget(1_000_000)),
        clock=FixedClock(),
        registry=MockRegistry(root / "data" / "registry_mock.json", unavailable=registry_down),
    )
    return TestClient(create_app(data_dir=data_dir, settings=settings, pipeline=Pipeline(deps)))


def sign_in(client: TestClient) -> str:
    assert (
        client.post(
            "/api/session", json={"username": "reviewer1", "password": PASSWORD}
        ).status_code
        == 200
    )
    return client.cookies["csrf"]


def start(
    tmp_path: Path,
    catalogue: Any,
    group: str,
    *,
    faults: set[str] | None = None,
    registry_down: bool = False,
    misread: dict[str, str] | None = None,
    crash: bool = False,
) -> Reviewer:
    """Upload the group's licence and return a signed-in reviewer for its run.
    ``misread`` makes the scripted model read these values wrong."""
    root, case = catalogue[0], case_of(catalogue, group)
    labels = {**case["expected_values"], **(misread or {})}
    transport = (CrashingTransport if crash else ScriptedTransport)(labels, faults=faults)
    client = make_client(tmp_path / "var", root, transport, registry_down=registry_down)
    csrf = sign_in(client)
    created = client.post(
        "/api/runs",
        files={"file": ("l.pdf", (root / case["document"]).read_bytes(), "application/pdf")},
        data={"applicant_name": case["applicant_name"]},
        headers={"X-CSRF-Token": csrf},
    )
    return Reviewer(client, csrf, created.json()["run_id"], transport)


class CrashingTransport(ScriptedTransport):
    """A model client with a bug: it raises an unexpected error until ``is_broken`` is False."""

    is_broken = True

    def send(self, req: Any) -> Any:
        if self.is_broken:
            raise RuntimeError("unexpected error in the model client")
        return super().send(req)


def misread_expiry(catalogue: Any) -> tuple[dict[str, str], str]:
    """The model reads the expiry year wrong, while the licence, its QR code and the
    registry agree on the true date (the "corrects expiry_date" row of the US2 table).
    Returns the misread label and the true date."""
    truth: str = case_of(catalogue, "near_expiry")["expected_values"]["expiry_date"]
    wrong = str(int(truth[:4]) + 2) + truth[4:]
    return {"expiry_date": wrong}, truth


def approve_flagged(r: Reviewer, *, true_expiry: str | None = None) -> None:
    """Decide every flagged field: correct a misread expiry date, approve the rest."""
    decisions = []
    for name, f in r.view()["form"]["fields"].items():
        if f["state"] not in ("flagged", "needs_examination"):
            continue
        if name == "expiry_date" and true_expiry and f["value"] != true_expiry:
            decisions.append(decision(name, "correct", true_expiry))
        else:
            decisions.append(decision(name, "approve"))
    assert r.review(*decisions).status_code == 200


# ------------------------------------------------------------------ correcting a field
def test_a_correction_replaces_the_value_and_is_audited_and_captured(
    tmp_path: Path, catalogue: Any
) -> None:
    misread, truth = misread_expiry(catalogue)
    r = start(tmp_path, catalogue, "near_expiry", misread=misread)
    read_quote = r.view()["form"]["fields"]["expiry_date"]["evidence_quote"]

    response = r.review(decision("expiry_date", "correct", truth, "QR code shows it"))

    assert response.status_code == 200
    expiry = r.view()["form"]["fields"]["expiry_date"]
    assert expiry["value"] == truth
    assert expiry["origin"] == "entered_by_reviewer"
    assert expiry["state"] == "corrected"
    assert expiry["evidence_quote"] == read_quote  # the licence text stays visible
    # Re-checked with every rule: only the true near-expiry warning can remain.
    assert {x["reason_code"] for x in expiry["rule_results"]} <= {"near_expiry"}
    [event] = r.audit("correct")
    assert (event["old"], event["new"], event["actor"]) == (
        misread["expiry_date"],
        truth,
        "reviewer1",
    )
    assert r.count("captured_corrections") == 1
    with r.pipeline.db.connect() as conn:
        capture = conn.execute("SELECT * FROM captured_corrections").fetchone()
    assert capture["status"] == "pending"
    assert truth not in capture["corrected_value_enc"]  # stored encrypted


def test_the_same_review_call_twice_changes_the_run_once(tmp_path: Path, catalogue: Any) -> None:
    misread, truth = misread_expiry(catalogue)
    r = start(tmp_path, catalogue, "near_expiry", misread=misread)
    version = r.view()["form"]["version"]
    same = decision("expiry_date", "correct", truth)

    first = r.review(same, version=version, action_id="a1")
    second = r.review(same, version=version, action_id="a1")

    assert (first.status_code, second.status_code) == (200, 200)
    assert len(r.audit("correct")) == 1
    assert r.count("captured_corrections") == 1
    assert r.view()["form"]["version"] == version + 1


def test_a_correction_that_breaks_a_blocking_rule_is_refused(
    tmp_path: Path, catalogue: Any
) -> None:
    r = start(tmp_path, catalogue, "near_expiry")
    before = r.view()["form"]["fields"]["licence_number"]["value"]

    response = r.review(decision("licence_number", "correct", "NOT-A-NUMBER"))

    assert response.status_code == 409
    assert response.json()["code"] == "blocking_rule_failed"
    assert response.json()["field"] == "licence_number"
    assert r.view()["form"]["fields"]["licence_number"]["value"] == before
    assert r.audit("correct") == []


def test_the_form_cannot_be_approved_while_a_flagged_field_is_undecided(
    tmp_path: Path, catalogue: Any
) -> None:
    r = start(tmp_path, catalogue, "near_expiry")

    response = r.review(approve_form=True)

    assert response.status_code == 409
    assert response.json()["code"] == "undecided_fields"
    assert r.view()["status"] == "awaiting_review"


# ------------------------------------------------------------------ approval and submission
def test_a_ready_run_still_needs_an_approval_and_a_submit(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "clean")
    assert r.view()["status"] == "awaiting_submit"
    assert r.submit().json()["code"] == "not_approved"

    assert r.review(approve_form=True).status_code == 200
    submitted = r.submit()

    assert submitted.status_code == 200
    assert submitted.json()["verified"] is True
    assert r.view()["status"] == "done"
    assert r.count("submissions") == 1
    [approval] = r.audit("approve_form")
    assert approval["actor"] == "reviewer1"


def test_a_change_after_approval_needs_a_new_approval(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "clean")
    r.review(approve_form=True)
    approved_version = r.view()["form"]["version"]

    r.review(decision("legal_name_en", "correct", "Changed Name LLC"))

    assert r.submit(version=approved_version).json()["code"] == "stale_version"
    assert r.submit().json()["code"] == "not_approved"
    assert r.view()["status"] == "awaiting_review"
    assert r.count("submissions") == 0


def test_submitting_twice_creates_one_submission(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "clean")
    r.review(approve_form=True)

    first = r.submit(action_id="s1").json()
    again = r.submit(action_id="s1").json()

    assert first["submission_id"] == again["submission_id"]
    assert r.count("submissions") == 1
    assert len(r.audit("submit")) == 1


def test_a_submission_that_reads_back_different_returns_the_run_to_review(
    tmp_path: Path, catalogue: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = start(tmp_path, catalogue, "clean")
    r.review(approve_form=True)
    version = r.view()["form"]["version"]
    real_read = r.pipeline.db.read_submission

    def tampered(submission_id: str) -> dict[str, Any] | None:
        row = real_read(submission_id)
        assert row is not None
        return {**row, "form_enc": r.pipeline.deps.cipher.encrypt_text('{"other": 1}')}

    monkeypatch.setattr(r.pipeline.db, "read_submission", tampered)
    result = r.submit().json()

    assert result["verified"] is False
    view = r.view()
    assert view["status"] == "awaiting_review"
    assert "verification_failed" in {x["code"] for x in view["reasons"]}
    assert view["form"]["version"] == version + 1

    # The reviewer approves the new version, with no value change, and submits again.
    monkeypatch.setattr(r.pipeline.db, "read_submission", real_read)
    assert r.review(approve_form=True).status_code == 200
    assert r.submit().json()["verified"] is True
    assert r.count("submissions") == 2
    assert r.view()["status"] == "done"


@pytest.mark.parametrize(("signed_in", "csrf", "status"), [(False, True, 401), (True, False, 403)])
def test_submit_needs_a_session_and_the_csrf_header(
    tmp_path: Path, catalogue: Any, signed_in: bool, csrf: bool, status: int
) -> None:
    r = start(tmp_path, catalogue, "clean")
    r.review(approve_form=True)
    if not signed_in:
        r.client.cookies.delete("session")

    response = r.post("submit", {"action_id": new_id(), "form_version": 1}, csrf=csrf)

    assert response.status_code == status
    assert r.count("submissions") == 0


# ------------------------------------------------------------------ reject and reopen
def test_a_rejected_case_is_never_submitted(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "near_expiry")

    r.review(reject_case=True, reject_reason="Licence belongs to another company")

    view = r.view()
    assert view["status"] == "rejected"
    assert "reviewer_rejected" in {x["code"] for x in view["reasons"]}
    assert r.submit().json()["code"] == "not_awaiting_submit"
    assert r.count("submissions") == 0
    [event] = r.audit("reject")
    assert event["actor"] == "reviewer1"


def test_reject_reopen_reject_records_every_event_with_its_reason(
    tmp_path: Path, catalogue: Any
) -> None:
    r = start(tmp_path, catalogue, "near_expiry")

    r.review(reject_case=True, reject_reason="first")
    reopened = r.post("reopen", {"action_id": new_id(), "reason": "new evidence"})
    r.review(reject_case=True, reject_reason="second")

    assert reopened.status_code == 200
    assert [e["reason"] for e in r.audit("reject")] == ["first", "second"]
    assert [e["reason"] for e in r.audit("reopen")] == ["new evidence"]
    assert r.view()["status"] == "rejected"


def test_a_reject_without_a_reason_is_refused(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "near_expiry")

    response = r.review(reject_case=True)

    assert response.json()["code"] == "reason_required"
    assert r.view()["status"] == "awaiting_review"


def test_only_a_rejected_run_can_be_reopened(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "near_expiry")

    response = r.post("reopen", {"action_id": new_id(), "reason": "why"})

    assert response.status_code == 409
    assert response.json()["code"] == "not_rejected"


# ------------------------------------------------------------------ overrides
def test_a_check_that_could_not_run_can_be_overridden_with_a_reason(
    tmp_path: Path, catalogue: Any
) -> None:
    r = start(tmp_path, catalogue, "clean", registry_down=True)
    assert r.view()["form"]["fields"]["licence_number"]["state"] == "flagged"

    response = r.review(decision("registry", "override", reason="Checked by phone"))

    assert response.status_code == 200
    assert r.view()["form"]["fields"]["licence_number"]["state"] == "overridden"
    [event] = r.audit("override")
    assert event["reason"] == "Checked by phone"
    assert r.review(approve_form=True).status_code == 200


def test_an_override_without_a_reason_is_refused(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "clean", registry_down=True)

    response = r.review(decision("registry", "override"))

    assert response.json()["code"] == "reason_required"
    assert r.audit("override") == []


def test_a_check_that_failed_cannot_be_overridden(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "registry_not_found")

    response = r.review(decision("registry", "override", reason="I know them"))

    assert response.status_code == 409
    assert response.json()["code"] == "not_overridable"
    assert r.view()["form"]["fields"]["licence_number"]["state"] == "flagged"


# ------------------------------------------------------------------ processing failures
def test_retry_processing_after_a_failure_continues_the_run(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "clean", faults={"refusal"})
    assert "processing_failed" in {x["code"] for x in r.view()["reasons"]}
    r.transport.faults.clear()  # the model service works again

    response = r.post("retry", {"action_id": new_id()})

    assert response.status_code == 202
    view = r.view()
    assert view["status"] == "awaiting_submit"
    assert "processing_failed" not in {x["code"] for x in view["reasons"]}
    assert len(r.audit("retry")) == 1


def test_retry_after_a_crash_processes_the_run_again(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "clean", crash=True)
    assert "processing_failed" in {x["code"] for x in r.view()["reasons"]}
    assert isinstance(r.transport, CrashingTransport)
    r.transport.is_broken = False

    response = r.post("retry", {"action_id": new_id()})

    assert response.status_code == 202
    assert r.view()["status"] == "awaiting_submit"


def test_retry_is_refused_when_processing_did_not_fail(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "near_expiry")

    response = r.post("retry", {"action_id": new_id()})

    assert response.status_code == 409
    assert response.json()["code"] == "not_retryable"


def test_after_a_failure_the_reviewer_can_enter_values_by_hand(
    tmp_path: Path, catalogue: Any
) -> None:
    r = start(tmp_path, catalogue, "clean", faults={"refusal"})
    labels = case_of(catalogue, "clean")["expected_values"]

    response = r.review(
        decision("licence_number", "correct", labels["licence_number"]),
        decision("expiry_date", "correct", labels["expiry_date"]),
    )

    assert response.status_code == 200
    fields = r.view()["form"]["fields"]
    for name in ("licence_number", "expiry_date"):
        assert fields[name]["value"] == labels[name]
        assert fields[name]["origin"] == "entered_by_reviewer"
        assert fields[name]["rule_results"] == []


# ------------------------------------------------------------------ restart
def test_a_run_in_review_survives_a_restart_with_its_decisions(
    tmp_path: Path, catalogue: Any
) -> None:
    misread, truth = misread_expiry(catalogue)
    r = start(tmp_path, catalogue, "near_expiry", misread=misread)
    r.review(decision("expiry_date", "correct", truth))
    before = r.view()

    restarted = make_client(tmp_path / "var", catalogue[0], r.transport)
    r2 = Reviewer(restarted, sign_in(restarted), r.run_id, r.transport)

    assert r2.view()["form"] == before["form"]
    assert r2.view()["status"] == before["status"]
    approve_flagged(r2)
    assert r2.review(approve_form=True).status_code == 200
    assert r2.submit().json()["verified"] is True
    assert len(r2.audit("correct")) == 1


# ------------------------------------------------------------------ audit property (T058)
STEP = st.tuples(
    st.sampled_from(["expiry_date", "legal_name_en", "chamber_number"]),
    st.sampled_from(["approve", "correct"]),
    st.booleans(),  # repeat the previous call with the same keys
)


@settings(max_examples=8, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(steps=st.lists(STEP, min_size=1, max_size=5))
def test_the_audit_alone_names_the_approver_and_every_change(
    catalogue: Any, steps: list[tuple[str, str, bool]]
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        misread, truth = misread_expiry(catalogue)
        r = start(Path(tmp), catalogue, "near_expiry", misread=misread)
        accepted: set[str] = set()
        previous: dict[str, Any] | None = None
        for i, (field, action, repeat) in enumerate(steps):
            d = (
                previous
                if repeat and previous
                else decision(field, action, truth if field == "expiry_date" else f"Value {i}")
            )
            if r.review(d).status_code == 200:
                accepted.add(d["decision_id"])
            previous = d
        approve_flagged(r, true_expiry=truth)
        assert r.review(approve_form=True).status_code == 200
        submitted_version = r.view()["form"]["version"]
        assert r.submit().json()["verified"] is True

        changes = [e for e in r.audit() if e["action"] in ("approve", "correct")]
        approvals = r.audit("approve_form")

    assert {e["event_key"] for e in changes} >= accepted  # every accepted decision, once
    assert len({e["event_key"] for e in changes}) == len(changes)
    assert approvals[-1]["actor"] == "reviewer1"
    assert approvals[-1]["new"] == str(submitted_version)
    assert all(e["new"] is not None for e in changes if e["action"] == "correct")
