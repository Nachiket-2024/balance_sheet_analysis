import asyncio

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....authorization.conditions.condition_validator import ConditionValidationError, validate_conditions
from ....authorization.context.request_context_builder import build_authorization_context
from ....authorization.dependencies.policy_route_dependencies import (
    PROTECTED_POLICY_NAMES,
    READ_DEPENDENCY,
    UPDATE_DEPENDENCY,
)
from ....authorization.repositories.policy_history_repository import policy_history_repository
from ....authorization.repositories.policy_repository import policy_repository
from ....authorization.schemas.policy_history_schema import (
    PolicyHistoryCompareResponse,
    PolicyHistoryEntryRead,
    PolicyRollbackRequest,
)
from ....authorization.schemas.policy_schema import PolicyRead
from ....authorization.services.authorization_service import authorization_service
from ....core.errors import AppError
from ....database.connection import database
from ....user_session.session_events import publish_permissions_changed
from ...get_or_404.get_or_404 import get_or_404

router = APIRouter(prefix="/authorization", tags=["Authorization"])


def _definition_for_entry(entry) -> dict | None:
    """
    The full policy definition snapshot "at" a given history entry: its
    new_definition, or (for a "deleted" entry, which has none) its
    previous_definition instead, so every entry type resolves to a
    comparable/rollback-able snapshot without compare/rollback needing
    special-case handling per change_type.
    """
    return entry.new_definition if entry.new_definition is not None else entry.previous_definition


@router.get("/policies/{policy_name}/history", response_model=list[PolicyHistoryEntryRead])
async def list_policy_history(
    policy_name: str,
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Every recorded change to this policy, newest first. Works even after
    the policy itself has been deleted (history is keyed by policy_name,
    not a live foreign key, see policy_history_model.py).
    """
    response.headers["X-Total-Count"] = str(await policy_history_repository.count_for_policy(policy_name, db))
    return await policy_history_repository.get_for_policy(policy_name, db, limit=limit, offset=offset)


@router.get("/policies/{policy_name}/history/compare", response_model=PolicyHistoryCompareResponse)
async def compare_policy_history(
    policy_name: str,
    from_id: int = Query(..., description="History entry id to compare from"),
    to_id: int = Query(..., description="History entry id to compare to"),
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Resolves both history entries, confirms both belong to policy_name (a
    from/to pair spanning two different policies would be meaningless), and
    diffs their definition snapshots field by field.
    """
    from_entry = await policy_history_repository.get_by_id(from_id, db)
    to_entry = await policy_history_repository.get_by_id(to_id, db)

    for entry, label in ((from_entry, "from_id"), (to_entry, "to_id")):
        if not entry:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="HISTORY_ENTRY_NOT_FOUND",
                detail=f"History entry for '{label}' not found",
                params={"field": label},
            )
        if entry.policy_name != policy_name:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="HISTORY_ENTRY_POLICY_MISMATCH",
                detail=f"History entry {entry.id} belongs to policy '{entry.policy_name}', not '{policy_name}'",
                params={"entryId": entry.id, "entryPolicyName": entry.policy_name, "policyName": policy_name},
            )

    from_definition = _definition_for_entry(from_entry)
    to_definition = _definition_for_entry(to_entry)

    all_fields = set((from_definition or {}).keys()) | set((to_definition or {}).keys())
    diff = {}
    for field in all_fields:
        old_value = (from_definition or {}).get(field)
        new_value = (to_definition or {}).get(field)
        if old_value != new_value:
            diff[field] = {"from": old_value, "to": new_value}

    return PolicyHistoryCompareResponse(
        policy_name=policy_name,
        from_history_id=from_id,
        to_history_id=to_id,
        from_definition=from_definition,
        to_definition=to_definition,
        changed_fields=sorted(diff.keys()),
        diff=diff,
    )


@router.post("/policies/{policy_name}/history/{history_id}/rollback", response_model=PolicyRead)
async def rollback_policy(
    policy_name: str,
    history_id: int,
    request: Request,
    rollback_request: PolicyRollbackRequest | None = None,
    current_user: dict = UPDATE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Restores a policy to a prior recorded definition. The policy must still
    exist: restoring a deleted policy isn't supported here; recreate it via
    POST /policies instead. Every history entry resolves to a restorable
    definition, including "deleted" entries (see _definition_for_entry), so
    rolling back to before the policy was deleted is a valid target.

    Applied via PolicyRepository.update, tagged as a "rolled_back" change so
    it's distinguishable from an ordinary edit: this creates a new history
    entry rather than overwriting the one being restored. Like
    update_policy, it can silently re-grant or strip access for every
    current holder, so it fans out the same publish_permissions_changed
    nudge (see policy_crud_routes.py and
    docs/mystic_auth/authorization/architecture/real-time-push.md).

    Goes through the same guards as PUT /policies/{policy_name}: malformed
    conditions are rejected, baseline policies can't be renamed/deactivated,
    and the caller must hold both the policy's CURRENT actions and the
    target (post-rollback) actions - the same symmetric pair update_policy
    enforces. Without the current-actions check, rolling back a
    widely-assigned policy could silently strip other holders' access;
    without the target-actions check, it would let a caller re-grant more
    than update_policy would ever let them assign directly.
    """
    policy = await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found", code="POLICY_NOT_FOUND")

    history_entry = await policy_history_repository.get_by_id(history_id, db)
    if not history_entry or history_entry.policy_name != policy_name:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="HISTORY_ENTRY_NOT_FOUND_FOR_POLICY",
            detail="History entry not found for this policy",
        )

    target_definition = _definition_for_entry(history_entry)

    try:
        validate_conditions((target_definition or {}).get("conditions"))
    except ConditionValidationError as exc:
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, code="INVALID_CONDITIONS", detail=exc.errors
        ) from exc

    if policy.name in PROTECTED_POLICY_NAMES and (target_definition or {}).get("name") != policy.name:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="BASELINE_POLICY_CANNOT_BE_RENAMED",
            detail=f"Baseline policy '{policy.name}' cannot be renamed",
            params={"policyName": policy.name},
        )

    if policy.name in PROTECTED_POLICY_NAMES and (target_definition or {}).get("is_active") is False:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="BASELINE_POLICY_CANNOT_BE_DEACTIVATED",
            detail=f"Baseline policy '{policy.name}' cannot be deactivated",
            params={"policyName": policy.name},
        )

    context = build_authorization_context(request)

    # Symmetric with update_policy's two-guard pattern: one check against
    # the policy's current actions, one against the target (post-rollback)
    # actions. Without this half, policies:update alone could roll back a
    # widely-assigned policy to a definition the caller doesn't hold,
    # silently stripping every other holder's access.
    await authorization_service.assert_authorized_to_grant(
        current_user["email"], policy.actions, policy.resource_type, db,
        context=context, conditions=policy.conditions,
    )

    await authorization_service.assert_authorized_to_grant(
        current_user["email"],
        (target_definition or {}).get("actions", []),
        (target_definition or {}).get("resource_type", policy.resource_type),
        db,
        context=context, conditions=(target_definition or {}).get("conditions"),
    )

    # Fetched before update() mutates the policy: rollback always restores
    # actions/resource_type/is_active (target_definition is the full
    # snapshot, see _definition_for_entry), so unlike update_policy's
    # partial PATCH this is never a no-op-for-grants case - every current
    # holder needs the nudge.
    holder_emails = await policy_repository.get_holder_emails(policy.id, db)

    reason = rollback_request.reason if rollback_request else None
    updated = await policy_repository.update(
        policy, target_definition or {}, db,
        changed_by=current_user["email"],
        change_reason=reason or f"Rolled back to history entry {history_id}",
        change_type="rolled_back",
    )

    if holder_emails:
        await asyncio.gather(*(publish_permissions_changed(email) for email in holder_emails))

    return updated
