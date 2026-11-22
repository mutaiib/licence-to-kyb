"""Session and upload API, per contracts/http-api.md (S9; FR-022)."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from licence_kyb.api.app import create_app
from licence_kyb.config import Settings
from licence_kyb.llm.client import ModelRequest, ModelResponse
from licence_kyb.testdata.answers import ScriptedTransport
from licence_kyb.testdata.catalogue import GROUPS, build
from tests.builders import first_case, make_pipeline

PASSWORD = "correct horse battery staple"  # noqa: S105 - test-only reviewer account
FERNET_KEY = Fernet.generate_key().decode()  # one key, so a restarted app reads earlier runs


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=2) for g in GROUPS if g.name in {"clean", "near_expiry"})
    return root, build(root, seed=5, groups=groups).cases


class BrokenTransport(ScriptedTransport):
    """A model transport that fails in a way the pipeline does not expect."""

    def send(self, req: ModelRequest) -> ModelResponse:
        raise RuntimeError("the transport broke")


def make_client(
    tmp_path: Path, root: Path, case: dict[str, Any], transport: ScriptedTransport | None = None
) -> TestClient:
    settings = Settings(
        reviewer_accounts={"reviewer1": PasswordHasher().hash(PASSWORD)},  # type: ignore[dict-item]
        session_secret="s" * 32,  # type: ignore[arg-type]
        cookie_secure=False,
    )
    pipeline = make_pipeline(
        tmp_path / "var",
        transport or ScriptedTransport(case["expected_values"]),
        registry_path=root / "data" / "registry_mock.json",
        fernet_key=FERNET_KEY,
    )
    return TestClient(create_app(data_dir=tmp_path / "var", settings=settings, pipeline=pipeline))


def sign_in(client: TestClient) -> str:
    response = client.post("/api/session", json={"username": "reviewer1", "password": PASSWORD})
    assert response.status_code == 200
    return client.cookies["csrf"]


def upload(client: TestClient, csrf: str, root: Path, case: dict[str, Any]) -> Any:
    return client.post(
        "/api/runs",
        files={"file": ("licence.pdf", (root / case["document"]).read_bytes(), "application/pdf")},
        data={"applicant_name": case["applicant_name"]},
        headers={"X-CSRF-Token": csrf},
    )


def test_sign_in_with_the_right_password_sets_a_session(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])

    response = client.post("/api/session", json={"username": "reviewer1", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"reviewer": "reviewer1"}
    assert "session" in client.cookies


def test_a_wrong_password_is_refused_with_its_code(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])

    response = client.post("/api/session", json={"username": "reviewer1", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_the_sixth_failed_sign_in_within_a_minute_is_rate_limited(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    statuses = [
        client.post("/api/session", json={"username": "reviewer1", "password": "wrong"}).status_code
        for _ in range(6)
    ]

    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


def test_requests_without_a_session_are_refused(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])

    response = client.get("/api/runs")

    assert response.status_code == 401
    assert response.json()["code"] == "session_expired"


def test_a_state_changing_request_without_the_csrf_header_is_refused(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    sign_in(client)

    response = client.post(
        "/api/runs",
        files={"file": ("x.pdf", b"%PDF-1.7", "application/pdf")},
        data={"applicant_name": "Acme"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_sign_out_ends_the_session(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    csrf = sign_in(client)

    assert client.delete("/api/session", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/runs").status_code == 401


def test_uploading_a_clean_licence_gives_a_run_with_a_draft_form(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    case = first_case(cases, "clean")
    client = make_client(tmp_path, root, case)
    csrf = sign_in(client)

    created = upload(client, csrf, root, case)
    assert created.status_code == 202
    view = client.get(f"/api/runs/{created.json()['run_id']}").json()

    assert view["route"] == "ready"
    assert view["status"] == "awaiting_submit"
    assert (
        view["form"]["fields"]["licence_number"]["value"]
        == case["expected_values"]["licence_number"]
    )
    assert view["form"]["fields"]["licence_number"]["evidence_quote"]
    assert view["pages"] == 1


def test_a_flagged_field_shows_its_value_state_reason_and_evidence_box(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    case = first_case(cases, "near_expiry")
    client = make_client(tmp_path, root, case)
    csrf = sign_in(client)

    run_id = upload(client, csrf, root, case).json()["run_id"]
    view = client.get(f"/api/runs/{run_id}").json()
    expiry = view["form"]["fields"]["expiry_date"]

    assert view["route"] == "needs_review"
    assert {"code": "near_expiry", "field": "expiry_date"} in [
        {"code": r["code"], "field": r["field"]} for r in view["reasons"]
    ]
    assert expiry["state"] == "flagged"
    assert expiry["value"] == case["expected_values"]["expiry_date"]
    assert [r["reason_code"] for r in expiry["rule_results"]] == ["near_expiry"]
    box = expiry["evidence_box"]
    assert box["page"] == 1
    assert 0 <= box["x"] <= 1
    assert 0 <= box["y"] <= 1


def test_the_same_file_twice_returns_the_existing_run(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    case = cases[0]
    client = make_client(tmp_path, root, case)
    csrf = sign_in(client)

    first = upload(client, csrf, root, case).json()["run_id"]
    second = upload(client, csrf, root, case)

    assert second.status_code == 200
    assert second.json() == {"run_id": first, "status": second.json()["status"], "duplicate": True}


def test_an_unsupported_file_is_rejected_with_its_reason_code(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    csrf = sign_in(client)

    response = client.post(
        "/api/runs",
        files={"file": ("x.pdf", b"MZ\x90\x00" * 50, "application/pdf")},
        data={"applicant_name": "Acme"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "invalid_type"


def test_a_request_with_invalid_values_gets_an_error_code_the_page_can_show(
    tmp_path: Path, catalogue: Any
) -> None:
    """A body that fails validation (here a business name over 200 characters) must carry
    a code, like every other error, so the page shows a reason, not "cannot connect"."""
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    csrf = sign_in(client)

    response = client.post(
        "/api/runs",
        files={"file": ("l.pdf", (root / cases[0]["document"]).read_bytes(), "application/pdf")},
        data={"applicant_name": "A" * 201},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_page_images_are_served_to_signed_in_reviewers(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    csrf = sign_in(client)
    run_id = upload(client, csrf, root, cases[0]).json()["run_id"]

    response = client.get(f"/api/runs/{run_id}/pages/1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


@pytest.mark.parametrize("run_id", ["%2E%2E", "no-such-run"])
def test_a_page_of_a_run_that_does_not_exist_is_not_found(
    tmp_path: Path, catalogue: Any, run_id: str
) -> None:
    """The run ID becomes part of a file path, so it must name a known run first."""
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    csrf = sign_in(client)
    upload(client, csrf, root, cases[0])

    response = client.get(f"/api/runs/{run_id}/pages/1")

    assert response.status_code == 404


def test_reasons_carry_their_values_and_fields_report_their_document_status(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    case = first_case(cases, "near_expiry")
    client = make_client(tmp_path, root, case)
    csrf = sign_in(client)

    run_id = upload(client, csrf, root, case).json()["run_id"]
    view = client.get(f"/api/runs/{run_id}").json()

    near = next(r for r in view["reasons"] if r["code"] == "near_expiry")
    assert near["detail"]["days"] == "10"
    assert view["form"]["fields"]["expiry_date"]["status"] == "present"
    # The synthetic licences print no unified licence number, so the API must say so.
    statuses = {name: f["status"] for name, f in view["form"]["fields"].items()}
    assert set(statuses.values()) <= {"present", "not_present", "unclear"}


def test_a_run_whose_processing_crashes_goes_to_review_with_processing_failed(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0], transport=BrokenTransport(None))
    csrf = sign_in(client)

    run_id = upload(client, csrf, root, cases[0]).json()["run_id"]
    view = client.get(f"/api/runs/{run_id}").json()

    assert view["status"] == "awaiting_review"
    assert "processing_failed" in [r["code"] for r in view["reasons"]]


def test_a_run_left_processing_before_a_restart_is_processed_at_startup(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    case = first_case(cases, "clean")
    pipeline = make_pipeline(
        tmp_path / "var",
        ScriptedTransport(case["expected_values"]),
        registry_path=root / "data" / "registry_mock.json",
        fernet_key=FERNET_KEY,
    )
    upload_result = pipeline.upload(
        (root / case["document"]).read_bytes(), applicant_name=case["applicant_name"]
    )
    assert upload_result.run_id is not None
    pipeline.db.update_run(upload_result.run_id, status="processing")

    with make_client(tmp_path, root, case) as after:
        sign_in(after)
        status = wait_for_status(after, upload_result.run_id, until={"awaiting_submit"})

    assert status == "awaiting_submit"


def wait_for_status(client: TestClient, run_id: str, *, until: set[str]) -> str:
    """Poll the run until its status is one of ``until``, for at most 20 seconds."""
    deadline = time.monotonic() + 20
    status = ""
    while time.monotonic() < deadline:
        status = client.get(f"/api/runs/{run_id}").json()["status"]
        if status in until:
            return status
        time.sleep(0.1)
    return status


def test_the_run_view_names_the_business_and_the_upload_time(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    csrf = sign_in(client)

    run_id = upload(client, csrf, root, cases[0]).json()["run_id"]
    view = client.get(f"/api/runs/{run_id}").json()

    assert view["applicant_name"] == cases[0]["applicant_name"]
    uploaded = datetime.fromisoformat(view["created_at"].replace("Z", "+00:00"))
    assert abs(datetime.now(UTC) - uploaded) < timedelta(minutes=5)  # the upload time, in UTC
