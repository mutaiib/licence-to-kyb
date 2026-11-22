"""Reviewer authentication: signed session cookies, CSRF and sign-in rate limits (FR-022).

- Passwords are argon2id hashes from configuration; each reviewer has an individual account.
- The session cookie is ``user|expiry|hmac``: HttpOnly, SameSite=Strict, Secure, 8 hours.
- CSRF uses a double-submit token: a readable ``csrf`` cookie that state-changing requests
  must echo in ``X-CSRF-Token``.
- More than 5 failed sign-ins in 60 seconds for an account or an IP returns 429.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from licence_kyb.config import Settings
from licence_kyb.store.db import Database

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf"
CSRF_HEADER = "X-CSRF-Token"
MAX_FAILURES = 5
WINDOW_SECONDS = 60.0
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


SignInResult = Literal["ok", "invalid", "rate_limited"]


def error_response(status: int, code: str) -> JSONResponse:
    return JSONResponse({"code": code}, status_code=status)


class Auth:
    def __init__(self, settings: Settings, db: Database | None = None) -> None:
        """``db`` stores revoked sessions; without it (tests of passwords only), sign-out
        cannot end a session on the server."""
        self.settings = settings
        self._db = db
        secret = settings.session_secret.get_secret_value() if settings.session_secret else None
        self._key = (secret or secrets.token_hex(32)).encode()
        self._hasher = PasswordHasher()
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        # Checked when the user name is unknown, so the reply takes as long as for a real one.
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(16))

    # ---------------------------------------------------------------- passwords + limits
    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        return q

    def check_password(self, username: str, password: str, ip: str) -> SignInResult:
        now = time.monotonic()
        keys = (f"user:{username}", f"ip:{ip}")
        # Count the try before the slow check, under a lock: parallel requests then cannot
        # all pass the limit before the first failure is stored.
        with self._lock:
            if any(len(self._recent(k, now)) >= MAX_FAILURES for k in keys):
                return "rate_limited"
            for k in keys:
                self._recent(k, now).append(now)
        stored = self.settings.reviewer_accounts.get(username)
        hashed = stored.get_secret_value() if stored is not None else self._dummy_hash
        try:
            ok = self._hasher.verify(hashed, password) and stored is not None
        except (VerificationError, InvalidHashError):
            ok = False
        if not ok:
            return "invalid"
        with self._lock:  # a right password does not use up a try
            for k in keys:
                self._recent(k, now).remove(now)
        return "ok"

    # ---------------------------------------------------------------- sessions
    def _sign(self, payload: str) -> str:
        return hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()

    def issue(self, response: Response, username: str) -> None:
        expiry = int(time.time() + self.settings.session_hours * 3600)
        session_id = secrets.token_urlsafe(16)  # lets sign-out end this session on the server
        payload = f"{username}|{session_id}|{expiry}"
        secure = self.settings.cookie_secure
        response.set_cookie(
            SESSION_COOKIE,
            f"{payload}|{self._sign(payload)}",
            httponly=True,
            secure=secure,
            samesite="strict",
            max_age=self.settings.session_hours * 3600,
        )
        response.set_cookie(
            CSRF_COOKIE,
            secrets.token_urlsafe(32),
            httponly=False,
            secure=secure,
            samesite="strict",
            max_age=self.settings.session_hours * 3600,
        )

    @staticmethod
    def clear(response: Response) -> None:
        response.delete_cookie(SESSION_COOKIE)
        response.delete_cookie(CSRF_COOKIE)

    def _session(self, request: Request) -> tuple[str, str, int] | None:
        """(user, session ID, expiry) of a valid, unexpired session cookie; else None."""
        parts = request.cookies.get(SESSION_COOKIE, "").split("|")
        if len(parts) != 4:  # noqa: PLR2004 - user|session_id|expiry|signature
            return None
        user, session_id, expiry, sig = parts
        if not hmac.compare_digest(sig, self._sign(f"{user}|{session_id}|{expiry}")):
            return None
        if not expiry.isdigit() or int(expiry) < time.time():
            return None
        return user, session_id, int(expiry)

    def reviewer(self, request: Request) -> str | None:
        session = self._session(request)
        if session is None:
            return None
        user, session_id, _ = session
        if self._db is not None and self._db.is_revoked(session_id):
            return None  # signed out: a copied cookie no longer works
        return user if user in self.settings.reviewer_accounts else None

    def revoke(self, request: Request) -> None:
        """End the request's session on the server (sign-out)."""
        session = self._session(request)
        if session is not None and self._db is not None:
            self._db.revoke_session(session[1], session[2])

    @staticmethod
    def csrf_ok(request: Request) -> bool:
        cookie = request.cookies.get(CSRF_COOKIE)
        header = request.headers.get(CSRF_HEADER)
        return bool(cookie) and bool(header) and hmac.compare_digest(cookie or "", header or "")
