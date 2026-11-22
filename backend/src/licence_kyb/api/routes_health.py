"""Liveness and readiness (docs/engineering-practices.md, section 9)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Request, Response, status

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, str]:
    state = request.app.state

    def database() -> object:
        return state.db.schema_version()

    def checkpoints() -> object:
        return state.checkpointer.conn.execute("SELECT 1").fetchone()

    checks = {"database": _probe(database), "checkpoints": _probe(checkpoints)}
    if any(value != "ok" for value in checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks


def _probe(check: Callable[[], object]) -> str:
    try:
        check()
    except (sqlite3.Error, OSError):
        return "unavailable"
    return "ok"
