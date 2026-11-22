"""Operations that keep the system moving: startup resume, deadline sweep, retention.

- On startup, every run left in ``received`` or ``processing`` resumes, with a fresh deadline
  (FR-030). The deadline belongs to the processing attempt, not to the run (FR-039).
- A run past its deadline goes to review with ``processing_failed``, never stays stuck.
- Retention deletes runs, their files and captured corrections after N days (FR-036).
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from licence_kyb.clock import Clock
from licence_kyb.schemas.results import reason_entry
from licence_kyb.store.db import Database

log = logging.getLogger(__name__)


class Operations:
    def __init__(
        self, db: Database, clock: Clock, *, deadline_seconds: float, files_dir: Path | None = None
    ) -> None:
        self.db = db
        self.clock = clock
        self.deadline_seconds = deadline_seconds
        self.files_dir = files_dir

    def new_deadline(self) -> str:
        return (self.clock.now() + timedelta(seconds=self.deadline_seconds)).isoformat()

    def resume_on_startup(self, resume: Callable[[str], None]) -> list[str]:
        runs = self.db.runs_with_status("received", "processing")
        for run in runs:
            self.db.update_run(run["run_id"], deadline_at=self.new_deadline())
            resume(run["run_id"])
        log.info("resumed runs after startup", extra={"count": len(runs)})
        return [r["run_id"] for r in runs]

    def sweep_deadlines(self) -> list[str]:
        now = self.clock.now()
        moved: list[str] = []
        for run in self.db.runs_with_status("processing"):
            deadline = run["deadline_at"]
            if deadline is None or datetime.fromisoformat(deadline) > now:
                continue
            self.send_to_review(run, event="deadline_sweep", note="processing deadline passed")
            moved.append(run["run_id"])
        return moved

    def send_to_review(self, run: dict[str, Any], *, event: str, note: str) -> None:
        """Move ``run`` to review with ``processing_failed``. Repeating it writes nothing new.

        ``event`` names the cause in the audit key; ``note`` is the audit reason text.
        """
        reasons = json.loads(run["reasons_json"])
        if not any(r.get("code") == "processing_failed" for r in reasons):
            reasons.append(reason_entry("processing_failed"))
        self.db.update_run(
            run["run_id"], status="awaiting_review", reasons_json=json.dumps(reasons)
        )
        self.db.record_audit(
            event_key=f"{run['run_id']}:{event}:{run['deadline_at']}",
            run_id=run["run_id"],
            action="status_change",
            actor="system",
            new="awaiting_review",
            reason=note,
        )

    def apply_retention(self, *, days: int) -> int:
        cutoff = (self.clock.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        expired = [
            r["run_id"]
            for r in self.db.runs_with_status(
                "received",
                "processing",
                "rejected",
                "awaiting_review",
                "awaiting_submit",
                "submitted",
                "done",
            )
            if r["created_at"] < cutoff
        ]
        deleted = self.db.delete_runs_created_before(cutoff)
        if self.files_dir is not None:
            for run_id in expired:
                shutil.rmtree(self.files_dir / run_id, ignore_errors=True)
        log.info("retention applied", extra={"deleted_runs": deleted})
        return deleted
