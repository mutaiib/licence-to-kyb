"""ASGI entry point: ``uvicorn licence_kyb.api.main:app``.

Fails fast at startup when a required secret is missing (twelve-factor config).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time

from licence_kyb.api.app import create_app
from licence_kyb.clock import FixedClock, SystemClock
from licence_kyb.config import Settings
from licence_kyb.llm.client import AnthropicTransport, DailyBudget, LLMClient, Transport
from licence_kyb.logging import configure_logging
from licence_kyb.pipeline import Deps, Pipeline
from licence_kyb.security import Cipher
from licence_kyb.testdata.answers import LabelDemoTransport


def build() -> object:
    configure_logging()
    settings = Settings()
    if not settings.fernet_keys:
        raise SystemExit("FERNET_KEYS is required (see .env.example)")
    if settings.session_secret is None:
        raise SystemExit("SESSION_SECRET is required (see .env.example)")
    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    transport: Transport = AnthropicTransport(api_key)
    if settings.demo_answers_dir is not None:
        logging.getLogger(__name__).warning(
            "DEMO MODE: answers come from synthetic case labels, not a model",
            extra={"cases": str(settings.demo_answers_dir)},
        )
        transport = LabelDemoTransport(settings.demo_answers_dir)
    deps = Deps(
        data_dir=settings.data_dir,
        cipher=Cipher([k.get_secret_value() for k in settings.fernet_keys]),
        llm=LLMClient(transport, DailyBudget(settings.daily_token_budget)),
        clock=FixedClock(datetime.combine(settings.demo_today, time(9), tzinfo=UTC))
        if settings.demo_today
        else SystemClock(),
        applicant_threshold=settings.applicant_name_threshold,
    )
    return create_app(data_dir=settings.data_dir, settings=settings, pipeline=Pipeline(deps))


app = build()
