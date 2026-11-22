"""Pick the model transport of the active model profile (ADR-004). Used by the API and by
the eval runner, so both call the same models for the same profile."""

from __future__ import annotations

from licence_kyb.config import ModelProfile, Settings
from licence_kyb.llm.client import AnthropicTransport, Transport
from licence_kyb.llm.openai_compatible import OpenAICompatibleTransport


def profile_transport(profile: ModelProfile, settings: Settings) -> Transport:
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
