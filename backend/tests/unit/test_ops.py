"""Operations: nothing stalls, nothing is kept past retention (FR-030, FR-036, FR-039)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from licence_kyb.clock import FixedClock
from licence_kyb.ops import Operations
from licence_kyb.store.db import Database

NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "app.sqlite3")
    database.migrate()
    return database


def make_run(db: Database, run_id: str, status: str, deadline: datetime | None = None) -> None:
    db.create_run(run_id=run_id, file_sha256=f"sha-{run_id}", applicant_name="Acme")
    fields: dict[str, object] = {"status": status}
    if deadline is not None:
        fields["deadline_at"] = deadline.isoformat()
    db.update_run(run_id, **fields)


def test_startup_resumes_every_received_or_processing_run_with_a_fresh_deadline(
    db: Database,
) -> None:
    make_run(db, "a", "received")
    make_run(db, "b", "processing", deadline=NOW - timedelta(minutes=5))
    make_run(db, "c", "awaiting_review")
    resumed: list[str] = []
    ops = Operations(db, FixedClock(NOW), deadline_seconds=120)

    ops.resume_on_startup(resumed.append)

    assert sorted(resumed) == ["a", "b"]
    for run_id in ("a", "b"):
        run = db.get_run(run_id)
        assert run is not None
        assert datetime.fromisoformat(run["deadline_at"]) == NOW + timedelta(seconds=120)


def test_a_run_past_its_deadline_goes_to_review_with_processing_failed(db: Database) -> None:
    make_run(db, "late", "processing", deadline=NOW - timedelta(seconds=1))
    make_run(db, "on-time", "processing", deadline=NOW + timedelta(seconds=30))
    ops = Operations(db, FixedClock(NOW), deadline_seconds=120)

    moved = ops.sweep_deadlines()

    assert moved == ["late"]
    late = db.get_run("late")
    assert late is not None
    assert late["status"] == "awaiting_review"
    assert {r["code"] for r in json.loads(late["reasons_json"])} == {"processing_failed"}
    on_time = db.get_run("on-time")
    assert on_time is not None
    assert on_time["status"] == "processing"
    assert [e["action"] for e in db.audit_events("late")] == ["status_change"]


def test_sweeping_twice_records_the_status_change_once(db: Database) -> None:
    make_run(db, "late", "processing", deadline=NOW - timedelta(seconds=1))
    ops = Operations(db, FixedClock(NOW), deadline_seconds=120)

    ops.sweep_deadlines()
    ops.sweep_deadlines()

    assert len(db.audit_events("late")) == 1


def test_retention_deletes_old_runs_and_keeps_current_ones(db: Database, tmp_path: Path) -> None:
    make_run(db, "old", "done")
    make_run(db, "new", "done")
    with db.connect() as conn:
        conn.execute(
            "UPDATE runs SET created_at = ? WHERE run_id = 'old'",
            ((NOW - timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),),
        )
    files_dir = tmp_path / "files"
    (files_dir / "old").mkdir(parents=True)
    (files_dir / "old" / "original.bin").write_bytes(b"x")
    ops = Operations(db, FixedClock(NOW), deadline_seconds=120, files_dir=files_dir)

    deleted = ops.apply_retention(days=30)

    assert deleted == 1
    assert db.get_run("old") is None
    assert db.get_run("new") is not None
    assert not (files_dir / "old").exists()
