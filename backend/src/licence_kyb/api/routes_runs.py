"""Runs: upload, list, view and page images (contracts/http-api.md)."""

from __future__ import annotations

import logging
import threading
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from licence_kyb.api.auth import error_response
from licence_kyb.api.schemas import (
    ErrorOut,
    RunCreated,
    RunList,
    RunSummary,
    RunView,
    UploadRejected,
)
from licence_kyb.api.views import build_run_view
from licence_kyb.nodes.intake import MAX_BYTES
from licence_kyb.pipeline import Pipeline

RUN_LIST_LIMIT = 200

router = APIRouter(prefix="/api/runs", tags=["runs"])
log = logging.getLogger(__name__)


def _pipeline(request: Request) -> Pipeline:
    pipeline: Pipeline = request.app.state.pipeline
    return pipeline


def process_in_background(pipeline: Pipeline, run_id: str) -> None:
    """Process a run. An error sends the run to review, so it never stays stuck (FR-039)."""
    try:
        pipeline.process(run_id)
    except Exception:  # any error: the reviewer takes over
        log.exception("processing failed", extra={"run_id": run_id})
        pipeline.mark_failed(run_id)


def resume_unfinished_runs(pipeline: Pipeline) -> threading.Thread:
    """After a restart, process again every run left in received or processing (FR-030).

    A background thread does the work, so the API answers requests at once.
    """

    def resume(run_id: str) -> None:
        process_in_background(pipeline, run_id)

    def resume_all() -> None:
        pipeline.ops.resume_on_startup(resume)

    thread = threading.Thread(target=resume_all, name="resume-runs", daemon=True)
    thread.start()
    return thread


@router.post(
    "",
    status_code=202,
    response_model=RunCreated,
    responses={200: {"model": RunCreated}, 422: {"model": UploadRejected}},
)
async def create_run(
    request: Request,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    applicant_name: Annotated[str, Form(min_length=1, max_length=200)],
) -> RunCreated | JSONResponse:
    data = await file.read(MAX_BYTES + 1)
    pipeline = _pipeline(request)
    result = pipeline.upload(data, applicant_name=applicant_name)
    if result.reason_code is not None:
        return JSONResponse(
            {"reason_code": result.reason_code, "run_id": result.run_id}, status_code=422
        )
    assert result.run_id is not None  # noqa: S101 - intake always returns a run id on success
    if result.duplicate:
        run = pipeline.db.get_run(result.run_id)
        status = run["status"] if run else "received"
        return JSONResponse(
            {"run_id": result.run_id, "status": status, "duplicate": True}, status_code=200
        )
    background.add_task(process_in_background, pipeline, result.run_id)
    return RunCreated(run_id=result.run_id, status="processing")


@router.get("", response_model=RunList)
def list_runs(request: Request) -> RunList:
    pipeline = _pipeline(request)
    cipher = pipeline.deps.cipher
    summaries: list[RunSummary] = []
    for row in pipeline.db.list_runs(limit=RUN_LIST_LIMIT):
        row["applicant_name"] = cipher.decrypt_text(row["applicant_name"])
        summaries.append(RunSummary(**row))
    return RunList(runs=summaries)


@router.get("/{run_id}", response_model=RunView, responses={404: {"model": ErrorOut}})
def get_run(run_id: str, request: Request) -> RunView | JSONResponse:
    view = build_run_view(_pipeline(request), run_id)
    if view is None:
        return error_response(404, "not_found")
    return view


@router.get(
    "/{run_id}/pages/{page}",
    responses={200: {"content": {"image/png": {}}}, 404: {"model": ErrorOut}},
)
def get_page(run_id: str, page: int, request: Request) -> Response:
    try:
        png = _pipeline(request).page_png(run_id, page)
    except FileNotFoundError:
        return error_response(404, "not_found")
    return Response(
        content=png, media_type="image/png", headers={"Cache-Control": "private, no-store"}
    )
