import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import (
    ACCOUNT_DELETED,
    ACCOUNT_PURGED,
    ACCOUNT_REACTIVATED,
    USER_ROLE_CHANGED,
    log_security_event,
)
from ...auth.password_logic.password_service import password_service

# Session invalidation on account deletion: the same mechanism logout-all
# uses, reused here so a soft-deleted/purged account's existing refresh tokens
# can't be used to mint a fresh access token even though
# refresh_token_service.refresh_tokens() itself doesn't check the database
# (it's Redis/JWT-claim only by design, see its own docstring).
from ...auth.refresh_token_logic.refresh_token_service import refresh_token_service

# Every real authorization check must build context from the actual request
# the same way, see authorization_dependency.py.
from ...authorization.context.request_context_builder import build_authorization_context
from ...authorization.dependencies.authorization_dependency import require_authorization

# PBAC action vocabulary and policy-based authorization. Replaces the removed
# static role-permission helpers.
from ...authorization.permissions import Permission
from ...authorization.services.authorization_service import authorization_service
from ...database.connection import database
from ...emails.email_normalization import normalize_email
from ...user_crud.user_crud_collector import UserStatus, user_crud

# UserRole is only used for target-account guards such as protecting the
# reserved system account from generic endpoints. It is resource metadata, not
# caller authorization; PBAC policies still decide access.
from ...user_table.user_model import UserRole
from ...user_table.user_schema import UserRead, UserRoleUpdate, UserStatsRead, UserUpdate
from ..get_or_404 import get_or_404
from .user_update_payload import prepare_update_data

# Management routes require broader PBAC permissions than self-service routes.
# The name avoids implying role-based admin access because role is metadata.
# main.py registers this router after self-service routes so /{user_email}
# cannot shadow /users/me or /users/stats.
router = APIRouter(prefix="/users", tags=["Users"])

_RESOURCE_TYPE = "users"


@router.get("/stats", response_model=UserStatsRead)
async def get_user_stats(
    current_user: dict = Depends(require_authorization(Permission.USERS_LIST_ALL.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session),
):
    """Same permission as the list itself (users:list_all): this is purely
    a different view of that same data, not a separate resource. Four
    independent counts, run concurrently rather than one query each awaited
    in turn."""
    total, verified, unverified, inactive = await asyncio.gather(
        user_crud.count(db),
        user_crud.count(db, is_verified=True),
        user_crud.count(db, is_verified=False),
        user_crud.count(db, status="inactive"),
    )
    return UserStatsRead(total=total, verified=verified, unverified=unverified, inactive=inactive)


@router.get("/", response_model=list[UserRead])
async def list_all_users(
    response: Response,
    # Keep the historical "all users" default for API callers. The frontend
    # passes its own explicit limit and offset.
    limit: int = Query(default=1000, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Case-insensitive substring match on name or email"),
    role: UserRole | None = Query(default=None, description="Exact match on role"),
    is_verified: bool | None = Query(default=None, description="Exact match on is_verified"),
    status: UserStatus | None = Query(
        default=None, description="One of: active, inactive, deleted (see UsersPage.tsx's Status badge)"
    ),
    sort_by: str | None = Query(
        default=None,
        description="Column to sort by: name, email, role, is_verified, or created_at. "
        "Any other value (including unset) falls back to id.",
    ),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(require_authorization(Permission.USERS_LIST_ALL.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    # X-Total-Count (not part of the response body, response_model stays
    # list[UserRead]) lets the frontend render numbered pages without a
    # separate round trip: computed from the same filters so the page count
    # always matches what's actually being paged through.
    total = await user_crud.count(db, search=search, role=role, is_verified=is_verified, status=status)
    response.headers["X-Total-Count"] = str(total)
    return await user_crud.get_all(
        db,
        limit=limit,
        offset=offset,
        search=search,
        role=role,
        is_verified=is_verified,
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.put("/{user_email}", response_model=UserRead)
async def update_any_user(
    user_email: str,
    update_data: UserUpdate,
    current_user: dict = Depends(require_authorization(Permission.USERS_UPDATE_ANY.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    user_email = normalize_email(user_email)
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found")

    # UserUpdate allows setting `password`, so without this guard anyone with
    # users:update_any could overwrite the system superuser's password and log
    # in as it.
    if user.role == UserRole.system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System user cannot be modified"
        )

    if (
        update_data.password is not None
        and user.hashed_password is not None
        and await password_service.verify_password(update_data.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    prepared_data = await prepare_update_data(update_data)
    updated_user = await user_crud.update(db_obj=user, update_data=prepared_data, db=db)

    # See update_my_profile's identical comment: an admin-driven password
    # change must revoke the target account's existing sessions too.
    if "hashed_password" in prepared_data:
        await refresh_token_service.revoke_all_tokens_for_user(user_email, db)

    return updated_user


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


@router.patch("/{user_email}/role")
async def update_user_role(
    user_email: str,
    role_data: UserRoleUpdate,
    request: Request,
    current_user: dict = Depends(require_authorization(Permission.USERS_ASSIGN_ROLE.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    user_email = normalize_email(user_email)
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found")

    if user.role == UserRole.system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System user role cannot be changed"
        )

    # Assigning the system role requires the separate, more sensitive
    # users:assign_system_role authorization. This can't be a static
    # per-route dependency like the others since it depends on *which* role is
    # being requested in the body, not just who's calling, so it goes
    # through the same centralized authorization_service the route-level
    # dependency itself uses, never a role check.
    if role_data.role == UserRole.system:
        await authorization_service.require(
            user_email=current_user["email"],
            action=Permission.USERS_ASSIGN_SYSTEM_ROLE.value,
            resource_type=_RESOURCE_TYPE,
            db=db,
            context=build_authorization_context(request),
        )

    old_role = user.role.value if user.role else None
    await user_crud.update_role(db_obj=user, role=role_data.role, db=db)

    await log_security_event(
        USER_ROLE_CHANGED,
        db,
        user_email=user_email,
        success=True,
        request=request,
        metadata={"changed_by": current_user["email"], "old_role": old_role, "new_role": role_data.role.value},
    )

    return {"detail": f"User {user_email} role updated to {role_data.role.value}"}
