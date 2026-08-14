from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import POLICY_ASSIGNED, POLICY_REVOKED, log_security_event

# Authentication-only dependency (no permission required) : used by
# /users/me/policies, where a user inspects their own assignments regardless
# of whether they hold policies:read.
from ...auth.current_user.current_user_dependency import get_current_user
from ...authorization.dependencies.policy_route_dependencies import (
    ASSIGN_DEPENDENCY,
    READ_DEPENDENCY,
    REVOKE_DEPENDENCY,
)
from ...authorization.policies.default_policies import SYSTEM_SUPERUSER_POLICY_NAME
from ...authorization.repositories.policy_repository import policy_repository
from ...authorization.schemas.policy_schema import PolicyAssignmentRequest, PolicyRead, UserPoliciesRead
from ...authorization.services.authorization_service import authorization_service
from ...core.errors import AppError
from ...database.connection import database
from ...user_crud.user_crud_collector import user_crud
from ..get_or_404.get_or_404 import get_or_404

router = APIRouter(prefix="/authorization", tags=["Authorization"])


@router.post("/users/{user_email}/policies")
async def assign_policy_to_user(
    user_email: str,
    assignment: PolicyAssignmentRequest,
    request: Request,
    current_user: dict = ASSIGN_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Assigns a policy to a user (idempotent : already holding it is a
    no-op). The caller must already hold every action this policy grants :
    otherwise policies:assign alone (without system_superuser itself) would
    let a caller hand out (to themselves or anyone else) a pre-existing
    policy more powerful than what they hold. policies:assign is the one
    action that can escalate access without policies:create/update at all,
    so this guard is what actually enforces that policy assignments cannot
    exceed the caller's own permissions.

    This is the actual mechanism by which an account gains capability under
    PBAC : never a role change. Role may be used for display/grouping, but
    must never select policies automatically.
    """
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")
    policy = await get_or_404(policy_repository.get_by_name(assignment.policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")

    await authorization_service.assert_authorized_to_grant(
        current_user["email"], policy.actions, policy.resource_type, db
    )

    await policy_repository.assign_policy_to_user(
        user_id=user.id, policy_id=policy.id, db=db, assigned_by=current_user["email"],
        user_email=user.email,
    )

    # This is the actual mechanism by which an account gains capability
    # (see this function's own docstring) - including, potentially,
    # system_superuser itself - so an unrecorded grant here is a real gap
    # in the security audit trail, not just a nice-to-have. user_email is
    # the RECEIVING user (consistent with every other audit entry here
    # being keyed on whose account was affected); the granting user is
    # in metadata, mirroring delete_any_user's assigned_by/deleted_by shape.
    await log_security_event(
        POLICY_ASSIGNED,
        db,
        user_email=user.email,
        success=True,
        request=request,
        metadata={"assigned_by": current_user["email"], "policy_name": policy.name},
    )
    return {"detail": f"Policy '{assignment.policy_name}' assigned to {user_email}"}


@router.delete("/users/{user_email}/policies/{policy_name}")
async def remove_policy_from_user(
    user_email: str,
    policy_name: str,
    request: Request,
    current_user: dict = REVOKE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """404 if the user didn't hold this policy (or either identifier
    doesn't resolve)."""
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")
    policy = await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")

    # Lockout protection: removing the last remaining assignment of
    # system_superuser would leave no one able to manage the authorization
    # system at all, not even to reassign it back.
    if policy_name == SYSTEM_SUPERUSER_POLICY_NAME:
        holder_count = await policy_repository.count_assignments(policy.id, db)
        if holder_count <= 1:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="CANNOT_REMOVE_LAST_SUPERUSER_ASSIGNMENT",
                detail="Cannot remove the last remaining assignment of 'system_superuser'",
            )

    removed = await policy_repository.remove_policy_from_user(
        user_id=user.id, policy_id=policy.id, db=db, user_email=user.email
    )
    if not removed:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="POLICY_NOT_HELD_BY_USER",
            detail=f"{user_email} does not hold policy '{policy_name}'",
            params={"userEmail": user_email, "policyName": policy_name},
        )

    await log_security_event(
        POLICY_REVOKED,
        db,
        user_email=user.email,
        success=True,
        request=request,
        metadata={"revoked_by": current_user["email"], "policy_name": policy_name},
    )
    return {"detail": f"Policy '{policy_name}' removed from {user_email}"}


# Registered BEFORE /users/{user_email}/policies below : FastAPI/Starlette
# matches routes in registration order, and a parameterized path segment
# happily matches the literal string "me" too; this specific route must
# come first or /users/{user_email}/policies (which requires policies:read)
# would shadow it.
@router.get("/users/me/policies", response_model=UserPoliciesRead)
async def list_my_policies(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Self-service: every policy currently assigned to the caller (active or
    not : for inspection, not an authorization decision). No policies:read
    required : a user inspecting their own assignments is not privileged
    information, mirroring GET /audit-log/me's own self-service rationale.
    Same response shape as the management GET /users/{email}/policies below,
    scoped to the caller.
    """
    policies = await policy_repository.get_policies_for_user(current_user["email"], db)
    # Explicit ORM -> schema conversion (unlike the response_model=... routes
    # in policy_crud_routes.py, which get this for free from FastAPI's own
    # serialization step) since UserPoliciesRead is constructed directly here.
    return UserPoliciesRead(
        user_email=current_user["email"], policies=[PolicyRead.model_validate(p) for p in policies]
    )


@router.get("/users/{user_email}/policies", response_model=UserPoliciesRead)
async def list_user_policies(
    user_email: str,
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Every policy assigned to this user (active or not : for inspection,
    not an authorization decision)."""
    await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    policies = await policy_repository.get_policies_for_user(user_email, db)
    return UserPoliciesRead(user_email=user_email, policies=[PolicyRead.model_validate(p) for p in policies])
