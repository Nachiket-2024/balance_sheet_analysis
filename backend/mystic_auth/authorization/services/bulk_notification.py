import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import log_security_event
from ...authorization.schemas.bulk_schema import BulkItemResult
from ...user_session.session_events import publish_permissions_changed


async def log_and_notify_bulk_success(
    repo_results: list[BulkItemResult],
    event_type: str,
    db: AsyncSession,
    *,
    actor_email: str,
    actor_field: str,
    identifier_field: str,
    notify_permissions_changed: bool = True,
) -> None:
    """
    Shared tail of every bulk PBAC route: audit-log every item outcome,
    then nudge affected users' open tabs for successful changes.

    Audit logging is one call per item (each is its own event). The
    permissions-changed notification is deduped to once per user instead,
    since it's just a "something changed, go check" signal, not an event
    record, so a batch touching the same user twice doesn't double-send.
    """
    notified_emails: set[str] = set()
    for result in repo_results:
        if result.status == "success":
            await log_security_event(
                event_type,
                db,
                user_email=result.user_email,
                success=True,
                metadata={
                    actor_field: actor_email,
                    identifier_field: result.identifier,
                    "bulk": True,
                    "result_status": result.status,
                },
            )
        if notify_permissions_changed and result.status == "success":
            notified_emails.add(result.user_email)

    if notified_emails:
        await asyncio.gather(*(publish_permissions_changed(email) for email in notified_emails))
