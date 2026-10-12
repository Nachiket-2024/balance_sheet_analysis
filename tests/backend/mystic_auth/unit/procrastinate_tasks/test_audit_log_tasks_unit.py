# tests/backend/mystic_auth/unit/procrastinate_tasks/test_audit_log_tasks_unit.py
#
# Regression guard for the audit-log write moving off the request path
# (see authorization_audit_logger.py's log_decision): log_authorization_decision_task
# is now the only thing that actually persists an authorization audit row.
# A silent bug here (wrong session usage, swallowing the exception instead
# of re-raising it, wrong entry passed through) would mean authorization
# decisions keep working while their audit trail quietly stops being
# written, exactly the failure mode this suite exists to catch for
# security-sensitive logging.
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from procrastinate.jobs import Job

from backend.mystic_auth.procrastinate_tasks.audit_log_tasks import (
    AUDIT_LOG_RETRY,
    log_authorization_decision_task,
)

MODULE = "backend.mystic_auth.procrastinate_tasks.audit_log_tasks"

ENTRY = {
    "user_email": "user@example.com",
    "action": "users:list_all",
    "resource_type": "users",
    "resource_identifier": None,
    "allowed": True,
    "candidate_policy_names": ["user_management"],
    "granting_policy_names": ["user_management"],
    "failed_conditions": None,
    "context": {"ip_address": "203.0.113.7"},
}


def _job(attempts: int) -> Job:
    return Job(
        queue="default", lock=None, queueing_lock=None,
        task_name="log_authorization_decision_task", attempts=attempts,
    )


def _seconds_until(decision) -> float:
    return (decision.retry_at - datetime.now(UTC)).total_seconds()


def _mock_session(mocker):
    """database.async_session() is an async context manager; this mocks it
    to yield a MagicMock session without touching a real database."""
    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    mocker.patch(f"{MODULE}.database.async_session", return_value=session_cm)
    return session


@pytest.mark.asyncio
async def test_task_writes_the_entry_via_create_entries_on_a_fresh_session(mocker):
    session = _mock_session(mocker)
    create_entries_mock = mocker.patch(
        "backend.mystic_auth.authorization.repositories.authorization_audit_log_repository."
        "authorization_audit_log_repository.create_entries",
        new_callable=AsyncMock,
    )

    await log_authorization_decision_task(entry=ENTRY)

    create_entries_mock.assert_called_once_with([ENTRY], session)


@pytest.mark.asyncio
async def test_task_logs_and_reraises_on_write_failure(mocker):
    _mock_session(mocker)
    mocker.patch(
        "backend.mystic_auth.authorization.repositories.authorization_audit_log_repository."
        "authorization_audit_log_repository.create_entries",
        new_callable=AsyncMock,
        side_effect=RuntimeError("db is down"),
    )
    error_mock = mocker.patch(f"{MODULE}.logger.error")

    with pytest.raises(RuntimeError):
        await log_authorization_decision_task(entry=ENTRY)

    error_mock.assert_called_once()


def test_task_is_configured_with_the_audit_log_retry_strategy():
    assert log_authorization_decision_task.retry_strategy is AUDIT_LOG_RETRY


def test_audit_log_retry_stops_after_max_attempts():
    decision = AUDIT_LOG_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=3))
    assert decision is None


def test_audit_log_retry_allows_up_to_three_attempts_total():
    for attempts in (0, 1, 2):
        decision = AUDIT_LOG_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=attempts))
        assert decision is not None


def test_audit_log_retry_backs_off_exponentially_with_jitter(mocker):
    # jitter=0 isolates the exponential component: min(2 * 2**attempts, 20).
    mocker.patch.object(AUDIT_LOG_RETRY, "jitter", 0)

    for attempts, expected_seconds in ((0, 2), (1, 4), (2, 8)):
        decision = AUDIT_LOG_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=attempts))
        assert _seconds_until(decision) == pytest.approx(expected_seconds, abs=0.5)


def test_audit_log_retry_delay_is_capped_at_max_delay(mocker):
    mocker.patch.object(AUDIT_LOG_RETRY, "jitter", 0)
    mocker.patch.object(AUDIT_LOG_RETRY, "max_attempts", 10)

    decision = AUDIT_LOG_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=9))
    assert _seconds_until(decision) == pytest.approx(20, abs=0.5)


def test_audit_log_retry_is_faster_than_email_retry():
    # A stuck audit write should surface faster than a stuck email retry
    # (see audit_log_tasks.py's module docstring for why): same shape,
    # tighter bounds.
    from backend.mystic_auth.procrastinate_tasks.email_tasks import EMAIL_RETRY

    assert AUDIT_LOG_RETRY.base_delay < EMAIL_RETRY.base_delay
    assert AUDIT_LOG_RETRY.max_delay < EMAIL_RETRY.max_delay
