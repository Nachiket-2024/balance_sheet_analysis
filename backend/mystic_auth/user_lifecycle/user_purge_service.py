from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit_log.audit_log_repository import audit_log_repository
from ..audit_log.audit_log_service import ACCOUNT_PURGED, log_security_event
from ..auth.refresh_token_logic.refresh_token_service import refresh_token_service
from ..authorization.caching.authorization_cache_service import authorization_cache_service
from ..authorization.repositories.authorization_audit_log_repository import authorization_audit_log_repository
from ..logging.logging_config import get_logger
from ..user.user_crud_collector import user_crud
from .account_lifecycle_events import build_account_lifecycle_event

logger = get_logger(__name__)


class AccountNoLongerEligibleForPurgeError(Exception):
    """Raised when the account was soft-deleted at the time this purge was
    decided but is no longer soft-deleted by the time it actually runs
    (reactivated in between), or no longer exists at all. Does NOT apply to
    an admin purging a still-active account directly: that is a legitimate
    call shape with no deleted_at precondition to regress on. Both callers
    must handle this themselves, the same way they already handle
    TokenVersionUnavailableError."""

    def __init__(self, user_email: str):
        self.user_email = user_email
        super().__init__(f"{user_email} is no longer eligible for purge (reactivated or already purged)")


async def purge_user_account(
    user,
    db: AsyncSession,
    *,
    purged_by: str,
    request: Request | None = None,
) -> int:
    """
    Hard-delete path shared by the admin `DELETE /users/{email}/purge` route
    (user_lifecycle_routes.py::purge_user) and the scheduled grace-period
    purge job (procrastinate_tasks/account_purge_tasks.py), so both go
    through the same revoke -> anonymize-history -> audit -> delete
    sequence instead of two independently-maintained copies.

    Takes a row lock on the user and, if it was already soft-deleted when
    this call was made, re-checks that it still is before doing anything
    irreversible: `user` may have been read well before this call (the
    nightly job reads its whole batch up front, then loops), and without
    this re-check a reactivation landing in that gap would still get
    permanently purged on the stale snapshot. The lock also closes the
    window against a reactivation racing in concurrently with this call
    itself, not just one that happened earlier. An admin purging a
    still-active account directly (never soft-deleted) is unaffected: there
    is no deleted_at precondition to regress on in that case. Raises
    AccountNoLongerEligibleForPurgeError if the row no longer exists, or if
    it was soft-deleted at call time but no longer is; both callers must
    handle this themselves.

    Sessions are revoked and the action audit-logged before the row is
    deleted: the audit write is what makes the action reviewable afterward,
    and `user_id`'s ON DELETE CASCADE would otherwise remove Manage Sessions
    rows out from under a post-delete revoke call.

    Raises TokenVersionUnavailableError, uncaught, if the account-version
    bump can't be confirmed (Postgres unavailable). Unlike a reversible soft
    delete, this fails closed on purpose since the row deletion hasn't
    happened yet at that point; better to block an irreversible purge on an
    unconfirmed revoke than delete an account while its sessions might still
    be alive. Both callers must handle this themselves.
    """
    user_email = user.email
    was_soft_deleted = user.deleted_at is not None

    locked_user = await user_crud.lock_by_id(user.id, db)
    if locked_user is None or (was_soft_deleted and locked_user.deleted_at is None):
        raise AccountNoLongerEligibleForPurgeError(user_email)
    user = locked_user

    revoked_count = await refresh_token_service.revoke_all_tokens_for_user(user_email, db)

    # Strips this account's email/IP/user-agent from its OWN PAST historical
    # audit rows - without this, "deleted" only ever meant the primary row,
    # while every login/logout/PBAC decision that account ever made kept a
    # plaintext, directly queryable email and IP forever (no FK, append-only,
    # no retention job - see audit_log_repository.anonymize_for_user's
    # docstring). Deliberately run BEFORE the ACCOUNT_PURGED entry below is
    # written, not after: anonymize_for_user matches every row with this
    # user_email, so running it after would immediately null out the very
    # row that's supposed to make this purge reviewable, defeating the
    # "audit write makes the action reviewable afterward" reasoning above.
    # Running it first means only the pre-existing history is swept; the
    # ACCOUNT_PURGED row created next doesn't exist yet and survives intact.
    # Best-effort in spirit (never raises) but not wrapped in try/except: an
    # unexpected DB error here should surface the same way any other
    # unexpected error in this function would, rather than silently leaving
    # PII behind with no signal that the anonymization step was skipped.
    anonymized_security_rows = await audit_log_repository.anonymize_for_user(user_email, db)
    anonymized_authz_rows = await authorization_audit_log_repository.anonymize_for_user(user_email, db)
    logger.info(
        "Purge: anonymized %s security_audit_log row(s) and %s authorization_audit_log row(s) for %s",
        anonymized_security_rows, anonymized_authz_rows, user_email,
    )

    await log_security_event(
        ACCOUNT_PURGED,
        db,
        user_email=user_email,
        success=True,
        request=request,
        metadata={"purged_by": purged_by, "sessions_revoked": revoked_count},
    )

    lifecycle_event = build_account_lifecycle_event(
        "purged",
        user,
        actor=purged_by,
        source="scheduled_grace_period_purge" if purged_by == "system:grace_period_purge" else "admin",
    )
    await user_crud.delete(db_obj=user, db=db, lifecycle_event=lifecycle_event)

    # This email can be reused by a new signup. Without this invalidation, a
    # new account with the same email could transiently inherit the purged
    # user's stale cached policies/permissions, since the cache is keyed by
    # email, not user id. Best-effort: a cache miss just re-reads the
    # (now empty) database.
    await authorization_cache_service.invalidate_user_policies(user_email)
    await authorization_cache_service.invalidate_user_permissions(user_email)

    return revoked_count
