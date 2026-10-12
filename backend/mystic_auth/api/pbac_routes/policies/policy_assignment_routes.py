from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....audit_log.audit_log_service import POLICY_ACTION_REVOKED, POLICY_ASSIGNED, POLICY_REVOKED, log_security_event
from ....authorization.context.request_context_builder import build_authorization_context
from ....authorization.dependencies.permission_route_dependencies import (
    GRANT_DEPENDENCY as PERMISSIONS_GRANT_DEPENDENCY,
)
from ....authorization.dependencies.policy_route_dependencies import (
    ASSIGN_DEPENDENCY,
    READ_DEPENDENCY,
    REVOKE_DEPENDENCY,
)
from ....authorization.policies.default_policies import SYSTEM_SUPERUSER_POLICY_NAME
from ....authorization.repositories.policy_repository import policy_repository
from ....authorization.schemas.policy_schema import (
    PolicyActionRevocationRequest,
    PolicyAssignmentRequest,
    PolicyHolderRead,
    PolicyRead,
    UserPoliciesRead,
)
from ....authorization.services.authorization_service import authorization_service
from ....authorization.services.policy_action_revocation_service import (
    ActionNotInPolicyError,
    policy_action_revocation_service,
)
from ....core.errors import AppError
from ....database.connection import database
from ....user.user_crud_collector import user_crud
from ....user.user_model import UserRole
from ....user_session.session_events import publish_permissions_changed
from ...get_or_404.get_or_404 import get_or_404
from .policy_self_routes import list_my_policies

router = APIRouter(prefix="/authorization", tags=["Authorization"])

# Backward-compatible import path for focused unit tests and integrations.
__all__ = ["list_my_policies", "router"]


@router.get("/policies/{policy_name}/holders", response_model=list[PolicyHolderRead])
async def list_policy_holders(
    policy_name: str,
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Every user currently assigned this policy, newest assignment first.
    Backs both the details dialog's "Assigned users" list and the delete
    confirm's "N users will lose access" count (the frontend just takes
    len() of this same list, no separate count endpoint)."""
    policy = await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")
    return await policy_repository.get_holders(policy.id, db)


@router.post("/users/{user_email}/policies")
async def assign_policy_to_user(
    user_email: str,
    assignment: PolicyAssignmentRequest,
    request: Request,
    current_user: dict = ASSIGN_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Assigns a policy to a user (idempotent: already holding it is a no-op).
    The caller must already hold every action this policy grants, otherwise
    policies:assign alone (without system_superuser itself) would let a
    caller hand out a pre-existing policy more powerful than what they
    hold. policies:assign is the one action that can escalate access
    without policies:create/update at all, so this guard is what enforces
    that policy assignments can't exceed the caller's own permissions.

    This is the actual mechanism by which an account gains capability under
    PBAC, never a role change. Role may be used for display/grouping, but
    must never select policies automatically.
    """
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")
    policy = await get_or_404(policy_repository.get_by_name(assignment.policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")

    # The reserved system account's authorization surface must never be
    # mutated through this generic route, mirroring the same guard on
    # update_user_role/update_user (user_management_update_routes.py).
    if user.role == UserRole.system:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SYSTEM_USER_CANNOT_BE_MODIFIED",
            detail="System user cannot be modified",
        )

    await authorization_service.assert_authorized_to_grant(
        current_user["email"], policy.actions, policy.resource_type, db,
        context=build_authorization_context(request), conditions=policy.conditions,
    )

    await policy_repository.assign_policy_to_user(
        user_id=user.id, policy_id=policy.id, db=db, assigned_by=current_user["email"],
        user_email=user.email,
    )

    # This is the actual mechanism by which an account gains capability
    # (see docstring above), including potentially system_superuser itself,
    # so an unrecorded grant here is a real gap in the audit trail.
    # user_email is the RECEIVING user, consistent with every other audit
    # entry being keyed on whose account was affected; the granting user
    # goes in metadata, mirroring delete_any_user's assigned_by/deleted_by shape.
    await log_security_event(
        POLICY_ASSIGNED,
        db,
        user_email=user.email,
        success=True,
        request=request,
        metadata={"assigned_by": current_user["email"], "policy_name": policy.name},
    )
    await publish_permissions_changed(user.email)
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
    doesn't resolve).

    The caller must already hold every action this policy grants: without
    this, policies:revoke alone could strip an equally- or more-privileged
    peer's access (even system_superuser itself) with no escalation check
    at all, the one gap assign_policy_to_user's symmetric guard didn't
    cover. Mirrors the same guard on update_policy/delete_policy
    (policy_crud_routes.py)."""
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")
    policy = await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")

    # The reserved system account's authorization surface must never be
    # mutated through this generic route, mirroring the same guard on
    # update_user_role/update_user (user_management_update_routes.py).
    if user.role == UserRole.system:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SYSTEM_USER_CANNOT_BE_MODIFIED",
            detail="System user cannot be modified",
        )

    await authorization_service.assert_authorized_to_grant(
        current_user["email"], policy.actions, policy.resource_type, db,
        context=build_authorization_context(request), conditions=policy.conditions,
    )

    # Confirm holdership BEFORE the lockout check below: otherwise a target
    # who never held the policy would incorrectly trip the "last holder"
    # guard (and get a 409) instead of the correct 404 not-held error.
    if not await policy_repository.user_holds_policy(user.id, policy.id, db):
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="POLICY_NOT_HELD_BY_USER",
            detail=f"{user_email} does not hold policy '{policy_name}'",
            params={"userEmail": user_email, "policyName": policy_name},
        )

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
    await publish_permissions_changed(user.email)
    return {"detail": f"Policy '{policy_name}' removed from {user_email}"}


@router.post("/users/{user_email}/policies/{policy_name}/revoke-action")
async def revoke_policy_action_from_user(
    user_email: str,
    policy_name: str,
    revocation: PolicyActionRevocationRequest,
    request: Request,
    current_user: dict = REVOKE_DEPENDENCY,
    _permissions_grant: dict = PERMISSIONS_GRANT_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Carves ONE action out of a user's policy assignment: that single action
    is revoked, but every other action the policy grants this user is
    preserved (converted to a direct grant, see
    policy_action_revocation_service.py). Unlike remove_policy_from_user,
    this never touches the Policy row itself, so every OTHER holder of this
    policy is entirely unaffected.

    Requires BOTH policies:revoke (this ends the user's policy assignment)
    AND permissions:grant (this creates new direct grants for the actions
    kept): a caller holding only one of the two could otherwise use this
    route to do half of what either dedicated route alone would refuse.

    Same privilege-escalation guard as remove_policy_from_user, checked
    against the policy's FULL action set (not just the remaining ones):
    without it, a caller holding policies:revoke + permissions:grant but
    not the policy's own actions could still strip a more-privileged
    peer's access via this route.
    """
    user = await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")
    policy = await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")

    # The reserved system account's authorization surface must never be
    # mutated through this generic route, mirroring the same guard on
    # update_user_role/update_user (user_management_update_routes.py).
    if user.role == UserRole.system:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SYSTEM_USER_CANNOT_BE_MODIFIED",
            detail="System user cannot be modified",
        )

    await authorization_service.assert_authorized_to_grant(
        current_user["email"], policy.actions, policy.resource_type, db,
        context=build_authorization_context(request), conditions=policy.conditions,
    )

    # Confirm holdership BEFORE the lockout check below: otherwise a target
    # who never held the policy would incorrectly trip the "last holder"
    # guard (and get a 409) instead of the correct 404 not-held error.
    if not await policy_repository.user_holds_policy(user.id, policy.id, db):
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="POLICY_NOT_HELD_BY_USER",
            detail=f"{user_email} does not hold policy '{policy_name}'",
            params={"userEmail": user_email, "policyName": policy_name},
        )

    # Same lockout protection as remove_policy_from_user: this ends the
    # user's system_superuser ASSIGNMENT just like a plain revoke does,
    # even though most of their access is preserved as direct grants -
    # removing the last assignment would still leave no one able to manage
    # the authorization system as system_superuser itself.
    if policy_name == SYSTEM_SUPERUSER_POLICY_NAME:
        holder_count = await policy_repository.count_assignments(policy.id, db)
        if holder_count <= 1:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="CANNOT_REMOVE_LAST_SUPERUSER_ASSIGNMENT",
                detail="Cannot remove the last remaining assignment of 'system_superuser'",
            )

    try:
        removed = await policy_action_revocation_service.revoke_single_action(
            user_id=user.id,
            policy=policy,
            action=revocation.action,
            db=db,
            revoked_by=current_user["email"],
            user_email=user.email,
        )
    except ActionNotInPolicyError as exc:
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="ACTION_NOT_IN_POLICY",
            detail=str(exc),
            params={"action": revocation.action, "policyName": policy_name},
        ) from exc

    if not removed:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="POLICY_NOT_HELD_BY_USER",
            detail=f"{user_email} does not hold policy '{policy_name}'",
            params={"userEmail": user_email, "policyName": policy_name},
        )

    await log_security_event(
        POLICY_ACTION_REVOKED,
        db,
        user_email=user.email,
        success=True,
        request=request,
        metadata={
            "revoked_by": current_user["email"],
            "policy_name": policy_name,
            "action": revocation.action,
            "retained_actions": [a for a in policy.actions if a != revocation.action],
        },
    )
    await publish_permissions_changed(user.email)
    return {"detail": f"Action '{revocation.action}' revoked from {user_email}'s '{policy_name}' assignment; other actions retained as direct grants"}


@router.get("/users/{user_email}/policies", response_model=UserPoliciesRead)
async def list_user_policies(
    user_email: str,
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Every policy assigned to this user (active or not, for inspection,
    not an authorization decision)."""
    await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    policies = await policy_repository.get_policies_for_user(user_email, db)
    return UserPoliciesRead(user_email=user_email, policies=[PolicyRead.model_validate(p) for p in policies])
