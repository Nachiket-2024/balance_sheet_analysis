# tests/backend/mystic_auth/unit/procrastinate_tasks/test_email_tasks_unit.py
#
# Regression guard for email delivery reliability: send_email_task used to
# catch every exception and return False, which no retry mechanism ever
# sees (it only reacts to a raised exception), so a transient SMTP failure
# silently dropped the email. The fix makes the task raise on failure
# (after logging) so Procrastinate's retry_strategy can see it and schedule
# a retry, up to max_attempts, while every attempt still leaves a full
# traceback in the logs.
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from procrastinate.jobs import Job

from backend.mystic_auth.procrastinate_tasks.email_tasks import (
    EMAIL_RETRY,
    send_email_task,
)

MODULE = "backend.mystic_auth.procrastinate_tasks.email_tasks"


def _job(attempts: int) -> Job:
    return Job(queue="default", lock=None, queueing_lock=None, task_name="send_email_task", attempts=attempts)


def _seconds_until(decision) -> float:
    return (decision.retry_at - datetime.now(UTC)).total_seconds()


@pytest.mark.asyncio
async def test_send_email_task_returns_true_on_success(mocker):
    # Tests always force EMAIL_ENABLED=False (see settings.py), so the
    # "real SMTP" label is covered separately below rather than here.
    mocker.patch(f"{MODULE}.email_sender.send", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.settings.EMAIL_ENABLED", True)
    info_mock = mocker.patch(f"{MODULE}.logger.info")

    result = await send_email_task(to_email="user@example.com", subject="Hi", body="Body")

    assert result is True
    info_mock.assert_any_call("Sending email to %s [%s]", "user@example.com", "real SMTP")
    info_mock.assert_any_call("Email task finished for %s [%s]", "user@example.com", "real SMTP")


@pytest.mark.asyncio
async def test_send_email_task_log_names_dry_run_mode_when_email_disabled(mocker):
    # Regression guard: this task's own terminal-visible log previously said "Email sent
    # successfully" regardless of whether EMAIL_ENABLED was true or false -
    # NullEmailSender's "not sending" log lives on a different, file-only
    # logger, so with email disabled the terminal showed a false-positive-
    # looking "sent successfully" line for what was actually a no-op.
    mocker.patch(f"{MODULE}.email_sender.send", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.settings.EMAIL_ENABLED", False)
    info_mock = mocker.patch(f"{MODULE}.logger.info")

    result = await send_email_task(to_email="user@example.com", subject="Hi", body="Body")

    assert result is True
    dry_run_label = "dry-run (EMAIL_ENABLED=false)"
    info_mock.assert_any_call("Sending email to %s [%s]", "user@example.com", dry_run_label)
    info_mock.assert_any_call("Email task finished for %s [%s]", "user@example.com", dry_run_label)


@pytest.mark.asyncio
async def test_send_email_task_logs_and_reraises_on_send_failure(mocker):
    mocker.patch(f"{MODULE}.email_sender.send", new_callable=AsyncMock, side_effect=RuntimeError("SMTP down"))
    error_mock = mocker.patch(f"{MODULE}.logger.error")

    with pytest.raises(RuntimeError):
        await send_email_task(to_email="user@example.com", subject="Hi", body="Body")

    error_mock.assert_called_once()


def test_send_email_task_is_configured_with_the_email_retry_strategy():
    assert send_email_task.retry_strategy is EMAIL_RETRY


def test_email_retry_stops_after_max_attempts():
    decision = EMAIL_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=3))
    assert decision is None


def test_email_retry_allows_up_to_three_attempts_total():
    for attempts in (0, 1, 2):
        decision = EMAIL_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=attempts))
        assert decision is not None


def test_email_retry_backs_off_exponentially_with_jitter(mocker):
    # jitter=0 isolates the exponential component: min(5 * 2**attempts, 60).
    mocker.patch.object(EMAIL_RETRY, "jitter", 0)

    for attempts, expected_seconds in ((0, 5), (1, 10), (2, 20)):
        decision = EMAIL_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=attempts))
        assert _seconds_until(decision) == pytest.approx(expected_seconds, abs=0.5)


def test_email_retry_delay_is_capped_at_max_delay(mocker):
    mocker.patch.object(EMAIL_RETRY, "jitter", 0)
    mocker.patch.object(EMAIL_RETRY, "max_attempts", 10)

    decision = EMAIL_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=9))
    assert _seconds_until(decision) == pytest.approx(60, abs=0.5)


def test_email_retry_jitter_adds_a_bounded_random_offset():
    # Same attempts count queried many times: every jittered delay must land
    # within [base, base + jitter], and shouldn't all be identical (a jitter
    # that never varies wouldn't protect against a thundering herd).
    base = min(EMAIL_RETRY.base_delay * (2**0), EMAIL_RETRY.max_delay)
    seconds = {
        round(_seconds_until(EMAIL_RETRY.get_retry_decision(exception=RuntimeError(), job=_job(attempts=0))), 3)
        for _ in range(20)
    }
    assert all(base - 0.5 <= s <= base + EMAIL_RETRY.jitter + 0.5 for s in seconds)
    assert len(seconds) > 1
