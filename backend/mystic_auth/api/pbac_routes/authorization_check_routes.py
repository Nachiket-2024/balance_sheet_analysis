from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# ip_address/current_time/security_context are derived from the real
# request here once, then shared by every check in the batch below.
from ...authorization.context.request_context_builder import build_authorization_context
from ...authorization.dependencies.authorization_dependency import require_authorization
from ...authorization.dependencies.policy_route_dependencies import READ_DEPENDENCY
from ...authorization.permissions import Permission
from ...authorization.schemas.batch_authorization_schema import (
    BatchAuthorizationCheckRequest,
    BatchAuthorizationCheckResponse,
    BatchAuthorizationCheckResult,
)
from ...authorization.schemas.policy_schema import AuthorizationCheckRequest, AuthorizationCheckResponse
from ...authorization.services.authorization_service import authorization_service
from ...database.connection import database
from ...user.user_crud_collector import user_crud
from ..get_or_404.get_or_404 import get_or_404

router = APIRouter(prefix="/authorization", tags=["Authorization"])


@router.post("/users/{user_email}/authorization-check", response_model=AuthorizationCheckResponse)
async def check_user_authorization(
    user_email: str,
    check: AuthorizationCheckRequest,
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Calculates a user's effective authorization for an action. Uses POST
    (not GET+query params) because check.resource/context are arbitrary
    nested JSON, needed to evaluate ownership/resource-attribute/context
    conditions (e.g. "would this user be allowed to publish *this specific*
    draft document?"), not just a resource-type-level check.

    Runs the exact same decision logic the app itself would use, via
    AuthorizationService.authorize_detailed, returning both the outcome and
    which policies were candidates vs. which actually granted it.

    Unlike every real protected route (which builds context itself and
    never trusts a client-supplied value), this endpoint accepts
    check.context from the caller: it's a hypothetical "what would happen
    if" simulation tool for operators, not a real access decision, so
    there's nothing to forge here.
    """
    await get_or_404(user_crud.get_by_email(user_email, db), "User not found", code="USER_NOT_FOUND")

    decision = await authorization_service.authorize_detailed(
        user_email, check.action, check.resource_type, db,
        resource=check.resource, context=check.context,
    )

    return AuthorizationCheckResponse(
        user_email=user_email,
        action=check.action,
        resource_type=check.resource_type,
        authorized=decision.allowed,
        candidate_policies=decision.matched_policies + decision.rejected_policies,
        granting_policies=decision.matched_policies,
        rejected_policies=decision.rejected_policies,
        failed_conditions=decision.failed_conditions,
        denial_reason=decision.denial_reason,
        evaluated_policies=decision.evaluated_policies,
        evaluation_timestamp=decision.evaluation_timestamp,
    )


@router.post("/batch-check", response_model=BatchAuthorizationCheckResponse)
async def batch_check_authorization(
    request: Request,
    batch: BatchAuthorizationCheckRequest,
    current_user: dict = Depends(require_authorization(Permission.USERS_READ_OWN.value, "users")),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Runs 1-50 authorization checks for the caller's own effective
    authorization in one request (bounds and per-field validation live in
    schemas/batch_authorization_schema.py). Requires only users:read_own,
    the baseline every real account holds: unlike the
    /users/{email}/authorization-check operator tool (which checks
    *someone else's* access and needs policies:read), this always checks
    the caller's *own* access, so the bar is just "you're a legitimate
    account".

    Builds the request context once and delegates the batch to
    AuthorizationService.authorize_batch, which fetches the caller's
    policies once and reuses them for every check, while still calling the
    same PolicyEvaluationEngine used by a single authorize() call, so
    results always agree. Each check is logged individually: this is a real
    decision, not a hypothetical simulation.

    The response exposes only `allowed` and a coarse `denial_reason` per
    check: policy names and failed condition keys stay reserved for the
    operator inspection endpoint above.
    """
    context = build_authorization_context(request)

    checks = [
        {"action": item.action, "resource_type": item.resource_type, "resource": item.resource}
        for item in batch.checks
    ]

    decisions = await authorization_service.authorize_batch(
        current_user["email"], checks, db, context=context
    )

    return BatchAuthorizationCheckResponse(
        results=[
            BatchAuthorizationCheckResult(
                action=decision.action,
                resource_type=decision.resource_type,
                allowed=decision.allowed,
                denial_reason=decision.denial_reason,
            )
            for decision in decisions
        ]
    )
