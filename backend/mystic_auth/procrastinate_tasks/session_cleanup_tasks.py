from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult

from ..core.settings import settings
from ..database.connection import database
from ..logging.logging_config import get_worker_logger
from ..user_session.session_repository import session_repository
from .procrastinate_app import app

logger = get_worker_logger(__name__)


@app.periodic(cron="30 3 * * *")
@app.task
async def purge_expired_sessions(timestamp: int) -> int:
    """Daily sweep of user_sessions rows that lapsed via expires_at without
    ever going through an explicit revoke (revoke_by_id/revoke_by_jti/
    revoke_by_chain_id/revoke_all_for_user/revoke_all_for_user_except_chain
    in session_repository.py already delete their rows immediately, so
    there's nothing left for this job to find in that case - this only
    catches a token that simply timed out with no logout call).

    Runs daily at 03:30 UTC, 30 minutes after
    purge_expired_soft_deleted_accounts so the two batch jobs (same worker
    process, both @app.periodic) don't overlap. `timestamp` is the
    scheduled cron tick Procrastinate calls this with; unused here since the
    cutoff is computed from the current time, not the tick time, same
    reasoning as account_purge_tasks.py.

    Safe to delete unconditionally, no per-row confirmation needed (unlike
    the account purge job's Valkey-confirmed revoke): the durable Postgres token-version records, not this table, are the
    source of truth for actual token validity, so a stale row disappearing
    here can never affect a live login/refresh decision.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=settings.SESSION_ROW_RETENTION_HOURS)

    async with database.async_session() as session:
        deleted_count = await session_repository.delete_expired_unrevoked(session, cutoff)

    logger.info(
        "Session cleanup: removed %s row(s) expired more than %s hour(s) ago",
        deleted_count, settings.SESSION_ROW_RETENTION_HOURS,
    )
    return deleted_count


@app.periodic(cron="35 3 * * *")
@app.task
async def purge_consumed_refresh_tokens(timestamp: int) -> int:
    """Delete expired one-time refresh-token claims in bounded batches.

    The primary-key registry is the durable source of truth for refresh
    rotation. Keeping each claim until its JWT expires makes replay checks
    survive Valkey loss; expired tokens can no longer be presented, so their
    claims are safe to remove.
    """
    del timestamp
    deleted_count = 0
    async with database.async_session() as session:
        while True:
            result = await session.execute(
                text(
                    "WITH expired AS ("
                    "  SELECT jti FROM consumed_refresh_tokens "
                    "  WHERE expires_at < now() ORDER BY expires_at LIMIT 5000"
                    ") DELETE FROM consumed_refresh_tokens AS consumed "
                    "USING expired WHERE consumed.jti = expired.jti"
                )
            )
            batch_count = cast(CursorResult, result).rowcount or 0
            await session.commit()
            deleted_count += batch_count
            if batch_count < 5000:
                break

    logger.info("Refresh token rotation cleanup: removed %s expired claim(s)", deleted_count)
    return deleted_count
