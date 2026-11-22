"""Sign-in and sign-out (contracts/http-api.md)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from licence_kyb.api.auth import Auth, error_response
from licence_kyb.api.schemas import ErrorOut, SessionIn, SessionOut

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post(
    "", response_model=SessionOut, responses={401: {"model": ErrorOut}, 429: {"model": ErrorOut}}
)
def sign_in(body: SessionIn, request: Request, response: Response) -> SessionOut | JSONResponse:
    auth: Auth = request.app.state.auth
    ip = request.client.host if request.client else "unknown"
    result = auth.check_password(body.username, body.password, ip)
    if result == "rate_limited":
        return error_response(429, "rate_limited")
    if result == "invalid":
        return error_response(401, "invalid_credentials")
    auth.issue(response, body.username)
    return SessionOut(reviewer=body.username)


@router.delete("", status_code=204)
def sign_out(response: Response) -> Response:
    Auth.clear(response)
    response.status_code = 204
    return response
