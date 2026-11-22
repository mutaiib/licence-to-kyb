"""ASGI entry point: ``uvicorn licence_kyb.api.main:app``."""

from __future__ import annotations

from licence_kyb.api.app import create_app
from licence_kyb.config import Settings
from licence_kyb.logging import configure_logging

configure_logging()
app = create_app(data_dir=Settings().data_dir)
