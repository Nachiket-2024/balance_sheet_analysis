import traceback
from datetime import UTC, datetime, timedelta

from ..core.settings import settings
from ..database.connection import database
from ..logging.logging_config import get_worker_logger
from .procrastinate_app import ExponentialBackoffWithJitter, app

logger = get_worker_logger(__name__)

# 3 attempts total, waiting min(2 * 2**attempts, 20) seconds (+ jitter)
# between each: shorter/faster than EMAIL_RETRY (email_tasks.py) since a
# stuck audit write should surface quickly rather than sit for up to a
# minute, but still enough attempts to ride out a brief Postgres blip.
AUDIT_LOG_RETRY = ExponentialBackoffWithJitter(max_attempts=3, base_delay=2, max_delay=20, jitter=2)


# `name=` is pinned explicitly, same reasoning as email_tasks.py: test code
# imports this task under a different root than the real worker, and an
# unpinned name would register a job the worker can't resolve
# ("TaskNotFound").
@app.task(
    name="mystic_auth.procrastinate_tasks.audit_log_tasks.log_authorization_decision_task",
    retry=AUDIT_LOG_RETRY,
)
async def log_authorization_decision_task(entry: dict) -> None:
    """Persists one authorization-decision audit row (see
    authorization_audit_logger.build_audit_entry for the row shape), off the
    request path: authorization_audit_logger.log_decision defers this
    instead of writing the row itself, so a protected route's response
    doesn't wait on the audit-log commit.

    Runs against `database`'s own SQLAlchemy engine (a fresh session per
    job, opened here), not the request's session, since that session is
    already closed by the time a worker picks this job up. If this
    exhausts all retries, the row lands as a `status='failed'` job in
    `procrastinate_jobs`, inspectable directly via SQL; the authorization
    decision itself was never at risk, only its audit trail entry.
    """
    # Imported here, not at module scope: avoids a circular import between
    # this module and authorization_service.py, which itself defers into
    # this task (procrastinate_app -> audit_log_tasks -> authorization
    # package -> authorization_audit_log_repository, none of which need to import this
    # task module back).
    from ..authorization.repositories.authorization_audit_log_repository import authorization_audit_log_repository

    try:
        async with database.async_session() as session:
            await authorization_audit_log_repository.create_entries([entry], session)
    except Exception:
        logger.error(
            "Error writing authorization audit log entry (will retry if attempts remain):\n%s",
            traceback.format_exc(),
        )
        raise


@app.periodic(cron="30 3 * * *")
@app.task(name="mystic_auth.procrastinate_tasks.audit_log_tasks.anonymize_expired_audit_log_entries")
async def anonymize_expired_audit_log_entries(timestamp: int) -> int:
    """Daily retention backstop for security_audit_log/authorization_audit_log:
    strips email/IP/user-agent from any row older than
    settings.AUDIT_LOG_RETENTION_DAYS, independent of whether the account
    was ever deleted. purge_user_account (user_purge_service.py) already
    anonymizes a purged account's rows immediately; this job is what keeps
    the tables from accumulating PII forever for accounts that are simply
    never deleted, and is also the eventual backstop if a direct DB edit or
    an old account somehow predates that purge-time anonymization. Runs at
    03:30 UTC, offset from purge_expired_soft_deleted_accounts' 03:00 so
    the two daily jobs don't contend for the same connection pool at once.

    `timestamp` is the scheduled cron tick Procrastinate calls this with;
    unused here since the cutoff is computed from the current time, not the
    tick time (same reasoning as purge_expired_soft_deleted_accounts).
    """
    # Imported here, not at module scope: same circular-import avoidance as
    # log_authorization_decision_task above (this module is itself imported
    # by procrastinate_app's task-discovery, which the authorization package
    # transitively imports back through).
    from ..audit_log.audit_log_repository import audit_log_repository
    from ..authorization.repositories.authorization_audit_log_repository import authorization_audit_log_repository

    cutoff = datetime.now(UTC) - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)

    async with database.async_session() as session:
        security_rows = await audit_log_repository.anonymize_older_than(cutoff, session)
        authz_rows = await authorization_audit_log_repository.anonymize_older_than(cutoff, session)

    logger.info(
        "Audit log retention: anonymized %s security_audit_log row(s) and %s authorization_audit_log "
        "row(s) older than %s days",
        security_rows, authz_rows, settings.AUDIT_LOG_RETENTION_DAYS,
    )
    return security_rows + authz_rows
