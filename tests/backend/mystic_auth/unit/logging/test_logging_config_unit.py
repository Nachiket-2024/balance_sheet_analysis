# tests/backend/mystic_auth/unit/test_logging_config_unit.py
#
# Regression guard: the access-log TimedRotatingFileHandler was previously
# constructed with backupCount=0, which is TimedRotatingFileHandler's own
# signal to never prune rotated files (not "keep zero backups"), so
# access.log.* grew without bound on a long-running deployment.
import logging
from logging.handlers import TimedRotatingFileHandler

from pythonjsonlogger import json as jsonlogger

from backend.mystic_auth.logging.logging_config import (
    PiiRedactionFilter,
    _make_access_handler,
    disable_uvicorn_access_logger,
    get_logger,
    get_startup_logger,
    get_worker_logger,
)

MODULE = "backend.mystic_auth.logging.logging_config"


def test_pii_filter_redacts_email_addresses_with_a_stable_keyed_fingerprint():
    filter_ = PiiRedactionFilter()
    first = logging.LogRecord("test", logging.INFO, __file__, 1, "login for %s", ("User@Example.com",), None)
    second = logging.LogRecord("test", logging.INFO, __file__, 1, "login for %s", ("user@example.com",), None)

    assert filter_.filter(first) is True
    assert filter_.filter(second) is True
    assert "User@Example.com" not in first.getMessage()
    assert first.getMessage() == second.getMessage()
    assert "<email:" in first.getMessage()


def test_pii_filter_leaves_messages_without_email_addresses_unchanged():
    filter_ = PiiRedactionFilter()
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "refresh completed", (), None)

    assert filter_.filter(record) is True
    assert record.getMessage() == "refresh completed"


def test_regular_logger_handlers_have_pii_redaction_filters():
    logger = get_logger("test_logging_config_pii_filters")

    assert all(any(isinstance(filter_, PiiRedactionFilter) for filter_ in handler.filters) for handler in logger.handlers)


def test_access_log_handler_falls_back_when_log_path_is_not_writable(mocker):
    mocker.patch(f"{MODULE}.TimedRotatingFileHandler", side_effect=PermissionError("read-only mount"))

    handler = _make_access_handler(logging.INFO, logging.Formatter("%(message)s"))

    assert isinstance(handler, logging.NullHandler)
    assert handler.level == logging.INFO


def test_access_log_handler_has_a_bounded_retention_window():
    logger = get_logger("test_logging_config_retention")

    rotating_handlers = [h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)]
    if rotating_handlers:
        assert rotating_handlers[0].backupCount > 0
    else:
        assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)


def test_get_logger_routine_info_only_reaches_the_file_handler_not_the_terminal():
    # The whole point of the split: routine per-request INFO logging must
    # stay out of the terminal (see get_logger()'s own docstring). Only
    # WARNING and up should reach its StreamHandler.
    logger = get_logger("test_logging_config_stream_level")

    stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    assert stream_handlers, "expected a StreamHandler on the regular logger"
    assert stream_handlers[0].level == logging.WARNING


def test_get_startup_logger_info_reaches_the_terminal():
    # Regression guard: a one-time, boot-relevant fact (e.g. whether
    # optional error monitoring is enabled) must be visible in `docker
    # compose logs` at INFO, unlike get_logger()'s routine INFO, which is
    # deliberately file-only.
    logger = get_startup_logger("test_logging_config_startup_stream_level")

    stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    assert stream_handlers, "expected a StreamHandler on the startup logger"
    assert stream_handlers[0].level == logging.INFO


def test_get_startup_logger_has_no_file_handler():
    # Startup facts are few and meant to be seen immediately. They don't
    # need (and shouldn't get) the same rotating file sink as routine
    # per-request access logs.
    logger = get_startup_logger("test_logging_config_startup_no_file")

    rotating_handlers = [h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)]
    assert not rotating_handlers


def test_get_startup_logger_uses_a_plain_console_formatter_in_dev(mocker):
    # A human watches this terminal live in dev (e.g. ./scripts/dev-up.sh),
    # so JSON there only costs readability: nobody's querying their own
    # local terminal. See _make_stream_formatter's docstring.
    mocker.patch(f"{MODULE}.settings.ENVIRONMENT", "development")

    logger = get_startup_logger("test_logging_config_startup_dev_formatter")

    stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    formatter = stream_handlers[0].formatter
    assert type(formatter) is logging.Formatter
    assert not isinstance(formatter, jsonlogger.JsonFormatter)


def test_get_startup_logger_uses_json_in_production(mocker):
    # Nobody watches a production terminal directly. Logs get shipped to a
    # real aggregator, which needs actual structured fields to filter/
    # search/alert on, not a string to regex apart.
    mocker.patch(f"{MODULE}.settings.ENVIRONMENT", "production")

    logger = get_startup_logger("test_logging_config_startup_prod_formatter")

    stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    assert isinstance(stream_handlers[0].formatter, jsonlogger.JsonFormatter)


def test_get_startup_logger_environment_check_is_case_insensitive(mocker):
    mocker.patch(f"{MODULE}.settings.ENVIRONMENT", "Production")

    logger = get_startup_logger("test_logging_config_startup_case_insensitive")

    stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    assert isinstance(stream_handlers[0].formatter, jsonlogger.JsonFormatter)


def test_get_logger_stream_handler_uses_a_plain_console_formatter_in_dev(mocker):
    mocker.patch(f"{MODULE}.settings.ENVIRONMENT", "development")

    logger = get_logger("test_logging_config_stream_dev_formatter")

    stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    formatter = stream_handlers[0].formatter
    assert type(formatter) is logging.Formatter
    assert not isinstance(formatter, jsonlogger.JsonFormatter)


def test_get_logger_stream_handler_uses_json_in_production(mocker):
    mocker.patch(f"{MODULE}.settings.ENVIRONMENT", "production")

    logger = get_logger("test_logging_config_stream_prod_formatter")

    stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    assert isinstance(stream_handlers[0].formatter, jsonlogger.JsonFormatter)


def test_get_worker_logger_info_reaches_the_terminal():
    # Regression guard: background job lifecycle events (e.g. send_email_task
    # starting/finishing) must be visible in `docker compose logs` at INFO,
    # since there's no HTTP access log line marking when they happen, unlike
    # get_logger()'s routine INFO, which is deliberately file-only.
    logger = get_worker_logger("test_logging_config_worker_stream_level")

    stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    assert stream_handlers, "expected a StreamHandler on the worker logger"
    assert stream_handlers[0].level == logging.INFO


def test_get_worker_logger_also_writes_to_the_file_handler():
    # Unlike get_startup_logger() (terminal-only, few one-time facts), worker
    # logs are per-task volume and should still land in access.log for later
    # analysis, same as get_logger().
    logger = get_worker_logger("test_logging_config_worker_has_file")

    rotating_handlers = [h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)]
    if rotating_handlers:
        assert rotating_handlers[0].backupCount > 0
    else:
        assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)


def test_get_logger_file_handler_stays_json_even_in_dev(mocker):
    # Regression guard: the dev-vs-prod split is for the terminal only.
    # File output (access.log, later analysis/shipping/tailing-with-jq) must
    # stay structured JSON in every environment, never plain console text.
    mocker.patch(f"{MODULE}.settings.ENVIRONMENT", "development")

    logger = get_logger("test_logging_config_file_stays_json_in_dev")

    rotating_handlers = [h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)]
    if rotating_handlers:
        assert isinstance(rotating_handlers[0].formatter, jsonlogger.JsonFormatter)
    else:
        assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)


def test_uvicorn_access_logger_is_disabled_to_avoid_raw_query_logging():
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.disabled = False
    uvicorn_access_logger.propagate = True
    uvicorn_access_logger.addFilter(logging.Filter())
    uvicorn_access_logger.addHandler(logging.NullHandler())

    disable_uvicorn_access_logger()

    assert uvicorn_access_logger.disabled is True
    assert uvicorn_access_logger.propagate is False
    assert not uvicorn_access_logger.handlers
    assert not uvicorn_access_logger.filters
