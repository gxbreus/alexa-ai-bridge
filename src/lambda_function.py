import logging
import json
import time

from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_model import Response
from .deadline import RequestDeadlineExceeded, request_deadline

from .alexa_handlers import (AskAIIntentHandler, FallbackHandler, HelpIntentHandler,
                             LaunchRequestHandler, SessionEndedRequestHandler, StopCancelIntentHandler)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception) -> Response:
        logger.exception("Unhandled Alexa request failure", exc_info=exception)
        return handler_input.response_builder.speak(
            "Tive um problema para responder agora. Tente novamente em alguns segundos."
        ).ask("Pode falar.").response


builder = SkillBuilder()
for request_handler in (LaunchRequestHandler(), AskAIIntentHandler(), HelpIntentHandler(),
                        StopCancelIntentHandler(), FallbackHandler(), SessionEndedRequestHandler()):
    builder.add_request_handler(request_handler)
builder.add_exception_handler(CatchAllExceptionHandler())
_sdk_handler = builder.lambda_handler()


def lambda_handler(event, context):
    started = time.perf_counter()
    request = event.get("request", {})
    logger.info(json.dumps({"event": "invocation_start", "request_id": request.get("requestId"),
                            "request_type": request.get("type")}))
    # Alexa precisa de uma resposta rápida, mas a busca web varia mais que uma
    # resposta sem ferramentas. Encerramos antes do limite externo da Alexa.
    budget = 7.2
    if context is not None:
        budget = max(0.01, min(budget, context.get_remaining_time_in_millis() / 1000 - 0.8))
    try:
        with request_deadline(budget):
            return _sdk_handler(event, context)
    except RequestDeadlineExceeded:
        logger.warning(json.dumps({"event": "invocation_deadline", "request_id": request.get("requestId")}))
        return {
            "version": "1.0",
            "sessionAttributes": event.get("session", {}).get("attributes", {}),
            "response": {
                "outputSpeech": {"type": "PlainText", "text": "Tive um problema para responder agora. Tente novamente em alguns segundos."},
                "reprompt": {"outputSpeech": {"type": "PlainText", "text": "Pode falar."}},
                "shouldEndSession": False,
            },
        }
    finally:
        logger.info(json.dumps({"event": "invocation_end", "request_id": request.get("requestId"),
                                "latency_ms": round((time.perf_counter() - started) * 1000)}))
