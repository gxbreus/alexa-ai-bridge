from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from openai import APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from .config import ConfigurationError, Settings
from .prompts import ASSISTANT_INSTRUCTIONS

logger = logging.getLogger(__name__)


class OpenAIServiceError(RuntimeError):
    """A safe, classified error that callers can expose generically."""

    def __init__(self, kind: str, message: str = "OpenAI request failed") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class AIAnswer:
    text: str
    response_id: str


class OpenAIService:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client or OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=0,
        )

    def ask(self, question: str, previous_response_id: str | None = None) -> AIAnswer:
        if not question or not question.strip():
            raise OpenAIServiceError("empty_query")
        payload: dict[str, Any] = {
            "model": self._settings.openai_model,
            "instructions": ASSISTANT_INSTRUCTIONS,
            "input": question.strip(),
            "reasoning": {"effort": "none"},
            "text": {"verbosity": "low"},
            "max_output_tokens": 240,
        }
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id

        started = time.perf_counter()
        try:
            response = self._client.responses.create(**payload)
        except APITimeoutError as error:
            self._log_failure("timeout", started)
            raise OpenAIServiceError("timeout") from error
        except RateLimitError as error:
            self._log_failure("rate_limit", started)
            raise OpenAIServiceError("rate_limit") from error
        except AuthenticationError as error:
            self._log_failure("authentication", started)
            raise OpenAIServiceError("authentication") from error
        except APIStatusError as error:
            self._log_failure("http_status", started)
            raise OpenAIServiceError("http_status") from error
        except Exception as error:
            self._log_failure("unexpected", started)
            raise OpenAIServiceError("unexpected") from error

        text = (getattr(response, "output_text", None) or "").strip()
        response_id = getattr(response, "id", None)
        if not text or not response_id:
            self._log_failure("empty_response", started)
            raise OpenAIServiceError("empty_response")
        logger.info(json.dumps({"event": "openai_response", "model": self._settings.openai_model,
                                 "latency_ms": round((time.perf_counter() - started) * 1000), "success": True}))
        return AIAnswer(text=text, response_id=response_id)

    def _log_failure(self, kind: str, started: float) -> None:
        logger.warning(json.dumps({"event": "openai_response", "model": self._settings.openai_model,
                                    "latency_ms": round((time.perf_counter() - started) * 1000),
                                    "success": False, "error_type": kind}))


@lru_cache(maxsize=1)
def get_openai_service() -> OpenAIService:
    try:
        return OpenAIService(Settings.from_environment())
    except ConfigurationError as error:
        raise OpenAIServiceError("configuration") from error
