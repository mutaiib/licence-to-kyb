"""Typed settings from the environment, plus the versioned YAML configuration files.

Secrets come only from the environment (twelve-factor). Nothing secret lives in a file
in the repository.
"""

from __future__ import annotations

import json
import os
from datetime import date
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
CONFIG_DIR = BACKEND_DIR / "config"
DATA_DIR = REPO_ROOT / "data"
"""Versioned reference data: activity lists, high-risk activities and the mock register."""

APPLICANT_NAME_THRESHOLD = 0.85
"""How close the application's business name must be to the licence's trade name (0 to 1)."""

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr | None = None
    model_api_key: SecretStr | None = None
    """For a hosted OpenAI-compatible provider. A local model server needs none."""
    fernet_keys: Annotated[list[SecretStr], NoDecode] = Field(default_factory=list)
    reviewer_accounts: Annotated[dict[str, SecretStr], NoDecode] = Field(default_factory=dict)
    """User name → argon2id hash. Each reviewer has an individual account."""

    daily_token_budget: int = Field(default=2_000_000, ge=0)
    retention_days: int = Field(default=30, ge=1)
    applicant_name_threshold: float = Field(default=APPLICANT_NAME_THRESHOLD, ge=0, le=1)
    data_dir: Path = Path("var")
    session_hours: int = Field(default=8, ge=1)
    demo_answers_dir: Path | None = None
    """Local demo only: answer from synthetic case labels instead of a model."""
    demo_today: date | None = None
    """Local demo only: the fixed date the synthetic catalogue was generated for."""
    session_secret: SecretStr | None = None
    """HMAC key for session cookies. Required in production; set it in the environment."""
    cookie_secure: bool = True

    @field_validator("fernet_keys", mode="before")
    @classmethod
    def _split_keys(cls, raw: Any) -> Any:
        if isinstance(raw, str):
            return [k.strip() for k in raw.split(",") if k.strip()]
        return raw

    @field_validator("reviewer_accounts", mode="before")
    @classmethod
    def _parse_accounts(cls, raw: Any) -> Any:
        if isinstance(raw, str):
            return json.loads(raw) if raw.strip() else {}
        return raw


class StepModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model: str
    effort: Effort
    max_tokens: int = Field(gt=0)


STEPS = ("route", "extract_primary", "extract_secondary", "resolve", "reread_vision")


class ModelsConfig(BaseModel):
    """The model and effort for each step."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    route: StepModel
    extract_primary: StepModel
    extract_secondary: StepModel
    # resolve and reread_vision: used from User Story 4 (the resolver).
    resolve: StepModel
    reread_vision: StepModel


class Prices(BaseModel):
    """USD per million tokens."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    input: float = Field(ge=0)
    output: float = Field(ge=0)
    cache_read: float = Field(default=0, ge=0)


class ModelProfile(BaseModel):
    """One way to run every model step: a provider, its models and what they can do
    (ADR-004). ``MODEL_PROFILE`` picks one; ``models.yaml`` names the default."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: Literal["anthropic", "openai_compatible"]
    base_url: str | None = None
    vision: bool = True
    price_per_mtok: Prices | None = None
    """None: the provider's published prices (``llm/client.py``)."""
    deadline_seconds: float | None = None
    """Overrides ``budgets.yaml`` for a slower model, such as one on a CPU."""
    steps: ModelsConfig


# Used from User Story 4 (the resolver).
class ResolverBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    soft_turns: int
    hard_turns: int
    hard_rounds: int
    soft_tokens: int
    hard_tokens: int
    soft_seconds: float
    hard_seconds: float
    hard_tool_calls: int


class BudgetsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    processing_deadline_seconds: float
    resolver: ResolverBudget


@cache
def load_yaml(name: str, directory: Path = CONFIG_DIR) -> dict[str, Any]:
    data = yaml.safe_load((directory / name).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a mapping")
    return data


def load_model_profile(name: str | None) -> ModelProfile:
    """The named profile, or the default when ``name`` is None."""
    data = load_yaml("models.yaml")
    profiles: dict[str, Any] = data["profiles"]
    chosen = name or data["default"]
    if chosen not in profiles:
        valid = ", ".join(sorted(profiles))
        raise ValueError(f"unknown model profile {chosen!r}: use one of {valid} (MODEL_PROFILE)")
    return ModelProfile.model_validate(profiles[chosen])


def active_profile_name() -> str | None:
    return os.environ.get("MODEL_PROFILE") or None


def active_profile() -> ModelProfile:
    return load_model_profile(active_profile_name())


def models_config() -> ModelsConfig:
    return active_profile().steps


def budgets_config() -> BudgetsConfig:
    return BudgetsConfig.model_validate(load_yaml("budgets.yaml"))


def processing_deadline_seconds() -> float:
    return active_profile().deadline_seconds or budgets_config().processing_deadline_seconds
