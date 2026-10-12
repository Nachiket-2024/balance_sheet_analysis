from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit_log.audit_log_service import ACCOUNT_DELETED_SELF, log_security_event
from ..auth.refresh_token_logic.refresh_token_service import refresh_token_service
from ..auth.token_logic.token_version_store import TokenVersionUnavailableError
from ..logging.logging_config import get_logger
from ..user.user_crud_collector import user_crud
from .account_lifecycle_events import build_account_lifecycle_event

logger = get_logger(__name__)


async def finalize_self_deletion(user, db: AsyncSession, *, request: Request | None = None) -> int:
    """
    Soft-delete + session revocation + audit logging shared by both
    self-service delete entry points: the synchronous password-confirmed
    path (user_self_service_routes.py::delete_my_account, for accounts with
    a password) and the async email-confirmed path for OAuth-only accounts
    (account_deletion_service.py::confirm_deletion, reached via POST
    /users/me/confirm-delete). One shared call site keeps the two from
    drifting apart, same reasoning as purge_user_account being shared
    between the admin purge route and the scheduled grace-period job.

    The soft-delete itself (a Postgres write) always succeeds regardless of
    whether the account-version bump below can be confirmed: the account is
    gone from every route's perspective either way (is_active gates every
    login/query path), so there's no recoverable failure to report back to
    the caller here, unlike password reset/change where a retry is still
    meaningful. If the bump can't be confirmed (Postgres unavailable), that's
    logged at critical (existing sessions may keep minting fresh tokens
    until they naturally expire, since refresh_tokens() checks token versions but does not re-check is_active)
    and recorded honestly in the audit trail
    instead of letting TokenVersionUnavailableError propagate and turn an
    already-successful deletion into a reported error.
    """
    email = user.email
    lifecycle_event = build_account_lifecycle_event("soft_deleted", user, actor=email, source="self_service")
    await user_crud.soft_delete(db_obj=user, db=db, lifecycle_event=lifecycle_event)

    # Same reasoning as delete_any_user/purge_user_account: is_active=False
    # alone doesn't stop an already-issued refresh token from minting fresh
    # access tokens until it expires, since refresh_tokens() checks versions but never re-checks is_active.
    try:
        revoked_count = await refresh_token_service.revoke_all_tokens_for_user(email, db)
        sessions_revoked_confirmed = True
    except TokenVersionUnavailableError:
        revoked_count = 0
        sessions_revoked_confirmed = False
        logger.critical(
            "Account %s was deleted, but session revocation could not be confirmed "
            "(Valkey unavailable): existing sessions may remain valid until Valkey recovers",
            email,
        )

    await log_security_event(
        ACCOUNT_DELETED_SELF,
        db,
        user_email=email,
        success=True,
        request=request,
        metadata={
            "deleted_by": email,
            "self_initiated": True,
            "sessions_revoked": revoked_count,
            "sessions_revoked_confirmed": sessions_revoked_confirmed,
        },
    )
    return revoked_count
