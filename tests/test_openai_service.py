from types import SimpleNamespace

import pytest

from src.config import ConfigurationError, Settings
from src.openai_service import OpenAIService, OpenAIServiceError


class FakeResponses:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.payloads = []

    def create(self, **kwargs):
        self.payloads.append(kwargs)
        if self.error:
            raise self.error
        return self.result


def service(responses):
    return OpenAIService(
        Settings("not-a-real-key", "gpt-5.6-luna", None, 7),
        client=SimpleNamespace(responses=responses),
    )


def test_first_question_uses_responses_api_without_previous_id():
    responses = FakeResponses(SimpleNamespace(id="ABC", output_text="Johnny Depp é ator."))
    result = service(responses).ask("Quem é Johnny Depp?")
    assert result.response_id == "ABC"
    assert result.text == "Johnny Depp é ator."
    assert "previous_response_id" not in responses.payloads[0]
    assert responses.payloads[0]["reasoning"] == {"effort": "none"}


def test_second_and_third_questions_keep_response_chain():
    responses = FakeResponses(SimpleNamespace(id="DEF", output_text="Ele tem 63 anos."))
    service(responses).ask("Quantos anos ele tem?", previous_response_id="ABC")
    assert responses.payloads[0]["previous_response_id"] == "ABC"
    responses.result = SimpleNamespace(id="GHI", output_text="Participou de diversos filmes.")
    service(responses).ask("Em quais filmes ele participou?", previous_response_id="DEF")
    assert responses.payloads[1]["previous_response_id"] == "DEF"


def test_empty_response_is_a_safe_error():
    with pytest.raises(OpenAIServiceError, match="OpenAI request failed") as error:
        service(FakeResponses(SimpleNamespace(id="ABC", output_text="  "))).ask("teste")
    assert error.value.kind == "empty_response"


def test_timeout_is_classified(monkeypatch):
    class FakeTimeout(Exception):
        pass

    import src.openai_service as module
    monkeypatch.setattr(module, "APITimeoutError", FakeTimeout)
    with pytest.raises(OpenAIServiceError) as error:
        service(FakeResponses(error=FakeTimeout())).ask("teste")
    assert error.value.kind == "timeout"


def test_missing_api_key_is_rejected(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        Settings.from_environment()
