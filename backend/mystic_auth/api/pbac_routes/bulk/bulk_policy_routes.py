from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ....audit_log.audit_log_service import POLICY_ASSIGNED, POLICY_REVOKED
from ....authorization.context.request_context_builder import build_authorization_context
from ....authorization.dependencies.policy_route_dependencies import ASSIGN_DEPENDENCY, REVOKE_DEPENDENCY
from ....authorization.policies.default_policies import SYSTEM_SUPERUSER_POLICY_NAME
from ....authorization.repositories.policy_repository import policy_repository
from ....authorization.schemas.bulk_schema import BulkItemResult, BulkPolicyRequest, BulkResponse, bulk_error, summarize
from ....authorization.services.authorization_service import authorization_service
from ....authorization.services.bulk_notification import log_and_notify_bulk_success
from ....core.errors import AppError
from ....database.connection import database
from ....user.user_crud_collector import user_crud
from ....user.user_model import UserRole

router = APIRouter(prefix="/authorization", tags=["Authorization"])


async def _resolve_and_authorize(
    item, users_by_email: dict, policies_by_name: dict, current_user_email: str, db: AsyncSession, context,
    grant_cache: dict, error_results: list[BulkItemResult],
):
    """Shared per-item validation for both assign and remove: user and
    policy exist, user isn't system-role, and the caller actually holds
    every action the policy grants. Returns the resolved (User, Policy), or
    None with the failure already appended to error_results."""
    user = users_by_email.get(item.user_email)
    policy = policies_by_name.get(item.policy_name)
    if user is None:
        error_results.append(bulk_error(item.user_email, item.policy_name, "USER_NOT_FOUND"))
        return None
    if policy is None:
        error_results.append(bulk_error(item.user_email, item.policy_name, "POLICY_NOT_FOUND"))
        return None
    if user.role == UserRole.system:
        error_results.append(bulk_error(item.user_email, item.policy_name, "SYSTEM_USER_CANNOT_BE_MODIFIED"))
        return None
    try:
        await authorization_service.assert_authorized_to_grant(
            current_user_email, policy.actions, policy.resource_type, db,
            context=context, conditions=policy.conditions, cache=grant_cache,
        )
    except AppError:
        error_results.append(bulk_error(item.user_email, item.policy_name, "CANNOT_GRANT_UNHELD_ACTION"))
        return None
    return user, policy


@router.post("/bulk/policies/assign", response_model=BulkResponse)
async def bulk_assign_policies(
    body: BulkPolicyRequest,
    request: Request,
    current_user: dict = ASSIGN_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Assigns one policy each to up to 200 (user_email, policy_name) pairs in
    one request, best-effort per item (see bulk_schema.py). Route-level
    ASSIGN_DEPENDENCY gates "can this caller attempt bulk policy assignment
    at all"; the same per-item privilege-escalation guard
    assign_policy_to_user enforces (assert_authorized_to_grant) is
    re-applied per item below, since holding policies:assign in general
    does not mean every specific policy in this batch is one the caller
    may hand out.
    """
    users_by_email = await user_crud.get_by_emails([item.user_email for item in body.items], db)
    policies_by_name = await policy_repository.get_policies_by_names(
        [item.policy_name for item in body.items], db
    )

    context = build_authorization_context(request)
    grant_cache: dict[tuple[str, str], bool] = {}
    valid_items = []
    error_results: list[BulkItemResult] = []
    for item in body.items:
        resolved = await _resolve_and_authorize(
            item, users_by_email, policies_by_name, current_user["email"], db, context, grant_cache, error_results
        )
        if resolved is None:
            continue
        valid_items.append(resolved)

    repo_results = await policy_repository.bulk_assign_policies(valid_items, db, assigned_by=current_user["email"])

    await log_and_notify_bulk_success(
        repo_results, POLICY_ASSIGNED, db,
        actor_email=current_user["email"], actor_field="assigned_by", identifier_field="policy_name",
    )

    return summarize(error_results + repo_results)


@router.post("/bulk/policies/remove", response_model=BulkResponse)
async def bulk_remove_policies(
    body: BulkPolicyRequest,
    request: Request,
    current_user: dict = REVOKE_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Removal counterpart to bulk_assign_policies. Mirrors the same
    resolve -> per-item guard -> stage -> commit-once shape."""
    users_by_email = await user_crud.get_by_emails([item.user_email for item in body.items], db)
    policies_by_name = await policy_repository.get_policies_by_names(
        [item.policy_name for item in body.items], db
    )

    # Batch-aware lockout guard: unlike single-item routes, a bulk request
    # commits every item in one pass, so the holder count doesn't shrink
    # between items. Count staged system_superuser removals as we go and
    # reject once that would exhaust the policy's holders, or a caller could
    # strip every superuser assignment in one call. Tracking holder *emails*
    # (not just a count) keeps a no-op item (targeting a non-holder) from
    # wrongly counting against the lockout. get_holder_emails_for_update
    # locks the rows so two concurrent bulk-removes can't together strip
    # every holder while each individually passes this guard.
    superuser_policy = policies_by_name.get(SYSTEM_SUPERUSER_POLICY_NAME)
    superuser_holder_emails = (
        set(await policy_repository.get_holder_emails_for_update(superuser_policy.id, db))
        if superuser_policy
        else set()
    )
    superuser_holder_count = len(superuser_holder_emails)
    superuser_removals_staged = 0

    context = build_authorization_context(request)
    grant_cache: dict[tuple[str, str], bool] = {}
    valid_items = []
    error_results: list[BulkItemResult] = []
    for item in body.items:
        resolved = await _resolve_and_authorize(
            item, users_by_email, policies_by_name, current_user["email"], db, context, grant_cache, error_results
        )
        if resolved is None:
            continue
        user, policy = resolved
        # Only an item that actually holds the policy counts against the
        # lockout - a no-op removal for a non-holder must not inflate the
        # staged count (see the comment above superuser_holder_emails).
        if item.policy_name == SYSTEM_SUPERUSER_POLICY_NAME and user.email in superuser_holder_emails:
            if superuser_removals_staged + 1 >= superuser_holder_count:
                error_results.append(
                    bulk_error(item.user_email, item.policy_name, "CANNOT_REMOVE_LAST_SUPERUSER_ASSIGNMENT")
                )
                continue
            superuser_removals_staged += 1
        valid_items.append((user, policy))

    repo_results = await policy_repository.bulk_remove_policies(valid_items, db)

    await log_and_notify_bulk_success(
        repo_results, POLICY_REVOKED, db,
        actor_email=current_user["email"], actor_field="revoked_by", identifier_field="policy_name",
    )

    return summarize(error_results + repo_results)
