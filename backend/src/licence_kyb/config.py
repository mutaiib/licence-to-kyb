"""Typed settings from the environment, plus the versioned YAML configuration files.

Secrets come only from the environment (twelve-factor). Nothing secret lives in a file
in the repository.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr | None = None
    fernet_keys: Annotated[list[SecretStr], NoDecode] = Field(default_factory=list)
    reviewer_accounts: Annotated[dict[str, SecretStr], NoDecode] = Field(default_factory=dict)
    """User name → argon2id hash. Each reviewer has an individual account."""

    daily_token_budget: int = Field(default=2_000_000, ge=0)
    retention_days: int = Field(default=30, ge=1)
    applicant_name_threshold: float = Field(default=0.85, ge=0, le=1)
    data_dir: Path = Path("var")
    session_hours: int = Field(default=8, ge=1)
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


class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    route: StepModel
    extract_primary: StepModel
    extract_secondary: StepModel
    resolve: StepModel
    reread_vision: StepModel


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


def models_config() -> ModelsConfig:
    return ModelsConfig.model_validate(load_yaml("models.yaml"))


def budgets_config() -> BudgetsConfig:
    return BudgetsConfig.model_validate(load_yaml("budgets.yaml"))
