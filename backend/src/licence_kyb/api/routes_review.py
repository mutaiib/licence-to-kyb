"""Reviewer actions on a run: review, submit, reopen and retry (contracts/http-api.md, US2).

Each endpoint builds one action, and the pipeline checks it before it resumes the paused
run. A refused action is answered with 409 and an error code; nothing changes.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from licence_kyb.api.schemas import (
    ActionErrorOut,
    ErrorOut,
    ReopenIn,
    RetryIn,
    ReviewIn,
    RunCreated,
    RunView,
    SubmitIn,
    SubmitOut,
)
from licence_kyb.api.views import build_run_view
from licence_kyb.nodes.review import ActionRefused
from licence_kyb.pipeline import Pipeline

router = APIRouter(prefix="/api/runs", tags=["review"])
log = logging.getLogger(__name__)
ERRORS: dict[int | str, dict[str, Any]] = {404: {"model": ErrorOut}, 409: {"model": ActionErrorOut}}


def _pipeline(request: Request) -> Pipeline:
    pipeline: Pipeline = request.app.state.pipeline
    return pipeline


def _action(request: Request, kind: str, body: Any) -> dict[str, Any]:
    reviewer = request.app.state.auth.reviewer(request)
    return {"kind": kind, "reviewer": reviewer, **body.model_dump(mode="json")}


def _refused(error: ActionRefused) -> JSONResponse:
    return JSONResponse(error.body(), status_code=409)


def _not_found() -> JSONResponse:
    return JSONResponse({"code": "not_found"}, status_code=404)


def retry_in_background(pipeline: Pipeline, run_id: str, action: dict[str, Any]) -> None:
    """Process the run again. An error sends it back to review, as on the first attempt."""
    try:
        pipeline.act(run_id, action)
    except Exception:
        log.exception("retry failed", extra={"run_id": run_id})
        pipeline.mark_failed(run_id)


def _act_and_view(request: Request, run_id: str, action: dict[str, Any]) -> RunView | JSONResponse:
    pipeline = _pipeline(request)
    if pipeline.db.get_run(run_id) is None:
        return _not_found()
    try:
        pipeline.act(run_id, action)
    except ActionRefused as error:
        return _refused(error)
    view = build_run_view(pipeline, run_id)
    return view if view is not None else _not_found()


@router.post("/{run_id}/review", response_model=RunView, responses=ERRORS)
def review_run(run_id: str, body: ReviewIn, request: Request) -> RunView | JSONResponse:
    """Apply field decisions; optionally approve or reject the whole form."""
    return _act_and_view(request, run_id, _action(request, "review", body))


@router.post("/{run_id}/reopen", response_model=RunView, responses=ERRORS)
def reopen_run(run_id: str, body: ReopenIn, request: Request) -> RunView | JSONResponse:
    return _act_and_view(request, run_id, _action(request, "reopen", body))


@router.post("/{run_id}/submit", response_model=SubmitOut, responses=ERRORS)
def submit_run(run_id: str, body: SubmitIn, request: Request) -> SubmitOut | JSONResponse:
    """Store the approved form once. A repeated call returns the same submission."""
    pipeline = _pipeline(request)
    if pipeline.db.get_run(run_id) is None:
        return _not_found()
    action = _action(request, "submit", body)
    earlier = pipeline.submission_for(run_id, action)
    if earlier is not None:
        return SubmitOut(**earlier)
    try:
        state = pipeline.act(run_id, action)
    except ActionRefused as error:
        return _refused(error)
    return SubmitOut(**state["submission"])


@router.post("/{run_id}/retry", status_code=202, response_model=RunCreated, responses=ERRORS)
def retry_run(
    run_id: str, body: RetryIn, request: Request, background: BackgroundTasks
) -> RunCreated | JSONResponse:
    """Process the run again from the step that failed. Processing runs in the background."""
    pipeline = _pipeline(request)
    if pipeline.db.get_run(run_id) is None:
        return _not_found()
    action = _action(request, "retry", body)
    try:
        pipeline.check(run_id, action)
    except ActionRefused as error:
        return _refused(error)
    background.add_task(retry_in_background, pipeline, run_id, action)
    return RunCreated(run_id=run_id, status="processing")
