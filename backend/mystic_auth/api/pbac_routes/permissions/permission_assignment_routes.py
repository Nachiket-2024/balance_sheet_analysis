from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ....audit_log.audit_log_service import PERMISSION_GRANTED, PERMISSION_REVOKED, log_security_event
from ....auth.current_user.current_user_dependency import get_current_user
from ....authorization.conditions.condition_validator import ConditionValidationError, validate_conditions
from ....authorization.context.request_context_builder import build_authorization_context
from ....authorization.dependencies.permission_route_dependencies import (
    GRANT_DEPENDENCY,
    READ_DEPENDENCY,
    REVOKE_DEPENDENCY,
)
from ....authorization.repositories.user_permission_repository import user_permission_repository
from ....authorization.schemas.permission_schema import (
    PermissionAssignmentRequest,
    UserPermissionRead,
    UserPermissionsRead,
)
from ....authorization.services.authorization_service import authorization_service
from ....core.errors import AppError
from ....database.connection import database
from ....user.user_crud_collector import user_crud
from ....user.user_model import UserRole
from ....user_session.session_events import publish_permissions_changed
from ...get_or_404.get_or_404 import get_or_404

router = APIRouter(prefix="/authorization", tags=["Authorization"])


@router.post("/users/{user_email}/permissions")
async def grant_permission_to_user(
    user_email: str,
    assignment: PermissionAssignmentRequest,
    request: Request,
    current_user: dict = GRANT_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Grants a single action directly to a user, bypassing Policy entirely
    (see authorization/models/user_permission_model.py). Idempotent on
    (action, resource_type): re-granting an already-held action updates its
    conditions in place rather than erroring.

    Same privilege-escalation guard as assign_policy_to_user, and for the
    identical reason: permissions:grant alone (without holding the action
    itself) would let a caller hand out capability they don't have.
    """
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    try:
        validate_conditions(assignment.conditions)
    except ConditionValidationError as exc:
        raise AppError(
            status_code=422, code="INVALID_CONDITIONS", detail=exc.errors
        ) from exc

    # The reserved system account's authorization surface must never be
    # mutated through this generic route, mirroring the same guard on
    # update_user_role/update_user (user_management_update_routes.py).
    if user.role == UserRole.system:
        raise AppError(
            status_code=403,
            code="SYSTEM_USER_CANNOT_BE_MODIFIED",
            detail="System user cannot be modified",
        )

    await authorization_service.assert_authorized_to_grant(
        current_user["email"], [assignment.action], assignment.resource_type, db,
        context=build_authorization_context(request), conditions=assignment.conditions,
    )

    await user_permission_repository.assign_permission_to_user(
        user_id=user.id,
        action=assignment.action,
        resource_type=assignment.resource_type,
        conditions=assignment.conditions,
        db=db,
        assigned_by=current_user["email"],
        user_email=user.email,
    )

    await log_security_event(
        PERMISSION_GRANTED,
        db,
        user_email=user.email,
        success=True,
        request=request,
        metadata={
            "granted_by": current_user["email"],
            "action": assignment.action,
            "resource_type": assignment.resource_type,
        },
    )
    await publish_permissions_changed(user.email)
    return {"detail": f"Permission '{assignment.action}' granted to {user_email}"}


@router.delete("/users/{user_email}/permissions/{action}")
async def revoke_permission_from_user(
    user_email: str,
    action: str,
    resource_type: str,
    request: Request,
    current_user: dict = REVOKE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """404 if the user didn't hold this exact (action, resource_type)
    grant. `resource_type` is a required query param since it's part of
    the grant's identity, same as the unique constraint on UserPermission."""
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    # The reserved system account's authorization surface must never be
    # mutated through this generic route, mirroring the same guard on
    # update_user_role/update_user (user_management_update_routes.py).
    if user.role == UserRole.system:
        raise AppError(
            status_code=403,
            code="SYSTEM_USER_CANNOT_BE_MODIFIED",
            detail="System user cannot be modified",
        )

    await authorization_service.assert_authorized_to_grant(
        current_user["email"], [action], resource_type, db,
        context=build_authorization_context(request),
    )

    removed = await user_permission_repository.remove_permission_from_user(
        user_id=user.id, action=action, resource_type=resource_type, db=db, user_email=user.email
    )
    if not removed:
        raise AppError(
            status_code=404,
            code="PERMISSION_NOT_HELD_BY_USER",
            detail=f"{user_email} does not hold permission '{action}' on '{resource_type}'",
            params={"userEmail": user_email, "action": action, "resourceType": resource_type},
        )

    await log_security_event(
        PERMISSION_REVOKED,
        db,
        user_email=user.email,
        success=True,
        request=request,
        metadata={"revoked_by": current_user["email"], "action": action, "resource_type": resource_type},
    )
    await publish_permissions_changed(user.email)
    return {"detail": f"Permission '{action}' removed from {user_email}"}


# Registered BEFORE /users/{user_email}/permissions below, same ordering
# reason as list_my_policies in policy_assignment_routes.py.
@router.get("/users/me/permissions", response_model=UserPermissionsRead)
async def list_my_permissions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """Self-service: every direct grant currently held by the caller
    (active or not). No permissions:read required, mirrors list_my_policies."""
    grants = await user_permission_repository.get_permissions_for_user(current_user["email"], db)
    return UserPermissionsRead(
        user_email=current_user["email"],
        permissions=[UserPermissionRead.model_validate(g) for g in grants],
    )


@router.get("/users/{user_email}/permissions", response_model=UserPermissionsRead)
async def list_user_permissions(
    user_email: str,
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Every direct grant held by this user (active or not)."""
    await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    grants = await user_permission_repository.get_permissions_for_user(user_email, db)
    return UserPermissionsRead(user_email=user_email, permissions=[UserPermissionRead.model_validate(g) for g in grants])
