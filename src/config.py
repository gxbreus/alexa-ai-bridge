from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when an essential deployment setting is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    alexa_skill_id: str | None
    openai_timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "Settings":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()
        timeout_value = os.getenv("OPENAI_TIMEOUT_SECONDS", "7").strip()
        if not key:
            raise ConfigurationError("OPENAI_API_KEY is not configured")
        if not model:
            raise ConfigurationError("OPENAI_MODEL is not configured")
        try:
            timeout = float(timeout_value)
        except ValueError as error:
            raise ConfigurationError("OPENAI_TIMEOUT_SECONDS must be numeric") from error
        if not 1 <= timeout <= 20:
            raise ConfigurationError("OPENAI_TIMEOUT_SECONDS must be between 1 and 20")
        return cls(key, model, os.getenv("ALEXA_SKILL_ID") or None, timeout)
