"""Sign-in and sign-out (contracts/http-api.md)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from licence_kyb.api.auth import ApiError, Auth
from licence_kyb.api.schemas import ErrorOut, SessionIn, SessionOut

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post(
    "", response_model=SessionOut, responses={401: {"model": ErrorOut}, 429: {"model": ErrorOut}}
)
def sign_in(body: SessionIn, request: Request, response: Response) -> SessionOut | JSONResponse:
    auth: Auth = request.app.state.auth
    ip = request.client.host if request.client else "unknown"
    try:
        ok = auth.check_password(body.username, body.password, ip)
    except ApiError as err:
        return JSONResponse({"code": err.code}, status_code=err.status)
    if not ok:
        return JSONResponse({"code": "invalid_credentials"}, status_code=401)
    auth.issue(response, body.username)
    return SessionOut(reviewer=body.username)


@router.delete("", status_code=204)
def sign_out(response: Response) -> Response:
    Auth.clear(response)
    response.status_code = 204
    return response
