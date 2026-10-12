import traceback

from ..core.settings import settings
from ..emails.email_sender import email_sender
from ..logging.logging_config import get_worker_logger
from .procrastinate_app import ExponentialBackoffWithJitter, app

logger = get_worker_logger(__name__)

# 3 attempts total, waiting min(5 * 2**attempts, 60) seconds (+ jitter)
# between each. See ExponentialBackoffWithJitter's own docstring.
EMAIL_RETRY = ExponentialBackoffWithJitter(max_attempts=3, base_delay=5, max_delay=60, jitter=3)


# The ignore below is needed because Blueprint.task() only types `retry` as
# the concrete RetryStrategy, not the documented BaseRetryStrategy extension point.
#
# `name=` is pinned since test code imports this task under a different
# root than the real worker, and an unpinned name would register a
# test-deferred job the worker can't resolve ("TaskNotFound").
@app.task(
    name="mystic_auth.procrastinate_tasks.email_tasks.send_email_task",
    retry=EMAIL_RETRY,
)
async def send_email_task(to_email: str, subject: str, body: str, is_html: bool = True) -> bool:
    """Sends an email via the configured EmailSender. Returns True on success.

    Raises on failure (rather than swallowing it) so Procrastinate's retry
    machinery can see it and retry with backoff, up to 3 attempts. A
    permanently-failed job lands as a `procrastinate_jobs` row with
    `status='failed'`, queryable directly, no separate dead-letter needed.
    """
    # EMAIL_ENABLED=false routes this through NullEmailSender (see
    # email_sender.py), which logs its own "not sending" line - but on a
    # different, file-only logger (get_logger, not get_worker_logger), so it
    # never reaches this terminal-visible stream. Without naming the mode
    # here too, this task's own "sent successfully" line looks identical
    # whether a real SMTP connection just opened or nothing happened at all,
    # which is exactly backwards for anyone watching `docker compose logs`
    # to confirm a dry run (local dev, CI, or an audit) really didn't send
    # real mail.
    mode = "dry-run (EMAIL_ENABLED=false)" if not settings.EMAIL_ENABLED else "real SMTP"
    logger.info("Sending email to %s [%s]", to_email, mode)
    try:
        await email_sender.send(to_email, subject, body, is_html)
        logger.info("Email task finished for %s [%s]", to_email, mode)
        return True

    except Exception:
        logger.error("Error sending email to %s (will retry if attempts remain):\n%s", to_email, traceback.format_exc())
        raise
