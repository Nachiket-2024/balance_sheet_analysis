import asyncio

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

# Rejects a malformed `conditions` block before it's ever persisted: unknown
# keys, wrong types, invalid timezones/IPs/dates must fail at write time, not
# surface later as a silent always-deny at evaluation time.
from ....authorization.conditions.condition_validator import ConditionValidationError, validate_conditions
from ....authorization.context.request_context_builder import build_authorization_context
from ....authorization.dependencies.policy_route_dependencies import (
    CREATE_DEPENDENCY,
    DELETE_DEPENDENCY,
    PROTECTED_POLICY_NAMES,
    READ_DEPENDENCY,
    UPDATE_DEPENDENCY,
)
from ....authorization.repositories.policy_repository import policy_repository
from ....authorization.schemas.policy_schema import PolicyCreate, PolicyRead, PolicyUpdate
from ....authorization.services.authorization_service import authorization_service
from ....core.errors import AppError
from ....core.search_query import SEARCH_QUERY_MAX_LENGTH
from ....database.connection import database
from ....user_session.session_events import publish_permissions_changed
from ...get_or_404.get_or_404 import get_or_404

router = APIRouter(prefix="/authorization", tags=["Authorization"])


@router.post("/policies", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: PolicyCreate,
    request: Request,
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
        current_user["email"], policy_data.actions, policy_data.resource_type, db,
        context=build_authorization_context(request), conditions=policy_data.conditions,
    )

    data = policy_data.model_dump()
    data["created_by"] = current_user["email"]
    return await policy_repository.create(data, db, changed_by=current_user["email"])


@router.get("/policies", response_model=list[PolicyRead])
async def list_policies(
    response: Response,
    limit: int = Query(default=1000, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(
        default=None,
        max_length=SEARCH_QUERY_MAX_LENGTH,
        description="Case-insensitive substring match on name or description",
    ),
    resource_type: str | None = Query(default=None, description="Exact match on resource_type"),
    is_active: bool | None = Query(default=None, description="Exact match on is_active"),
    contains_action: str | None = Query(
        default=None, description="Only policies whose actions array contains this exact action"
    ),
    destructive_only: bool = Query(
        default=False, description="Only policies containing a catalog-defined destructive action"
    ),
    sort_by: str | None = Query(
        default=None,
        description="Column to sort by: name, resource_type, is_active, created_at, or updated_at. "
        "Any other value (including unset) falls back to id.",
    ),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Every policy, active or not. X-Total-Count (not part of the response
    body, response_model stays a plain list) lets the frontend render
    numbered pages without a separate round trip, computed from the same
    filters so the page count always matches what's actually being paged
    through. Callers not passing any of search/resource_type/is_active/
    sort_by get the same unfiltered, id-ordered result this always
    returned (e.g. UserPoliciesDialog's "assign a policy" dropdown, which
    wants the full list)."""
    response.headers["X-Total-Count"] = str(
        await policy_repository.count(
            db, search=search, resource_type=resource_type, is_active=is_active,
            contains_action=contains_action, destructive_only=destructive_only,
        )
    )
    return await policy_repository.get_all_as_read_schemas(
        db,
        limit=limit,
        offset=offset,
        search=search,
        resource_type=resource_type,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
        contains_action=contains_action,
        destructive_only=destructive_only,
    )


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
    request: Request,
    current_user: dict = UPDATE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Partially updates a policy: only provided fields are applied (e.g. this
    can disable a policy via is_active=False without touching its actions).

    Baseline policies (self_service, user_management, system_superuser)
    can't be renamed away from their well-known name, since default
    assignments (signup, oauth2, create_system_user.py) look them up by
    name. They also can't be deactivated: is_active=False excludes a policy
    from evaluation for every holder at once, and for system_superuser that
    would silently strip every superuser of all access, bypassing both the
    rename/delete guards and the separate lockout guard on
    remove_policy_from_user (which only fires on unassignment).

    If actions are changing, the caller must already hold every action the
    policy would grant afterwards: otherwise policies:update alone could
    re-grant an existing, possibly widely-assigned policy new actions the
    caller doesn't have.

    Symmetrically, changing actions/resource_type/conditions or deactivating requires
    the caller to already hold every action the policy *currently* grants
    (checked pre-update), not just the post-update grant-side check above.
    Otherwise policies:update alone could narrow, retarget, or deactivate a
    policy a more-privileged peer depends on, stripping their access. A
    A pure description edit, or reactivating (is_active=True), doesn't change
    what the policy grants. Changing conditions is a grant-scope change and
    is checked against the caller's own matching grants.
    See delete_policy and remove_policy_from_user (policy_assignment_routes.py)
    for the same guard applied to delete and revoke, where removal is
    always a downgrade.
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

    context = build_authorization_context(request)

    if "actions" in fields or "resource_type" in fields or "conditions" in fields or fields.get("is_active") is False:
        await authorization_service.assert_authorized_to_grant(
            current_user["email"], policy.actions, policy.resource_type, db,
            context=context, conditions=policy.conditions,
        )

    if "actions" in fields or "resource_type" in fields or "conditions" in fields:
        target_actions = fields.get("actions", policy.actions)
        target_resource_type = fields.get("resource_type", policy.resource_type)
        target_conditions = fields.get("conditions", policy.conditions)
        await authorization_service.assert_authorized_to_grant(
            current_user["email"], target_actions, target_resource_type, db,
            context=context, conditions=target_conditions,
        )

    # A pure description/conditions edit (or reactivating via is_active=True)
    # doesn't change what any holder is actually granted - see this
    # function's own docstring - so only nudge holders' open tabs when the
    # change could actually alter their effective access. Fetched before the
    # update commits: holder_emails is unaffected either way (update() never
    # touches UserPolicy rows), but reading it up front keeps this query out
    # of the same transaction as the mutation below.
    affects_grants = "actions" in fields or "resource_type" in fields or "is_active" in fields
    holder_emails = await policy_repository.get_holder_emails(policy.id, db) if affects_grants else []

    updated = await policy_repository.update(
        policy, fields, db,
        changed_by=current_user["email"],
        change_reason=update_data.change_reason,
    )

    # Same real-time nudge as policy_assignment_routes.py's grant/revoke,
    # just fanned out to every current holder instead of one already-known
    # user_email: editing a policy's actions/resource_type/is_active changes
    # what everyone who holds it is granted, all at once, so every one of
    # their open tabs needs the same "go recheck your permissions" push.
    if holder_emails:
        await asyncio.gather(*(publish_permissions_changed(email) for email in holder_emails))

    return updated


@router.delete("/policies/{policy_name}")
async def delete_policy(
    policy_name: str,
    request: Request,
    reason: str | None = Query(default=None, max_length=500),
    current_user: dict = DELETE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Cascades to remove every assignment of this policy from every user
    (see UserPolicy's ondelete="CASCADE"). The policy's definition survives
    in policy_history (see /policies/{policy_name}/history) even after this
    deletion.

    The caller must already hold every action this policy grants: without
    this, policies:delete alone could strip an equally- or more-privileged
    peer's access by deleting a policy out from under them, something
    policies:delete was never meant to allow on its own. Mirrors the same
    guard on update_policy above and remove_policy_from_user
    (policy_assignment_routes.py)."""
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

    # Deactivation is the reversible safety step before a destructive delete.
    # Keep this invariant in the authoritative API as well as the Policies
    # page, so direct API callers cannot bypass the operator workflow and
    # immediately remove a policy that is still actively granting access.
    if policy.is_active:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="POLICY_MUST_BE_INACTIVE_TO_DELETE",
            detail=f"Policy '{policy_name}' must be inactive before it can be deleted",
            params={"policyName": policy_name},
        )

    await authorization_service.assert_authorized_to_grant(
        current_user["email"], policy.actions, policy.resource_type, db,
        context=build_authorization_context(request), conditions=policy.conditions,
    )

    # Fetched before delete(), which cascades UserPolicy rows away along
    # with the policy itself (see delete()'s own docstring) - there would be
    # no holders left to look up afterwards.
    holder_emails = await policy_repository.get_holder_emails(policy.id, db)

    await policy_repository.delete(policy, db, changed_by=current_user["email"], change_reason=reason)

    # Same fan-out nudge as update_policy above: deleting a policy strips
    # every holder's access to whatever it granted, all at once.
    if holder_emails:
        await asyncio.gather(*(publish_permissions_changed(email) for email in holder_emails))

    return {"detail": f"Policy '{policy_name}' deleted successfully"}
