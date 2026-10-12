import hashlib
import hmac
import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler

from pythonjsonlogger import json as jsonlogger

from ..core.settings import settings
from .correlation_id_middleware import request_id_ctx_var


class RequestIdFilter(logging.Filter):
    """Injects the current request's correlation ID (if any) into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get()
        return True


class HealthCheckFilter(logging.Filter):
    """Hide Docker healthcheck requests from terminal access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/health/ready" not in record.getMessage()


class PiiRedactionFilter(logging.Filter):
    """Remove raw email addresses from every application log sink.

    A stable, keyed fingerprint preserves the ability to correlate events for
    one account without making the email address itself available to anyone
    with log access. Redaction happens at the handler boundary so it also
    covers third-party/library errors and future call sites.
    """

    _EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

    @staticmethod
    def _fingerprint(match: re.Match[str]) -> str:
        normalized = match.group(0).strip().lower().encode("utf-8")
        digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), normalized, hashlib.sha256).hexdigest()[:16]
        return f"<email:{digest}>"

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = self._EMAIL_RE.sub(self._fingerprint, message)
        if redacted != message:
            # Materialize the message so handlers cannot format the original
            # args again after this filter has run.
            record.msg = redacted
            record.args = ()
        return True


def disable_uvicorn_access_logger() -> None:
    """Drop raw Uvicorn access logs because they include query strings."""

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers.clear()
    uvicorn_access_logger.filters.clear()
    uvicorn_access_logger.propagate = False
    uvicorn_access_logger.disabled = True


LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
ACCESS_LOG_PATH = os.path.join(LOG_DIR, 'access.log')


def _make_access_handler(level: int, formatter: logging.Formatter) -> logging.Handler:
    try:
        handler: logging.Handler = TimedRotatingFileHandler(
            ACCESS_LOG_PATH,
            when="midnight",
            interval=1,
            # backupCount=0 means "never delete a rotated file" (disables
            # pruning), not "keep no backups" - that let access.log.* grow
            # unbounded. 30 days is a reasonable retention window.
            backupCount=30
        )
    except OSError:
        # A container may mount the source tree read-only or hand ownership
        # of the log directory to a host logging user. Startup must still
        # succeed; the caller's console handler remains available for
        # warnings/errors, while deployments can fix the mount for full JSON
        # access-log retention.
        handler = logging.NullHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def _make_stream_formatter(json_fields: str, console_fields: str) -> logging.Formatter:
    """Human-readable console output in dev, structured JSON in production.
    Applies to the terminal (StreamHandler) only; file output
    (access_handler below) stays JSON unconditionally.

    In dev a person watches this terminal live, so JSON only costs
    readability. In production nobody watches it directly; logs ship to an
    aggregator (Loki/ELK/CloudWatch) that wants structured fields, not text
    to regex apart.

    Keyed off `settings.ENVIRONMENT`, same as main.py's docs/redoc split.
    `json_fields` and `console_fields` are separate strings because
    JsonFormatter's format string only names JSON keys, not plain-text
    alignment directives like `%(levelname)-8s`.
    """
    if settings.ENVIRONMENT.lower() == "production":
        return jsonlogger.JsonFormatter(json_fields)
    return logging.Formatter(console_fields)


def get_logger(name: str = "base_logger") -> logging.Logger:
    """Returns a logger configured with:
    - JSON formatted rotating file logs (always, see access_handler below)
    - base_logger INFO logs stored in files only
    - warnings/errors visible in Docker terminal (JSON in production,
      human-readable console text in dev, see _make_stream_formatter)
    - Uvicorn access logs visible except health checks
    """

    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL)
    logger.propagate = False

    if not logger.handlers:
        # File output stays JSON unconditionally, in every environment.
        # It's for later analysis/shipping/tailing-with-jq, never for
        # someone watching it live the way the terminal is.
        file_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s'
        )
        stream_formatter = _make_stream_formatter(
            json_fields='%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s',
            console_fields='%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s',
        )

        request_id_filter = RequestIdFilter()
        pii_filter = PiiRedactionFilter()

        access_handler = _make_access_handler(logging.INFO, file_formatter)
        access_handler.addFilter(request_id_filter)
        access_handler.addFilter(pii_filter)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.WARNING)
        stream_handler.setFormatter(stream_formatter)
        stream_handler.addFilter(request_id_filter)
        stream_handler.addFilter(pii_filter)

        logger.addHandler(access_handler)
        logger.addHandler(stream_handler)

    disable_uvicorn_access_logger()

    return logger


def get_worker_logger(name: str = "worker") -> logging.Logger:
    """Like get_logger(), but INFO is terminal-visible instead of file-only.

    get_logger() hides INFO from the terminal to keep it free of
    per-request noise. Background jobs (e.g. Procrastinate tasks) are the
    opposite case: there's no HTTP access log entry marking when they
    start/finish, and an operator watching `docker compose logs` wants to
    see "task started" / "task done" lines live. So this logger promotes
    INFO to the terminal while still writing to the same JSON access log
    file as get_logger() for later analysis.
    """
    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL)
    logger.propagate = False

    if not logger.handlers:
        file_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s'
        )
        stream_formatter = _make_stream_formatter(
            json_fields='%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s',
            console_fields='%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s',
        )

        request_id_filter = RequestIdFilter()
        pii_filter = PiiRedactionFilter()

        access_handler = _make_access_handler(logging.INFO, file_formatter)
        access_handler.addFilter(request_id_filter)
        access_handler.addFilter(pii_filter)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(stream_formatter)
        stream_handler.addFilter(request_id_filter)
        stream_handler.addFilter(pii_filter)

        logger.addHandler(access_handler)
        logger.addHandler(stream_handler)

    return logger


def get_startup_logger(name: str = "startup") -> logging.Logger:
    """Logger for one-time, boot-relevant facts (e.g. whether an optional
    subsystem like error monitoring is enabled) that should be visible in
    `docker compose logs` immediately, unlike get_logger()'s file-only
    INFO level. Fires once per process start (or per `--reload` in dev),
    never per request, so promoting it to the terminal doesn't reintroduce
    per-request noise.

    Use sparingly: a handful of startup facts, not a general substitute
    for get_logger(). Human-readable in dev, structured JSON in
    production, see _make_stream_formatter.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        stream_formatter = _make_stream_formatter(
            json_fields='%(asctime)s %(levelname)s %(name)s %(message)s',
            console_fields='%(asctime)s %(levelname)-8s %(name)s: %(message)s',
        )

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(stream_formatter)

        logger.addHandler(stream_handler)

    return logger
