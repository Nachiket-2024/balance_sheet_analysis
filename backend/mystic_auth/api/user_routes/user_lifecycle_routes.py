from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import (
    ACCOUNT_DELETED,
    ACCOUNT_REACTIVATED,
    log_security_event,
)

# Session invalidation on account deletion: the same mechanism logout-all
# uses, reused here so a soft-deleted/purged account's existing refresh tokens
# can't be used to mint a fresh access token even though
# refresh_token_service.refresh_tokens() itself doesn't check the database
# (it's Valkey/JWT-only by design, see its own docstring).
from ...auth.refresh_token_logic.refresh_token_service import refresh_token_service
from ...auth.token_logic.token_version_store import TokenVersionUnavailableError
from ...authorization.dependencies.authorization_dependency import require_authorization

# PBAC action vocabulary and policy-based authorization. Replaces the removed
# static role-permission helpers.
from ...authorization.permissions import Permission
from ...core.errors import AppError
from ...database.connection import database
from ...emails.email_normalization import normalize_email
from ...logging.logging_config import get_logger
from ...user.user_crud_collector import user_crud
from ...user.user_model import UserRole
from ...user.user_schema import UserRead

# UserRole is only used for target-account guards such as protecting the
# reserved system account from generic endpoints. It is resource metadata, not
# caller authorization; PBAC policies still decide access.
from ...user_lifecycle.account_lifecycle_events import build_account_lifecycle_event
from ...user_lifecycle.user_purge_service import AccountNoLongerEligibleForPurgeError, purge_user_account
from ..get_or_404.get_or_404 import get_or_404

# Account state transitions (delete/purge/reactivate) on another user's
# account, split out from user_management_query_routes.py (read-only views)
# and user_management_update_routes.py (field updates). main.py registers
# this router after self-service routes so /{user_email} cannot shadow
# /users/me or /users/stats.
router = APIRouter(prefix="/users", tags=["Users"])

logger = get_logger(__name__)

_RESOURCE_TYPE = "users"


@router.delete("/{user_email}")
async def delete_any_user(
    user_email: str,
    request: Request,
    current_user: dict = Depends(require_authorization(Permission.USERS_DEACTIVATE_ANY.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    """
    Soft-delete: is_active=False + deleted_at=now (see user_lifecycle_crud.py).
    The row and every FK-referencing row (policy assignments, audit history)
    stay intact: this is the default, reversible deletion flow. Permanent
    removal is a separate, more sensitive operation (see purge_user below).
    """
    user_email = normalize_email(user_email)
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    if user.role == UserRole.system:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SYSTEM_USER_CANNOT_BE_DELETED",
            detail="System user cannot be deleted"
        )

    # The frontend disables this action against the caller's own row, but
    # that's UI-only: without a server-side check here, anyone holding
    # users:deactivate_any could soft-delete themselves, revoking their own
    # sessions immediately and, for a sole admin, with no other admin left
    # to reactivate the account.
    if user_email == current_user["email"]:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CANNOT_DELETE_OWN_ACCOUNT",
            detail="Cannot delete your own account through this endpoint"
        )

    lifecycle_event = build_account_lifecycle_event(
        "soft_deleted", user, actor=current_user["email"], source="admin"
    )
    await user_crud.soft_delete(db_obj=user, db=db, lifecycle_event=lifecycle_event)

    # is_active=False already blocks login, but refresh_tokens() is
    # Valkey/JWT-only and doesn't check the database, so a still-valid
    # refresh token could keep minting access tokens without this.
    #
    # The soft-delete above already succeeded, so a failed revoke here must
    # not turn a successful deletion into an error response: log critical
    # and record it honestly in the audit trail instead.
    try:
        revoked_count = await refresh_token_service.revoke_all_tokens_for_user(user_email, db)
        sessions_revoked_confirmed = True
    except TokenVersionUnavailableError:
        revoked_count = 0
        sessions_revoked_confirmed = False
        logger.critical(
            "User %s was deleted by %s, but session revocation could not be confirmed "
            "(Valkey unavailable) - existing sessions may remain valid until Valkey recovers",
            user_email, current_user["email"],
        )

    await log_security_event(
        ACCOUNT_DELETED,
        db,
        user_email=user_email,
        success=True,
        request=request,
        metadata={
            "deleted_by": current_user["email"],
            "sessions_revoked": revoked_count,
            "sessions_revoked_confirmed": sessions_revoked_confirmed,
        },
    )
    return {"detail": f"User {user_email} deleted successfully"}


@router.delete("/{user_email}/purge")
async def purge_user(
    user_email: str,
    request: Request,
    current_user: dict = Depends(require_authorization(Permission.USERS_DELETE_ANY.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    """
    Deliberately a separate, more sensitive action from users:deactivate_any (see
    permissions.py) since this is irreversible and cascades: policy
    assignments are removed via users.id -> policy_model.py's ON DELETE
    CASCADE. Historical audit rows are anonymized before the purge event is
    written, then survive as non-identifying snapshot history rather than as
    a foreign-key dependency on the deleted user.
    """
    user_email = normalize_email(user_email)
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    if user.role == UserRole.system:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SYSTEM_USER_CANNOT_BE_PURGED",
            detail="System user cannot be purged"
        )

    # Same reasoning as delete_any_user's self-action guard, and more
    # severe here since a purge is irreversible.
    if user_email == current_user["email"]:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CANNOT_PURGE_OWN_ACCOUNT",
            detail="Cannot purge your own account through this endpoint"
        )

    # Shared with the scheduled grace-period purge job so both use the same
    # revoke -> anonymize-history -> audit -> delete sequence.
    #
    # Unlike the reversible soft-delete paths, this revokes BEFORE the
    # irreversible hard delete: a TokenVersionUnavailableError here
    # propagates and the row is never deleted, so an unconfirmed revoke
    # blocks the purge rather than risking a purge with live sessions.
    try:
        await purge_user_account(user, db, purged_by=current_user["email"], request=request)
    except TokenVersionUnavailableError as exc:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SESSION_REVOCATION_UNAVAILABLE",
            detail="Could not confirm existing sessions were revoked; purge was not performed. Please try again shortly",
        ) from exc
    except AccountNoLongerEligibleForPurgeError as exc:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="USER_NOT_DELETED",
            detail="User was reactivated and is no longer eligible for purge",
        ) from exc
    return {"detail": f"User {user_email} permanently removed"}


@router.patch("/{user_email}/reactivate", response_model=UserRead)
async def reactivate_user(
    user_email: str,
    request: Request,
    current_user: dict = Depends(require_authorization(Permission.USERS_REACTIVATE.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    user_email = normalize_email(user_email)
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    # Reactivate is specifically the soft-delete undo path: nothing to
    # restore if the account was never soft-deleted.
    if user.deleted_at is None:
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="USER_NOT_DELETED",
            detail="User is not deleted"
        )

    # Policy assignments were never touched by soft delete, so access returns
    # exactly as it was, so no re-granting needed.
    lifecycle_event = build_account_lifecycle_event(
        "reactivated", user, actor=current_user["email"], source="admin"
    )
    restored_user = await user_crud.reactivate(db_obj=user, db=db, lifecycle_event=lifecycle_event)

    await log_security_event(
        ACCOUNT_REACTIVATED,
        db,
        user_email=user_email,
        success=True,
        request=request,
        metadata={"reactivated_by": current_user["email"]},
    )
    return restored_user
