from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import (
    ACCOUNT_DELETED,
    ACCOUNT_PURGED,
    ACCOUNT_REACTIVATED,
    log_security_event,
)

# Session invalidation on account deletion: the same mechanism logout-all
# uses, reused here so a soft-deleted/purged account's existing refresh tokens
# can't be used to mint a fresh access token even though
# refresh_token_service.refresh_tokens() itself doesn't check the database
# (it's Redis/JWT-only by design, see its own docstring).
from ...auth.refresh_token_logic.refresh_token_service import refresh_token_service
from ...authorization.dependencies.authorization_dependency import require_authorization

# PBAC action vocabulary and policy-based authorization. Replaces the removed
# static role-permission helpers.
from ...authorization.permissions import Permission
from ...database.connection import database
from ...emails.email_normalization import normalize_email
from ...user_crud.user_crud_collector import user_crud

# UserRole is only used for target-account guards such as protecting the
# reserved system account from generic endpoints. It is resource metadata, not
# caller authorization; PBAC policies still decide access.
from ...user_table.user_model import UserRole
from ...user_table.user_schema import UserRead
from ..get_or_404.get_or_404 import get_or_404

# Account state transitions (delete/purge/reactivate) on another user's
# account. Split out of the former user_management_routes.py alongside
# user_management_query_routes.py (read-only views) and
# user_management_update_routes.py (field updates), mirroring
# api/pbac_routes/'s existing split-by-operation-type precedent.
# main.py registers this router after self-service routes so /{user_email}
# cannot shadow /users/me or /users/stats.
router = APIRouter(prefix="/users", tags=["Users"])

_RESOURCE_TYPE = "users"


@router.delete("/{user_email}")
async def delete_any_user(
    user_email: str,
    request: Request,
    current_user: dict = Depends(require_authorization(Permission.USERS_DELETE_ANY.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    """
    Soft-delete: is_active=False + deleted_at=now (see user_lifecycle_crud.py).
    The row and every FK-referencing row (policy assignments, audit history)
    stay intact: this is the default, reversible deletion flow. Permanent
    removal is a separate, more sensitive operation (see purge_user below).
    """
    user_email = normalize_email(user_email)
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found")

    if user.role == UserRole.system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System user cannot be deleted"
        )

    # The frontend disables this action against the caller's own row, but
    # that's UI-only: without a server-side check here, anyone holding
    # users:delete_any could soft-delete themselves, revoking their own
    # sessions immediately and, for a sole admin, with no other admin left
    # to reactivate the account.
    if user_email == current_user["email"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete your own account through this endpoint"
        )

    await user_crud.soft_delete(db_obj=user, db=db)

    # is_active=False already blocks login and blocks using an existing access
    # token (current_user_handler.py re-queries the DB on every request), but
    # refresh_token_service.refresh_tokens() itself is Redis/JWT-only and
    # doesn't check the database, so without this a still-valid refresh token
    # could keep minting fresh (if useless) access tokens until it expires on
    # its own. Also marks every Manage Sessions row revoked (see
    # revoke_all_tokens_for_user's own implementation).
    revoked_count = await refresh_token_service.revoke_all_tokens_for_user(user_email, db)

    await log_security_event(
        ACCOUNT_DELETED,
        db,
        user_email=user_email,
        success=True,
        request=request,
        metadata={"deleted_by": current_user["email"], "sessions_revoked": revoked_count},
    )

    return {"detail": f"User {user_email} deleted successfully"}


@router.delete("/{user_email}/purge")
async def purge_user(
    user_email: str,
    request: Request,
    current_user: dict = Depends(require_authorization(Permission.USERS_PURGE.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    """
    Deliberately a separate, more sensitive action from users:delete_any (see
    permissions.py) since this is irreversible and cascades: policy
    assignments are removed via users.id -> policy_model.py's ON DELETE
    CASCADE, while audit log rows reference user_email as a snapshot string
    (not a foreign key), so audit history survives even a purge.
    """
    user_email = normalize_email(user_email)
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found")

    if user.role == UserRole.system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System user cannot be purged"
        )

    # Same reasoning as delete_any_user's self-action guard, and more
    # severe here since a purge is irreversible.
    if user_email == current_user["email"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot purge your own account through this endpoint"
        )

    # The row is about to disappear, so sessions must be revoked before
    # deletion. revoke_all_tokens_for_user also marks every Manage Sessions
    # row revoked, which is redundant work here specifically (users.id's ON
    # DELETE CASCADE removes those rows a moment later anyway, unlike
    # delete_any_user's soft-delete case, where the rows survive) but
    # harmless, and keeping one call site rather than a purge-specific
    # variant is worth that one extra write.
    revoked_count = await refresh_token_service.revoke_all_tokens_for_user(user_email, db)

    # Recorded before the row is deleted, since the event itself is what makes
    # this irreversible action reviewable after the fact.
    await log_security_event(
        ACCOUNT_PURGED,
        db,
        user_email=user_email,
        success=True,
        request=request,
        metadata={"purged_by": current_user["email"], "sessions_revoked": revoked_count},
    )

    await user_crud.delete(db_obj=user, db=db)
    return {"detail": f"User {user_email} permanently removed"}


@router.patch("/{user_email}/reactivate", response_model=UserRead)
async def reactivate_user(
    user_email: str,
    request: Request,
    current_user: dict = Depends(require_authorization(Permission.USERS_REACTIVATE.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    user_email = normalize_email(user_email)
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found")

    # Reactivate is specifically the soft-delete undo path: nothing to
    # restore if the account was never soft-deleted.
    if user.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not deleted"
        )

    # Policy assignments were never touched by soft delete, so access returns
    # exactly as it was, so no re-granting needed.
    restored_user = await user_crud.reactivate(db_obj=user, db=db)

    await log_security_event(
        ACCOUNT_REACTIVATED,
        db,
        user_email=user_email,
        success=True,
        request=request,
        metadata={"reactivated_by": current_user["email"]},
    )

    return restored_user
