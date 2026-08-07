from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import USER_ROLE_CHANGED, log_security_event
from ...auth.password_logic.password_service import password_service

# Session invalidation on account deletion: the same mechanism logout-all
# uses, reused here so a soft-deleted/purged account's existing refresh tokens
# can't be used to mint a fresh access token even though
# refresh_token_service.refresh_tokens() itself doesn't check the database
# (it's Redis/JWT-only by design, see its own docstring).
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
from ...user_crud.user_crud_collector import user_crud
from ...user_crud.user_crud_modules.user_update_payload_preparation import prepare_update_data

# UserRole is only used for target-account guards such as protecting the
# reserved system account from generic endpoints. It is resource metadata, not
# caller authorization; PBAC policies still decide access.
from ...user_table.user_model import UserRole
from ...user_table.user_schema import UserRead, UserRoleUpdate, UserUpdate
from ..get_or_404.get_or_404 import get_or_404

# Management field updates on another user's account. Split out of the
# former user_management_routes.py alongside user_management_query_routes.py
# (read-only views) and user_lifecycle_routes.py (account state transitions),
# mirroring api/pbac_routes/'s existing split-by-operation-type precedent.
# main.py registers this router after self-service routes so /{user_email}
# cannot shadow /users/me or /users/stats.
router = APIRouter(prefix="/users", tags=["Users"])

_RESOURCE_TYPE = "users"


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
