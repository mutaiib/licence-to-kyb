"""FastAPI application factory. Routes are added per user story."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from licence_kyb.api import routes_health
from licence_kyb.graph import open_checkpointer
from licence_kyb.store.db import Database


def create_app(*, data_dir: Path) -> FastAPI:
    app = FastAPI(
        title="licence-to-kyb",
        version="0.0.0",
        description="Trade licence to KYB onboarding (contracts/http-api.md).",
    )
    db = Database(data_dir / "app.sqlite3")
    db.migrate()
    app.state.db = db
    app.state.checkpointer = open_checkpointer(data_dir / "checkpoints.sqlite3")
    app.include_router(routes_health.router)
    return app
