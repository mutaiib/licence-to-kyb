"""Structured JSON logs with the run ID on every line and personal data masked."""

from __future__ import annotations

import contextvars
import logging

from pythonjsonlogger.json import JsonFormatter

from licence_kyb.security import PiiMaskingFilter

current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("run_id", default=None)


class RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = current_run_id.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RunIdFilter())
    handler.addFilter(PiiMaskingFilter())
    handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(run_id)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
