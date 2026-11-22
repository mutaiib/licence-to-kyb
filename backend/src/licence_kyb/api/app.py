"""FastAPI application factory (contracts/http-api.md)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response

from licence_kyb.api import routes_health, routes_review, routes_runs, routes_session
from licence_kyb.api.auth import SAFE_METHODS, Auth, error_response
from licence_kyb.config import Settings
from licence_kyb.graph import open_checkpointer
from licence_kyb.pipeline import Pipeline
from licence_kyb.store.db import Database

PUBLIC = {("POST", "/api/session")}


def create_app(
    *, data_dir: Path, settings: Settings | None = None, pipeline: Pipeline | None = None
) -> FastAPI:
    """The API app. ``main.py`` always passes a pipeline.

    Without a pipeline, only the health, session and OpenAPI parts work: the health tests and
    scripts/export_openapi.py use that. The run routes need a pipeline.
    """
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if pipeline is not None:
            routes_runs.resume_unfinished_runs(pipeline)
        yield

    app = FastAPI(
        title="licence-to-kyb",
        version="0.0.0",
        description="Trade licence to KYB onboarding (contracts/http-api.md).",
        lifespan=lifespan,
    )
    if pipeline is not None:
        app.state.pipeline = pipeline
        app.state.db = pipeline.db
        app.state.checkpointer = pipeline.checkpointer
    else:
        db = Database(data_dir / "app.sqlite3")
        db.migrate()
        app.state.db = db
        app.state.checkpointer = open_checkpointer(data_dir / "checkpoints.sqlite3")
    app.state.auth = Auth(settings)

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path, method = request.url.path, request.method
        if path.startswith("/api/") and (method, path) not in PUBLIC:
            if app.state.auth.reviewer(request) is None:
                return error_response(401, "session_expired")
            if method not in SAFE_METHODS and not Auth.csrf_ok(request):
                return error_response(403, "forbidden")
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(routes_health.router)
    app.include_router(routes_session.router)
    app.include_router(routes_runs.router)
    app.include_router(routes_review.router)
    return app
