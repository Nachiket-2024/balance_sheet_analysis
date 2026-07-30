import logging
import os
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


LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
ACCESS_LOG_PATH = os.path.join(LOG_DIR, 'access.log')


def _make_stream_formatter(json_fields: str, console_fields: str) -> logging.Formatter:
    """
    Human-readable console output in dev, structured JSON in production.
    For the terminal (StreamHandler) only; file output (access_handler
    below) stays JSON unconditionally regardless of environment.

    In dev, a person watches this terminal live (e.g. ./scripts/dev-up.sh),
    so JSON there only costs readability. In production, nobody watches the
    terminal directly; logs ship to a real aggregator (Loki/ELK/CloudWatch/
    etc.) that needs actual structured fields, not text to regex-guess
    apart. Standard practice (structlog's own default: ConsoleRenderer for
    dev, JSONRenderer for prod), not a new idea.

    Keyed off `settings.ENVIRONMENT`, the same flag `main.py` already uses
    for the identical split (whether `/docs` is exposed). `json_fields` and
    `console_fields` are separate strings, not one shared one, because
    JsonFormatter's format string only names which fields to include as
    JSON keys, so it doesn't reliably support plain-text alignment
    directives like `%(levelname)-8s`.
    """
    if settings.ENVIRONMENT.lower() == "production":
        return jsonlogger.JsonFormatter(json_fields)
    return logging.Formatter(console_fields)


def get_logger(name: str = "base_logger") -> logging.Logger:
    """
    Returns a logger configured with:
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

        access_handler = TimedRotatingFileHandler(
            ACCESS_LOG_PATH,
            when="midnight",
            interval=1,
            # backupCount=0 previously meant "never delete a rotated file",
            # not "keep no backups" (TimedRotatingFileHandler's own
            # semantics: 0 disables pruning entirely), so access.log.* grew
            # unbounded on a long-running deployment. 30 days is a
            # reasonable default retention window for access logs.
            backupCount=30
        )
        access_handler.setLevel(logging.INFO)
        access_handler.setFormatter(file_formatter)
        access_handler.addFilter(request_id_filter)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.WARNING)
        stream_handler.setFormatter(stream_formatter)
        stream_handler.addFilter(request_id_filter)

        logger.addHandler(access_handler)
        logger.addHandler(stream_handler)

    # Uvicorn access logs in terminal, but hide healthcheck spam
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.INFO)
    uvicorn_access_logger.addFilter(HealthCheckFilter())
    uvicorn_access_logger.propagate = True

    return logger


def get_worker_logger(name: str = "worker") -> logging.Logger:
    """
    Like get_logger(), but INFO is terminal-visible instead of file-only.

    get_logger() deliberately hides INFO from the terminal to keep it free
    of per-request noise (see its docstring). Background jobs (e.g. the
    Taskiq email task) are the opposite case: there's no HTTP access log
    entry marking when they start/finish, and an operator watching
    `docker compose logs` wants to see "task started" / "task done" lines
    live, the same way Taskiq's own receiver logs already appear. So this
    logger promotes INFO to the terminal while still writing to the same
    JSON access log file as get_logger() for later analysis.
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

        access_handler = TimedRotatingFileHandler(
            ACCESS_LOG_PATH,
            when="midnight",
            interval=1,
            backupCount=30
        )
        access_handler.setLevel(logging.INFO)
        access_handler.setFormatter(file_formatter)
        access_handler.addFilter(request_id_filter)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(stream_formatter)
        stream_handler.addFilter(request_id_filter)

        logger.addHandler(access_handler)
        logger.addHandler(stream_handler)

    return logger


def get_startup_logger(name: str = "startup") -> logging.Logger:
    """
    Returns a logger for one-time, boot-relevant facts (e.g. whether an
    optional subsystem like error monitoring is enabled) that should be
    visible in `docker compose logs`/the terminal immediately, unlike
    get_logger()'s INFO level, which is deliberately file-only there to
    keep the terminal free of routine per-request noise (see its own
    docstring). Fires once per process start (or once per reload in dev
    with `--reload`, same as uvicorn's own startup lines), never per
    request, so promoting it to the terminal doesn't reintroduce that noise.

    Use sparingly: a handful of startup facts an operator would want to
    see without opening a log file, not a general substitute for
    get_logger(). Human-readable in dev, structured JSON in production,
    see _make_stream_formatter's docstring for why. Log aggregation
    tooling in production parses this identically to every other stream
    log either way.
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