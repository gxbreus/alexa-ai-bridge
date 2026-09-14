import logging

from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_model import Response

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
lambda_handler = builder.lambda_handler()
