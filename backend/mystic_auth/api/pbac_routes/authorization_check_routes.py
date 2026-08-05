from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# The one place ip_address/current_time/security_context are derived from
# the real request : batch-check builds this once, shared by every check
# in the batch (they're all the same incoming request)
from ...authorization.context.request_context_builder import build_authorization_context
from ...authorization.dependencies.authorization_dependency import require_authorization
from ...authorization.permissions import Permission
from ...authorization.schemas.batch_authorization_schema import (
    BatchAuthorizationCheckRequest,
    BatchAuthorizationCheckResponse,
    BatchAuthorizationCheckResult,
)
from ...authorization.schemas.policy_schema import AuthorizationCheckRequest, AuthorizationCheckResponse
from ...authorization.services.authorization_service import authorization_service
from ...database.connection import database
from ...user_crud.user_crud_collector import user_crud
from ..get_or_404 import get_or_404
from .policy_permissions import READ_DEPENDENCY

router = APIRouter(prefix="/authorization", tags=["Authorization"])


@router.post("/users/{user_email}/authorization-check", response_model=AuthorizationCheckResponse)
async def check_user_authorization(
    user_email: str,
    check: AuthorizationCheckRequest,
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """
    Calculates a user's effective authorization for an action, using POST
    (not GET+query params) because check.resource/context are arbitrary
    nested JSON, needed to evaluate ownership/resource-attribute/context
    conditions (e.g. "would this user be allowed to publish *this specific*
    draft document?"), not just a resource-type-level check.

    Runs the exact same decision logic the app itself would use for this
    user/action/resource/context (via AuthorizationService.authorize_detailed
    : no separate/duplicated evaluation logic), returning both the outcome
    and which policies were candidates vs. which actually granted it.

    This endpoint deliberately accepts check.context as caller-supplied :
    unlike every real protected route (which builds context itself via
    context/request_context_builder.py and never trusts a client-supplied
    value), this is a hypothetical "what would happen if" simulation tool
    for admins/operators, not a real access decision, so there is nothing
    to forge: no actual authorization outcome depends on it.
    """
    await get_or_404(user_crud.get_by_email(user_email, db), "User not found")

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
    authorization in one request (see schemas/batch_authorization_schema.py
    for the exact bounds and per-field validation : malformed/oversized/
    empty batches are rejected by the schema itself, before this function
    runs). Requires only users:read_own, the baseline every real account
    holds via self_service: unlike the /users/{email}/authorization-check
    admin inspection tool (which checks *someone else's* access and needs
    policies:read), this endpoint always checks the caller's *own*
    effective authorization, so the bar is simply "you're a legitimate,
    onboarded account" rather than an elevated permission.

    Builds the real request context once and delegates the whole batch to
    AuthorizationService.authorize_batch, which fetches the caller's
    policies exactly once and reuses them for every check : avoiding
    repeated policy database queries within the batch : while calling the
    exact same PolicyEvaluationEngine used by every single authorize()
    call, so a batch-of-one check always agrees with calling authorize()
    directly for that same input. Each check is logged individually,
    exactly like a real authorize() call : this is a real decision, not a
    hypothetical "what if" simulation.

    The response exposes only `allowed` and a coarse `denial_reason` per
    check, deliberately never policy names or failed condition keys : those
    stay reserved for the admin inspection endpoint above.
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
