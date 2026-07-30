from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from starlette.types import ASGIApp

from .logging_config import get_logger

logger = get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logs HTTP requests and responses, including streaming responses."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request, call_next):
        logger.info(f"Incoming request: {request.method} {request.url}")

        # Exceptions are intentionally NOT caught here; they're left to
        # propagate to the single global exception handler in main.py, which
        # logs the full traceback and returns the 500 response. Catching them
        # here too previously meant this middleware's own plain
        # (non-traceback) error log usually fired instead of the global
        # handler's, silently discarding stack traces.
        response = await call_next(request)

        if not isinstance(response, StreamingResponse):
            logger.info(
                f"Response: {response.status_code} for {request.method} {request.url}"
            )

        if isinstance(response, StreamingResponse):
            async def streaming_body():
                async for chunk in response.body_iterator:
                    yield chunk

            response = StreamingResponse(
                streaming_body(),
                status_code=response.status_code,
                headers=response.headers
            )
            logger.info(f"Streaming response with status code: {response.status_code}")

        return response
