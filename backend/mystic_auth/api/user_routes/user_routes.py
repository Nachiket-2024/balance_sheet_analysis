from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import (
    ACCOUNT_DELETED,
    ACCOUNT_PURGED,
    ACCOUNT_REACTIVATED,
    log_security_event,
)

# UserUpdate's `password` field name intentionally does not match any column on
# the User model (only `hashed_password` is a real column); it must be hashed
# and renamed here before reaching user_crud.update, or the submitted password
# is silently discarded (set as an unmapped attribute SQLAlchemy never
# persists) and the account keeps its old/no password.
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

# PBAC: action vocabulary (permissions.py) and the authorization
# dependency/service that decide access via assigned policies. Replaces the
# removed RBAC-era require_permission / role_has_permission (a static role ->
# permission mapping).
from ...authorization.permissions import Permission
from ...authorization.services.authorization_service import authorization_service
from ...database.connection import database
from ...emails.email_normalization import normalize_email
from ...user_crud.user_crud_collector import user_crud

# UserRole is used ONLY for the target-account guards below (e.g. "the system
# account can never be modified via these generic endpoints"). This is
# deliberately not a PBAC authorization decision: it never asks "what
# role/policies does the CALLER have": it protects one specific reserved
# resource from every caller, regardless of what they're authorized to do in
# general. Role may still be used as resource metadata/grouping; it must
# simply never *grant* access, which this doesn't; it only narrows access.
from ...user_table.user_model import UserRole
from ...user_table.user_schema import UserRead, UserRoleUpdate, UserUpdate
from ..route_helpers import get_or_404

router = APIRouter(prefix="/users", tags=["Users"])

_RESOURCE_TYPE = "users"


async def _prepare_update_data(update_data: UserUpdate) -> dict:
    """
    Dumps only explicitly-set fields. If a plaintext `password` was submitted,
    validates its strength (same minimum as signup/password-reset) and
    replaces it with a real Argon2 hash under `hashed_password`.
    """
    data = update_data.model_dump(exclude_unset=True)
    # Only ever consulted by update_my_profile's own current-password check
    # above it in the route handler, never a real column, so it must not
    # reach user_crud.update (which would otherwise set it as a harmless but
    # sloppy unmapped attribute on the ORM object).
    data.pop("current_password", None)
    plain_password = data.pop("password", None)
    if plain_password is not None:
        if not await password_service.validate_password_strength(plain_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password does not meet minimum strength requirements",
            )
        data["hashed_password"] = await password_service.hash_password(plain_password)
    return data


@router.get("/me", response_model=UserRead)
async def get_my_profile(
    current_user: dict = Depends(require_authorization(Permission.USERS_READ_OWN.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    email = current_user["email"]
    user = await get_or_404(user_crud.get_by_email(email, db), "User not found")
    return user


@router.put("/me", response_model=UserRead)
async def update_my_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(require_authorization(Permission.USERS_UPDATE_OWN.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    email = current_user["email"]
    user = await get_or_404(user_crud.get_by_email(email, db), "User not found")

    # A stolen access-token cookie (e.g. via XSS) is otherwise enough to
    # permanently lock the legitimate owner out by just setting a new
    # password: no proof of the old one required. Skipped for an
    # OAuth-only account (hashed_password is None) setting a password for
    # the first time, since there's nothing yet to confirm against.
    if update_data.password is not None and user.hashed_password is not None:
        if not update_data.current_password or not await password_service.verify_password(
            update_data.current_password, user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        # Same check password_reset_service.py already does for the forgot-
        # password flow: a "change" that doesn't change anything shouldn't
        # succeed, and shouldn't revoke every other session for no reason.
        if await password_service.verify_password(update_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from the current password",
            )

    prepared_data = await _prepare_update_data(update_data)
    updated_user = await user_crud.update(db_obj=user, update_data=prepared_data, db=db)

    # A password change rotates the credential, so any existing session
    # (including this device's own refresh token) must not survive it,
    # mirroring password_reset_service.py's identical reasoning: an account
    # may be having its password changed specifically because it's
    # compromised, so an attacker's session shouldn't outlive the change.
    if "hashed_password" in prepared_data:
        await refresh_token_service.revoke_all_tokens_for_user(email)

    return updated_user


@router.get("/", response_model=list[UserRead])
async def list_all_users(
    limit: int = Query(default=1000, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_authorization(Permission.USERS_LIST_ALL.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    return await user_crud.get_all(db, limit=limit, offset=offset)


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

    prepared_data = await _prepare_update_data(update_data)
    updated_user = await user_crud.update(db_obj=user, update_data=prepared_data, db=db)

    # See update_my_profile's identical comment: an admin-driven password
    # change must revoke the target account's existing sessions too.
    if "hashed_password" in prepared_data:
        await refresh_token_service.revoke_all_tokens_for_user(user_email)

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
    # its own.
    revoked_count = await refresh_token_service.revoke_all_tokens_for_user(user_email)

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

    # The row is about to disappear, so sessions must be revoked before deletion.
    revoked_count = await refresh_token_service.revoke_all_tokens_for_user(user_email)

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

    await user_crud.update_role(db_obj=user, role=role_data.role, db=db)
    return {"detail": f"User {user_email} role updated to {role_data.role.value}"}
