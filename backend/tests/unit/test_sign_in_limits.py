"""The sign-in limit holds under parallel requests, and timing does not reveal accounts."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from argon2 import PasswordHasher

from licence_kyb.api.auth import MAX_FAILURES, Auth
from licence_kyb.config import Settings


def auth() -> Auth:
    return Auth(
        Settings(
            reviewer_accounts={"reviewer1": PasswordHasher().hash("right")},  # type: ignore[dict-item]
            session_secret="s" * 32,  # type: ignore[arg-type]
        )
    )


def test_parallel_wrong_passwords_get_no_more_tries_than_the_limit() -> None:
    a = auth()
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(
            pool.map(lambda _: a.check_password("reviewer1", "wrong", "1.2.3.4"), range(20))
        )

    assert results.count("invalid") == MAX_FAILURES
    assert results.count("rate_limited") == 20 - MAX_FAILURES


def test_a_right_password_does_not_use_up_a_try() -> None:
    a = auth()
    for _ in range(MAX_FAILURES - 1):
        a.check_password("reviewer1", "wrong", "1.2.3.4")

    assert a.check_password("reviewer1", "right", "1.2.3.4") == "ok"
    assert a.check_password("reviewer1", "wrong", "1.2.3.4") == "invalid"  # still one try left


def test_an_unknown_user_takes_as_long_as_a_known_one() -> None:
    a = auth()

    def seconds(user: str, ip: str) -> float:
        start = time.perf_counter()
        a.check_password(user, "wrong", ip)
        return time.perf_counter() - start

    known = seconds("reviewer1", "10.0.0.1")
    unknown = seconds("nobody", "10.0.0.2")

    assert unknown > known / 3  # same order: both run argon2
