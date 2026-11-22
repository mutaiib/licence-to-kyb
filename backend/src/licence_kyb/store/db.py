"""SQLite persistence with forward-only migrations and keyed, idempotent writes.

Every write method takes the entity's unique key. Repeating a write with the same key
returns the existing row and writes nothing new, which makes graph nodes safe to re-run
after a LangGraph resume (data-model.md, "Writes and resumption").
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

_TABLES = frozenset(
    {
        "runs",
        "files",
        "review_decisions",
        "approvals",
        "submissions",
        "audit_events",
        "captured_corrections",
        "spans",
    }
)


@dataclass(frozen=True)
class RunRow:
    run_id: str
    file_sha256: str
    status: str
    form_version: int


@dataclass(frozen=True)
class SubmissionRow:
    submission_id: str
    run_id: str
    form_version: int
    verified: bool | None


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------ migrations
    def migrate(self) -> None:
        scripts = sorted(
            (
                p
                for p in resources.files("licence_kyb.store.migrations").iterdir()
                if p.name.endswith(".sql")
            ),
            key=lambda p: p.name,
        )
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            current = self._version(conn)
            for script in scripts:
                number = int(script.name.split("_", 1)[0])
                if number <= current:
                    continue
                # executescript commits any open transaction first, so the migration and its
                # version bump run as one script inside one explicit transaction.
                conn.executescript(
                    "BEGIN;\n"
                    + script.read_text(encoding="utf-8")
                    + f"\nDELETE FROM schema_version;\nINSERT INTO schema_version (version) "
                    f"VALUES ({number:d});\nCOMMIT;\n"
                )

    def schema_version(self) -> int:
        with self.connect() as conn:
            return self._version(conn)

    @staticmethod
    def _version(conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return int(row["version"]) if row else 0

    # ------------------------------------------------------------------ helpers
    def count(self, table: str) -> int:
        if table not in _TABLES:
            raise ValueError(f"unknown table {table}")
        with self.connect() as conn:
            return int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])  # noqa: S608

    # ------------------------------------------------------------------ runs
    def create_run(self, *, run_id: str, file_sha256: str, applicant_name: str) -> RunRow:
        """Create a run, or return the existing run for an identical file (FR-003)."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, file_sha256, applicant_name) VALUES (?, ?, ?) "
                "ON CONFLICT(file_sha256) DO NOTHING",
                (run_id, file_sha256, applicant_name),
            )
            row = conn.execute(
                "SELECT run_id, file_sha256, status, form_version FROM runs WHERE file_sha256 = ?",
                (file_sha256,),
            ).fetchone()
        return RunRow(row["run_id"], row["file_sha256"], row["status"], row["form_version"])

    def update_run(self, run_id: str, **fields: Any) -> None:
        allowed = {
            "status",
            "route",
            "reasons_json",
            "form_version",
            "deadline_at",
            "cost_usd",
            "duration_ms",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"cannot update {sorted(unknown)}")
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE runs SET {assignments}, "  # noqa: S608 - column names are allow-listed
                "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE run_id = ?",
                (*fields.values(), run_id),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def runs_with_status(self, *statuses: str) -> list[dict[str, Any]]:
        marks = ",".join("?" for _ in statuses)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM runs WHERE status IN ({marks}) ORDER BY created_at",  # noqa: S608
                statuses,
            ).fetchall()
        return [dict(r) for r in rows]

    def list_runs(self, limit: int) -> list[dict[str, Any]]:
        """The newest runs first, with the columns the run list shows."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT run_id, created_at, applicant_name, route, status, cost_usd, duration_ms "
                "FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_runs_created_before(self, iso_timestamp: str) -> int:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM runs WHERE created_at < ?", (iso_timestamp,))
            return cur.rowcount

    # ------------------------------------------------------------------ files
    def record_file(
        self, *, run_id: str, mime: str, page_count: int, megapixels: float, encrypted_path: str
    ) -> None:
        """One file per run. Repeating the write for the same run writes nothing new."""
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO files (run_id, mime, page_count, megapixels, "
                "encrypted_path) VALUES (?, ?, ?, ?, ?)",
                (run_id, mime, page_count, megapixels, encrypted_path),
            )

    def file_mime(self, run_id: str) -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT mime FROM files WHERE run_id = ?", (run_id,)).fetchone()
        return str(row["mime"])

    # ------------------------------------------------------------------ keyed writes
    def record_decision(
        self,
        *,
        decision_id: str,
        run_id: str,
        form_version: int,
        target: str,
        action: str,
        value: str | None,
        reason: str | None,
        reviewer: str,
    ) -> bool:
        """Return True when the decision is new, False when its key was already applied."""
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO review_decisions (decision_id, run_id, form_version, target, action, "
                "value_enc, reason, reviewer) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(decision_id) DO NOTHING",
                (decision_id, run_id, form_version, target, action, value, reason, reviewer),
            )
            return cur.rowcount == 1

    def record_approval(
        self, *, action_id: str, run_id: str, form_version: int, reviewer: str
    ) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO approvals (action_id, run_id, form_version, reviewer) "
                "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (action_id, run_id, form_version, reviewer),
            )
            return cur.rowcount == 1

    def approval_for(self, run_id: str, form_version: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE run_id = ? AND form_version = ?",
                (run_id, form_version),
            ).fetchone()
        return dict(row) if row else None

    def record_submission(
        self,
        *,
        action_id: str,
        run_id: str,
        form_version: int,
        form_json: str,
        approved_by: str,
    ) -> SubmissionRow:
        """At most one submission per approved form version (FR-027)."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO submissions (submission_id, action_id, run_id, form_version, "
                "form_enc, approved_by) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (str(uuid.uuid4()), action_id, run_id, form_version, form_json, approved_by),
            )
            row = conn.execute(
                "SELECT submission_id, run_id, form_version, verified FROM submissions "
                "WHERE action_id = ? OR (run_id = ? AND form_version = ?) LIMIT 1",
                (action_id, run_id, form_version),
            ).fetchone()
        verified = None if row["verified"] is None else bool(row["verified"])
        return SubmissionRow(row["submission_id"], row["run_id"], row["form_version"], verified)

    def read_submission(self, submission_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)
            ).fetchone()
        return dict(row) if row else None

    def set_submission_verified(self, submission_id: str, verified: bool) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE submissions SET verified = ? WHERE submission_id = ?",
                (int(verified), submission_id),
            )

    def record_audit(
        self,
        *,
        event_key: str,
        run_id: str,
        action: str,
        actor: str,
        target: str | None = None,
        old: str | None = None,
        new: str | None = None,
        reason: str | None = None,
    ) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO audit_events (event_key, seq, run_id, action, target, old_enc, "
                "new_enc, reason, actor) VALUES (?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM "
                "audit_events WHERE run_id = ?), ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(event_key) DO NOTHING",
                (event_key, run_id, run_id, action, target, old, new, reason, actor),
            )
            return cur.rowcount == 1

    def audit_events(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events WHERE run_id = ? ORDER BY seq", (run_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def record_capture(
        self,
        *,
        capture_key: str,
        run_id: str,
        field: str,
        read_value_enc: str,
        corrected_value_enc: str,
        fault_group: str,
    ) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO captured_corrections (capture_key, run_id, field, read_value_enc, "
                "corrected_value_enc, fault_group) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(capture_key) DO NOTHING",
                (capture_key, run_id, field, read_value_enc, corrected_value_enc, fault_group),
            )
            return cur.rowcount == 1
