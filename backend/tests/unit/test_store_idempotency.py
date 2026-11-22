"""Every write is keyed: repeating it with the same key writes nothing new (data-model.md)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from licence_kyb.store.db import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "app.sqlite3")
    database.migrate()
    return database


def new_run(db: Database) -> str:
    run_id = str(uuid.uuid4())
    db.create_run(run_id=run_id, file_sha256=uuid.uuid4().hex, applicant_name="Acme")
    return run_id


def test_migrations_are_idempotent(db: Database) -> None:
    db.migrate()
    db.migrate()

    assert db.schema_version() >= 1


def test_same_file_hash_gives_one_run(db: Database) -> None:
    first = db.create_run(run_id="r-1", file_sha256="abc", applicant_name="Acme")
    second = db.create_run(run_id="r-2", file_sha256="abc", applicant_name="Acme")

    assert first.run_id == second.run_id == "r-1"
    assert db.count("runs") == 1


def test_audit_event_with_a_repeated_key_is_recorded_once(db: Database) -> None:
    run_id = new_run(db)
    for _ in range(3):
        db.record_audit(
            event_key="d-1", run_id=run_id, action="approve", target="expiry_date", actor="r1"
        )

    assert db.count("audit_events") == 1


def test_a_new_action_with_a_new_key_is_always_recorded(db: Database) -> None:
    run_id = new_run(db)
    db.record_audit(event_key="a-1", run_id=run_id, action="reject", actor="r1", reason="fake")
    db.record_audit(event_key="a-2", run_id=run_id, action="reopen", actor="r1", reason="mistake")
    db.record_audit(
        event_key="a-3", run_id=run_id, action="reject", actor="r1", reason="fake again"
    )

    actions = [e["action"] for e in db.audit_events(run_id)]
    assert actions == ["reject", "reopen", "reject"]


def test_submission_is_unique_per_form_version_and_repeat_returns_the_same_id(db: Database) -> None:
    run_id = new_run(db)
    first = db.record_submission(
        action_id="s-1", run_id=run_id, form_version=3, form_json="{}", approved_by="r1"
    )
    repeat = db.record_submission(
        action_id="s-2", run_id=run_id, form_version=3, form_json="{}", approved_by="r1"
    )
    later = db.record_submission(
        action_id="s-3", run_id=run_id, form_version=4, form_json="{}", approved_by="r1"
    )

    assert first.submission_id == repeat.submission_id
    assert later.submission_id != first.submission_id
    assert db.count("submissions") == 2


def test_approval_is_unique_per_form_version(db: Database) -> None:
    run_id = new_run(db)
    db.record_approval(action_id="p-1", run_id=run_id, form_version=2, reviewer="r1")
    db.record_approval(action_id="p-2", run_id=run_id, form_version=2, reviewer="r1")

    assert db.count("approvals") == 1


def test_captured_correction_with_a_repeated_key_is_stored_once(db: Database) -> None:
    run_id = new_run(db)
    for _ in range(2):
        db.record_capture(
            capture_key="d-9",
            run_id=run_id,
            field="expiry_date",
            read_value_enc="x",
            corrected_value_enc="y",
            fault_group="blur_date",
        )

    assert db.count("captured_corrections") == 1
