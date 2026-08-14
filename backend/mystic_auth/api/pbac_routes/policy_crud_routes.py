from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

# Rejects a malformed `conditions` block before it's ever persisted: unknown
# keys, wrong types, invalid timezones/IPs/dates must fail at write time, not
# surface later as a silent always-deny at evaluation time.
from ...authorization.conditions.condition_validator import ConditionValidationError, validate_conditions
from ...authorization.dependencies.policy_route_dependencies import (
    CREATE_DEPENDENCY,
    DELETE_DEPENDENCY,
    PROTECTED_POLICY_NAMES,
    READ_DEPENDENCY,
    UPDATE_DEPENDENCY,
)
from ...authorization.repositories.policy_repository import policy_repository
from ...authorization.schemas.policy_schema import PolicyCreate, PolicyRead, PolicyUpdate
from ...authorization.services.authorization_service import authorization_service
from ...core.errors import AppError
from ...database.connection import database
from ..get_or_404.get_or_404 import get_or_404

router = APIRouter(prefix="/authorization", tags=["Authorization"])


@router.post("/policies", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: PolicyCreate,
    current_user: dict = CREATE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Creates a policy after rejecting a malformed conditions block, a
    duplicate name, or a grant that exceeds the caller's own actions."""
    try:
        validate_conditions(policy_data.conditions)
    except ConditionValidationError as exc:
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, code="INVALID_CONDITIONS", detail=exc.errors
        ) from exc

    # Reject a duplicate name up front with a clear 409, rather than letting
    # the database's unique constraint raise an opaque 500.
    existing = await policy_repository.get_by_name(policy_data.name, db)
    if existing:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="POLICY_NAME_EXISTS",
            detail=f"A policy named '{policy_data.name}' already exists",
            params={"policyName": policy_data.name},
        )

    # Privilege-escalation guard: the caller cannot mint a policy granting an
    # action they do not themselves hold, since otherwise policies:create alone
    # (without system_superuser itself) would let a caller mint an
    # arbitrarily powerful policy.
    await authorization_service.assert_authorized_to_grant(
        current_user["email"], policy_data.actions, policy_data.resource_type, db
    )

    data = policy_data.model_dump()
    data["created_by"] = current_user["email"]
    return await policy_repository.create(data, db, changed_by=current_user["email"])


@router.get("/policies", response_model=list[PolicyRead])
async def list_policies(
    limit: int = Query(default=1000, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Every policy, active or not."""
    return await policy_repository.get_all(db, limit=limit, offset=offset)


@router.get("/policies/{policy_name}", response_model=PolicyRead)
async def get_policy(
    policy_name: str,
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """The named policy, or 404 if it doesn't exist."""
    return await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")


@router.put("/policies/{policy_name}", response_model=PolicyRead)
async def update_policy(
    policy_name: str,
    update_data: PolicyUpdate,
    current_user: dict = UPDATE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Partially updates a policy: only provided fields are applied (e.g.
    this can disable a policy via is_active=False without touching its
    actions).

    Baseline policies (self_service, user_administration, system_superuser)
    cannot be renamed away from their well-known name, since every default
    assignment (signup, oauth2, create_system_user.py) looks them up by
    name. They also cannot be deactivated: is_active=False excludes a
    policy from evaluation for every holder simultaneously, and for
    system_superuser specifically that would silently strip every superuser
    (including the true system account) of all access, bypassing both the
    rename/delete guards and the separate "last remaining assignment"
    lockout guard on remove_policy_from_user (which only fires on
    unassignment, a different endpoint this doesn't go through).

    If actions are being changed, the caller must already hold every action
    the policy would grant afterwards, since without this, policies:update alone
    could silently re-grant an existing (possibly widely-assigned) policy
    new, more powerful actions the caller doesn't themselves have.
    """
    policy = await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")

    fields = update_data.model_dump(exclude_unset=True, exclude={"change_reason"})

    # exclude_unset means "conditions" is absent entirely when the caller
    # isn't changing it, so this only fires when the update actually
    # touches conditions.
    if "conditions" in fields:
        try:
            validate_conditions(fields["conditions"])
        except ConditionValidationError as exc:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, code="INVALID_CONDITIONS", detail=exc.errors
            ) from exc

    if policy.name in PROTECTED_POLICY_NAMES and "name" in fields and fields["name"] != policy.name:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="BASELINE_POLICY_CANNOT_BE_RENAMED",
            detail=f"Baseline policy '{policy.name}' cannot be renamed",
            params={"policyName": policy.name},
        )

    # Reject a rename that collides with another existing policy up front
    # with a clear 409, rather than letting the database's unique
    # constraint raise an opaque 500; mirrors the same check in create_policy.
    if "name" in fields and fields["name"] != policy.name:
        existing = await policy_repository.get_by_name(fields["name"], db)
        if existing:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="POLICY_NAME_EXISTS",
                detail=f"A policy named '{fields['name']}' already exists",
                params={"policyName": fields["name"]},
            )

    if policy.name in PROTECTED_POLICY_NAMES and fields.get("is_active") is False:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="BASELINE_POLICY_CANNOT_BE_DEACTIVATED",
            detail=f"Baseline policy '{policy.name}' cannot be deactivated",
            params={"policyName": policy.name},
        )

    if "actions" in fields or "resource_type" in fields:
        target_actions = fields.get("actions", policy.actions)
        target_resource_type = fields.get("resource_type", policy.resource_type)
        await authorization_service.assert_authorized_to_grant(
            current_user["email"], target_actions, target_resource_type, db
        )

    return await policy_repository.update(
        policy, fields, db,
        changed_by=current_user["email"],
        change_reason=update_data.change_reason,
    )


@router.delete("/policies/{policy_name}")
async def delete_policy(
    policy_name: str,
    reason: str | None = Query(default=None, max_length=500),
    current_user: dict = DELETE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Cascades to remove every assignment of this policy from every user
    (see UserPolicy's ondelete="CASCADE"). The policy's definition survives
    in policy_history (see /policies/{policy_name}/history) even after this
    deletion."""
    policy = await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")

    # Baseline policies are load-bearing: signup, oauth2, and
    # create_system_user.py all look them up by name and assume they exist.
    # Deleting one would silently leave every future account with no
    # default access.
    if policy_name in PROTECTED_POLICY_NAMES:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="BASELINE_POLICY_CANNOT_BE_DELETED",
            detail=f"Baseline policy '{policy_name}' cannot be deleted",
            params={"policyName": policy_name},
        )

    await policy_repository.delete(policy, db, changed_by=current_user["email"], change_reason=reason)
    return {"detail": f"Policy '{policy_name}' deleted successfully"}
