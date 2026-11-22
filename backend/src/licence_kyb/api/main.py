"""ASGI entry point: ``uvicorn licence_kyb.api.main:app``.

Fails fast at startup when a required secret is missing (twelve-factor config).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time

from licence_kyb.api.app import create_app
from licence_kyb.clock import FixedClock, SystemClock
from licence_kyb.config import Settings, active_profile, active_profile_name
from licence_kyb.llm.client import AnthropicTransport, DailyBudget, LLMClient, Transport
from licence_kyb.llm.openai_compatible import OpenAICompatibleTransport
from licence_kyb.logging import configure_logging
from licence_kyb.pipeline import Deps, Pipeline
from licence_kyb.security import Cipher


def model_transport(settings: Settings) -> Transport:
    """Demo answers when asked for; otherwise the provider of the active model profile."""
    log = logging.getLogger(__name__)
    if settings.demo_answers_dir is not None:
        log.warning(
            "DEMO MODE: answers come from synthetic case labels, not a model",
            extra={"cases": str(settings.demo_answers_dir)},
        )
        # Imported only in demo mode: test-data libraries are not in the production image.
        from licence_kyb.testdata.answers import LabelDemoTransport  # noqa: PLC0415

        return LabelDemoTransport(settings.demo_answers_dir)
    profile = active_profile()
    log.info(
        "model profile",
        extra={"profile": active_profile_name() or "default", "provider": profile.provider},
    )
    if profile.provider == "openai_compatible":
        if profile.base_url is None:
            raise SystemExit("the model profile needs a base_url (config/models.yaml)")
        price = profile.price_per_mtok
        key = settings.model_api_key.get_secret_value() if settings.model_api_key else None
        return OpenAICompatibleTransport.for_url(
            profile.base_url,
            vision=profile.vision,
            api_key=key,
            timeout_seconds=profile.deadline_seconds or 900.0,
            prices=(price.input, price.output, price.cache_read) if price else (0.0, 0.0, 0.0),
        )
    key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    return AnthropicTransport(key)


def build() -> object:
    configure_logging()
    settings = Settings()
    if not settings.fernet_keys:
        raise SystemExit("FERNET_KEYS is required (see .env.example)")
    if settings.session_secret is None:
        raise SystemExit("SESSION_SECRET is required (see .env.example)")
    deps = Deps(
        data_dir=settings.data_dir,
        cipher=Cipher([k.get_secret_value() for k in settings.fernet_keys]),
        llm=LLMClient(model_transport(settings), DailyBudget(settings.daily_token_budget)),
        clock=FixedClock(datetime.combine(settings.demo_today, time(9), tzinfo=UTC))
        if settings.demo_today
        else SystemClock(),
        applicant_threshold=settings.applicant_name_threshold,
    )
    return create_app(data_dir=settings.data_dir, settings=settings, pipeline=Pipeline(deps))


app = build()
