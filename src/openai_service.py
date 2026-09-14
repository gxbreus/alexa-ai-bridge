from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from openai import APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from .config import ConfigurationError, Settings
from .prompts import ASSISTANT_INSTRUCTIONS
from .deadline import RequestDeadlineExceeded

logger = logging.getLogger(__name__)

_MARKDOWN_LINK = re.compile(r"\s*\(\[([^\]]+)\]\([^)]*\)\)")
_RAW_URL = re.compile(r"\s*https?://\S+")


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
            "max_output_tokens": 120,
            # A resposta só é gerada depois de uma busca: o modelo não decide
            # silenciosamente responder a partir de conhecimento não verificado.
            "tools": [{"type": "web_search", "search_context_size": "low"}],
            "tool_choice": "required",
            "include": ["web_search_call.action.sources"],
        }
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id

        started = time.perf_counter()
        logger.info(json.dumps({"event": "openai_call_start", "model": self._settings.openai_model}))
        try:
            response = self._client.responses.create(**payload)
        except (APITimeoutError, RequestDeadlineExceeded) as error:
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

        text = _spoken_text(getattr(response, "output_text", None) or "")
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


def _spoken_text(text: str) -> str:
    """Remove links de citações que não podem ser reproduzidos pela Alexa."""
    text = _MARKDOWN_LINK.sub(r". Fonte: \1.", text)
    text = _RAW_URL.sub("", text)
    return text.replace(".. Fonte:", ". Fonte:").strip()


@lru_cache(maxsize=1)
def get_openai_service() -> OpenAIService:
    started = time.perf_counter()
    logger.info(json.dumps({"event": "openai_client_init_start"}))
    try:
        service = OpenAIService(Settings.from_environment())
        logger.info(json.dumps({"event": "openai_client_init_ready",
                                "latency_ms": round((time.perf_counter() - started) * 1000)}))
        return service
    except ConfigurationError as error:
        raise OpenAIServiceError("configuration") from error
