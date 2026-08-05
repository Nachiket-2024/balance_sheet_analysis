from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...authorization.conditions.condition_validator import ConditionValidationError, validate_conditions
from ...authorization.repositories.policy_history_repository import policy_history_repository
from ...authorization.repositories.policy_repository import policy_repository
from ...authorization.schemas.policy_history_schema import (
    PolicyHistoryCompareResponse,
    PolicyHistoryEntryRead,
    PolicyRollbackRequest,
)
from ...authorization.schemas.policy_schema import PolicyRead
from ...authorization.services.authorization_service import authorization_service
from ...database.connection import database
from ..get_or_404 import get_or_404
from .policy_permissions import PROTECTED_POLICY_NAMES, READ_DEPENDENCY, UPDATE_DEPENDENCY

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"History entry for '{label}' not found")
        if entry.policy_name != policy_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"History entry {entry.id} belongs to policy '{entry.policy_name}', not '{policy_name}'",
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
    rollback_request: PolicyRollbackRequest | None = None,
    current_user: dict = UPDATE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Restores a policy to a prior recorded definition. The policy must still
    exist: restoring a deleted policy isn't supported here; recreate it via
    POST /policies instead. Every history entry resolves to a restorable
    definition, including "deleted" entries (their previous_definition is
    their pre-deletion state, see _definition_for_entry), so rolling back
    to a point before the policy was ever deleted is a valid target.

    The restored snapshot is applied via PolicyRepository.update, tagged as
    a "rolled_back" change so it's distinguishable from an ordinary edit:
    this creates a new history entry and never overwrites or removes the
    entry being rolled back to.

    Restoring a historical definition is otherwise indistinguishable from an
    ordinary edit in terms of what it can grant, so it goes through the same
    guards as PUT /policies/{policy_name}: a malformed conditions block is
    rejected, baseline policies can't be renamed/deactivated, and the caller
    must already hold every action the restored definition would grant,
    since without this, rolling back to an old revision would be a way to silently
    re-grant a more powerful set of actions than update_policy would ever let
    the caller assign directly.
    """
    policy = await get_or_404(policy_repository.get_by_name(policy_name, db), "Policy not found")

    history_entry = await policy_history_repository.get_by_id(history_id, db)
    if not history_entry or history_entry.policy_name != policy_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found for this policy")

    target_definition = _definition_for_entry(history_entry)

    try:
        validate_conditions((target_definition or {}).get("conditions"))
    except ConditionValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors) from exc

    if policy.name in PROTECTED_POLICY_NAMES and (target_definition or {}).get("name") != policy.name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Baseline policy '{policy.name}' cannot be renamed",
        )

    if policy.name in PROTECTED_POLICY_NAMES and (target_definition or {}).get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Baseline policy '{policy.name}' cannot be deactivated",
        )

    await authorization_service.assert_authorized_to_grant(
        current_user["email"],
        (target_definition or {}).get("actions", []),
        (target_definition or {}).get("resource_type", policy.resource_type),
        db,
    )

    reason = rollback_request.reason if rollback_request else None
    return await policy_repository.update(
        policy, target_definition or {}, db,
        changed_by=current_user["email"],
        change_reason=reason or f"Rolled back to history entry {history_id}",
        change_type="rolled_back",
    )
