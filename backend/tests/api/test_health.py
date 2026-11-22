"""Health endpoints: liveness always, readiness only when storage is reachable."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from licence_kyb.api.app import create_app
from licence_kyb.store.db import Database


def test_healthz_reports_a_live_process(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.get("/healthz")

    assert response.status_code == 200


def test_readyz_is_ready_when_database_and_checkpoints_are_reachable(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["checkpoints"] == "ok"


def test_readyz_is_not_ready_when_the_database_is_unreachable(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)
    app.state.db = Database(tmp_path)  # a directory: SQLite cannot open it as a database
    client = TestClient(app)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
