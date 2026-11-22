"""Run untrusted work in a child process with a memory and time limit (security review).

A 2 KB PDF can inflate to gigabytes when its pages are decoded. Reading pages in the API
process would let one upload exhaust its memory and, after a restart, do it again. Here the
child does the reading; the parent watches the child's resident memory and its time, and
stops it past either limit. Only the child can die.

The memory is read from /proc (Linux, as in the container). Where /proc is missing, only the
time limit applies.
"""

from __future__ import annotations

import multiprocessing as mp
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

POLL_SECONDS = 0.05


class TooCostly(Exception):  # noqa: N818 - reads as "the document is too costly"
    """The work went past a limit, or the child failed. The message names which."""


def run_limited(fn: Callable[..., Any], *args: Any, memory_mb: int, seconds: float) -> Any:
    """``fn(*args)`` in a child process. Raises ``TooCostly`` past a limit or on any error."""
    ctx = mp.get_context("spawn")  # never fork a threaded server process
    receive, send = ctx.Pipe(duplex=False)
    child = ctx.Process(target=_child, args=(send, fn, args), daemon=True)
    child.start()
    send.close()
    deadline = time.monotonic() + seconds
    try:
        while not receive.poll(POLL_SECONDS):
            if not child.is_alive():
                raise TooCostly("the child process stopped")
            if time.monotonic() > deadline:
                raise TooCostly("time limit")
            if _resident_mb(child.pid) > memory_mb:
                raise TooCostly("memory limit")
        ok, value = receive.recv()
    except EOFError as exc:
        raise TooCostly("the child process stopped") from exc
    finally:
        if child.is_alive():
            child.kill()
        child.join()
        receive.close()
    if not ok:
        raise TooCostly(value)
    return value


def _child(send: Connection, fn: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        send.send((True, fn(*args)))
    except BaseException as exc:
        send.send((False, type(exc).__name__))
    finally:
        send.close()


def _resident_mb(pid: int | None) -> float:
    """The child's resident memory in MB; 0 where /proc is not available."""
    try:
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return 0.0
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return 0.0
