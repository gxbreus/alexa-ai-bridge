from types import SimpleNamespace

from src import alexa_handlers
from src.lambda_function import lambda_handler
from src.openai_service import AIAnswer, OpenAIServiceError


def request(request_type, *, intent_name=None, query=None, attributes=None):
    body = {"type": request_type, "requestId": "request-123", "timestamp": "2026-09-14T12:00:00Z", "locale": "pt-BR"}
    if intent_name:
        body["intent"] = {"name": intent_name, "confirmationStatus": "NONE", "slots": {}}
        if query is not None:
            body["intent"]["slots"]["query"] = {"name": "query", "value": query, "confirmationStatus": "NONE"}
    return {
        "version": "1.0",
        "session": {"new": False, "sessionId": "session-123", "application": {"applicationId": "amzn1.ask.skill.test"}, "attributes": attributes or {}, "user": {"userId": "user-123"}},
        "context": {"System": {"application": {"applicationId": "amzn1.ask.skill.test"}, "user": {"userId": "user-123"}, "device": {"deviceId": "device-123", "supportedInterfaces": {}}, "apiEndpoint": "https://api.amazonalexa.com"}},
        "request": body,
    }


class FakeService:
    def __init__(self, answers=None, error=None):
        self.answers = iter(answers or [])
        self.error = error
        self.calls = []

    def ask(self, question, previous_response_id=None):
        self.calls.append((question, previous_response_id))
        if self.error:
            raise self.error
        return next(self.answers)


def speech(result):
    output_speech = result["response"]["outputSpeech"]
    return output_speech.get("text") or output_speech["ssml"]


def test_launch_keeps_session_open():
    result = lambda_handler(request("LaunchRequest"), None)
    assert "Pode falar." in speech(result)
    assert result["response"]["shouldEndSession"] is False
    assert "Pode falar." in result["response"]["reprompt"]["outputSpeech"]["ssml"]


def test_three_turn_conversation_preserves_response_id(monkeypatch):
    fake = FakeService([
        AIAnswer("Albert Einstein foi um físico.", "ABC"),
        AIAnswer("Ele nasceu em 1879.", "DEF"),
        AIAnswer("Ele nasceu na Alemanha.", "GHI"),
    ])
    monkeypatch.setattr(alexa_handlers, "get_openai_service", lambda: fake)
    first = lambda_handler(request("IntentRequest", intent_name="AskAIIntent", query="Quem é Albert Einstein?"), None)
    second = lambda_handler(request("IntentRequest", intent_name="AskAIIntent", query="Quando ele nasceu?", attributes=first["sessionAttributes"]), None)
    third = lambda_handler(request("IntentRequest", intent_name="AskAIIntent", query="Em qual país?", attributes=second["sessionAttributes"]), None)
    assert fake.calls == [("Quem é Albert Einstein?", None), ("Quando ele nasceu?", "ABC"), ("Em qual país?", "DEF")]
    assert third["sessionAttributes"]["previous_response_id"] == "GHI"
    assert third["response"]["shouldEndSession"] is False


def test_missing_query_does_not_call_openai(monkeypatch):
    fake = FakeService()
    monkeypatch.setattr(alexa_handlers, "get_openai_service", lambda: fake)
    result = lambda_handler(request("IntentRequest", intent_name="AskAIIntent"), None)
    assert "Não entendi" in speech(result)
    assert fake.calls == []


def test_openai_error_has_friendly_response(monkeypatch):
    monkeypatch.setattr(alexa_handlers, "get_openai_service", lambda: FakeService(error=OpenAIServiceError("rate_limit")))
    result = lambda_handler(request("IntentRequest", intent_name="AskAIIntent", query="teste"), None)
    assert "Tive um problema" in speech(result)
    assert result["response"]["shouldEndSession"] is False


def test_stop_and_cancel_end_the_session():
    for intent_name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
        result = lambda_handler(request("IntentRequest", intent_name=intent_name), None)
        assert result["response"]["shouldEndSession"] is True


def test_session_ended_returns_no_speech():
    result = lambda_handler(request("SessionEndedRequest"), None)
    assert result["response"] == {}
