"""Personal data stays encrypted at rest (security review, round 2): licence numbers in
reason details and reviewers' free-text reasons never reach the database in plain text."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from licence_kyb.testdata.answers import ScriptedTransport
from licence_kyb.testdata.catalogue import GROUPS, build
from tests.api.test_review_submit import Reviewer, case_of, make_client, new_id, sign_in


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=1) for g in GROUPS if g.name in {"qr_mismatch", "clean"})
    return root, build(root, seed=7, groups=groups).cases


def start(tmp_path: Path, catalogue: Any, group: str) -> Reviewer:
    root, case = catalogue[0], case_of(catalogue, group)
    transport = ScriptedTransport(case["expected_values"])
    client = make_client(tmp_path / "var", root, transport)
    csrf = sign_in(client)
    created = client.post(
        "/api/runs",
        files={"file": ("l.pdf", (root / case["document"]).read_bytes(), "application/pdf")},
        data={"applicant_name": case["applicant_name"]},
        headers={"X-CSRF-Token": csrf},
    )
    return Reviewer(client, csrf, created.json()["run_id"], transport)


def database_bytes(tmp_path: Path) -> bytes:
    return b"".join(p.read_bytes() for p in (tmp_path / "var").rglob("app.sqlite3*"))


def test_a_qr_mismatch_shows_both_numbers_but_stores_neither_in_plain_text(
    tmp_path: Path, catalogue: Any
) -> None:
    r = start(tmp_path, catalogue, "qr_mismatch")
    number = case_of(catalogue, "qr_mismatch")["expected_values"]["licence_number"]

    [reason] = [x for x in r.view()["reasons"] if x["code"] == "qr_mismatch"]

    assert reason["detail"]["value"] == number  # the reviewer still sees it
    assert number.encode() not in database_bytes(tmp_path)


def test_a_reviewers_reason_is_stored_encrypted(tmp_path: Path, catalogue: Any) -> None:
    r = start(tmp_path, catalogue, "clean")

    r.review(reject_case=True, reject_reason="Owner Ahmed Example signed for another firm")
    r.post("reopen", {"action_id": new_id(), "reason": "Ahmed Example sent proof"})

    assert [e["reason"] for e in r.audit("reject")] == [
        "Owner Ahmed Example signed for another firm"
    ]
    assert b"Ahmed Example" not in database_bytes(tmp_path)
