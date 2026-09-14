from __future__ import annotations

import json
import logging
from typing import Any

from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response

from .openai_service import OpenAIServiceError, get_openai_service

logger = logging.getLogger(__name__)
REPROMPT = "Pode falar."
GENERIC_ERROR = "Tive um problema para responder agora. Tente novamente em alguns segundos."


def _is_request(handler_input: HandlerInput, request_type: str) -> bool:
    return handler_input.request_envelope.request.object_type == request_type


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return _is_request(handler_input, "LaunchRequest")

    def handle(self, handler_input: HandlerInput) -> Response:
        return handler_input.response_builder.speak(REPROMPT).ask(REPROMPT).response


class AskAIIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        request = handler_input.request_envelope.request
        return request.object_type == "IntentRequest" and request.intent.name == "AskAIIntent"

    def handle(self, handler_input: HandlerInput) -> Response:
        intent = handler_input.request_envelope.request.intent
        query = (intent.slots.get("query").value if intent.slots.get("query") else "") or ""
        if not query.strip():
            return handler_input.response_builder.speak("Não entendi a pergunta. Pode falar de novo.").ask(REPROMPT).response
        attributes = handler_input.attributes_manager.session_attributes
        previous_response_id = attributes.get("previous_response_id")
        try:
            answer = get_openai_service().ask(query, previous_response_id)
        except OpenAIServiceError as error:
            _log(handler_input, "AskAIIntent", False, error.kind)
            return handler_input.response_builder.speak(GENERIC_ERROR).ask(REPROMPT).response
        attributes["previous_response_id"] = answer.response_id
        _log(handler_input, "AskAIIntent", True)
        return handler_input.response_builder.speak(answer.text).ask(REPROMPT).response


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        request = handler_input.request_envelope.request
        return request.object_type == "IntentRequest" and request.intent.name == "AMAZON.HelpIntent"

    def handle(self, handler_input: HandlerInput) -> Response:
        return handler_input.response_builder.speak("Você pode fazer uma pergunta. Pode falar.").ask(REPROMPT).response


class StopCancelIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        request = handler_input.request_envelope.request
        return request.object_type == "IntentRequest" and request.intent.name in {"AMAZON.StopIntent", "AMAZON.CancelIntent"}

    def handle(self, handler_input: HandlerInput) -> Response:
        return handler_input.response_builder.speak("Até mais.").set_should_end_session(True).response


class FallbackHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return _is_request(handler_input, "IntentRequest")

    def handle(self, handler_input: HandlerInput) -> Response:
        return handler_input.response_builder.speak("Não entendi. Pode falar de outro jeito.").ask(REPROMPT).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return _is_request(handler_input, "SessionEndedRequest")

    def handle(self, handler_input: HandlerInput) -> Response:
        _log(handler_input, "SessionEndedRequest", True)
        return handler_input.response_builder.response


def _log(handler_input: HandlerInput, intent_name: str, success: bool, error_type: str | None = None) -> None:
    request = handler_input.request_envelope.request
    logger.info(json.dumps({"event": "alexa_request", "request_id": request.request_id,
                             "request_type": request.object_type, "intent_name": intent_name,
                             "success": success, "error_type": error_type}))
