"""Session and upload API, per contracts/http-api.md (S9; FR-022)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

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


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=2) for g in GROUPS if g.name in {"clean", "near_expiry"})
    return root, build(root, seed=5, groups=groups).cases


def make_client(tmp_path: Path, root: Path, case: dict[str, Any]) -> TestClient:
    settings = Settings(
        reviewer_accounts={"reviewer1": PasswordHasher().hash(PASSWORD)},  # type: ignore[dict-item]
        session_secret="s" * 32,  # type: ignore[arg-type]
        cookie_secure=False,
    )
    deps = Deps(
        data_dir=tmp_path / "var",
        cipher=Cipher([Fernet.generate_key().decode()]),
        llm=LLMClient(ScriptedTransport(case["expected_values"]), DailyBudget(1_000_000)),
        clock=FixedClock(),
        registry=MockRegistry(root / "data" / "registry_mock.json"),
    )
    return TestClient(
        create_app(data_dir=tmp_path / "var", settings=settings, pipeline=Pipeline(deps))
    )


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
    case = next(c for c in cases if c["group"] == "clean")
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
    case = next(c for c in cases if c["group"] == "near_expiry")
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


def test_page_images_are_served_to_signed_in_reviewers(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    csrf = sign_in(client)
    run_id = upload(client, csrf, root, cases[0]).json()["run_id"]

    response = client.get(f"/api/runs/{run_id}/pages/1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
