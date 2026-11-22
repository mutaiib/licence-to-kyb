"""A session ends on the server (traceability review, round 3; FR-022).

Signing out only deleted the cookie in the browser, so a copied cookie still worked for up to
8 hours. Each session now has an ID; sign-out revokes it on the server."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from licence_kyb.api import auth as auth_module
from licence_kyb.api.auth import SESSION_COOKIE
from licence_kyb.testdata.catalogue import GROUPS, build
from tests.api.test_session_and_upload import make_client, sign_in


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=1) for g in GROUPS if g.name == "clean")
    return root, build(root, seed=5, groups=groups).cases


def session_cookie(client: TestClient) -> str:
    value = client.cookies.get(SESSION_COOKIE)
    assert value
    return value


def test_a_copied_cookie_stops_working_after_sign_out(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    csrf = sign_in(client)
    copied = session_cookie(client)

    assert client.delete("/api/session", headers={"X-CSRF-Token": csrf}).status_code == 204

    replay = make_client(tmp_path, root, cases[0])
    replay.cookies.set(SESSION_COOKIE, copied)
    assert replay.get("/api/runs").status_code == 401


def test_an_expired_session_is_refused(
    tmp_path: Path, catalogue: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    sign_in(client)
    later = time.time() + 9 * 3600  # past the 8-hour session
    monkeypatch.setattr(auth_module.time, "time", lambda: later)

    assert client.get("/api/runs").status_code == 401


def test_a_changed_cookie_is_refused(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = make_client(tmp_path, root, cases[0])
    sign_in(client)
    _user, *rest = session_cookie(client).split("|")
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, "|".join(["someone-else", *rest]))

    assert client.get("/api/runs").status_code == 401
