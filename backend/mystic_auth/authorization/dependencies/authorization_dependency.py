from collections.abc import Awaitable, Callable

from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.current_user.current_user_dependency import get_current_user
from ...core.errors import AppError
from ...database.connection import database
from ..context.request_context_builder import build_authorization_context
from ..services.authorization_service import authorization_service


def require_authorization(action: str, resource_type: str) -> Callable[..., Awaitable[dict]]:
    """
    Returns a FastAPI dependency usable as
    `Depends(require_authorization("users:list_all", "users"))`: it
    authenticates the caller, builds the request's authorization context
    (server-side only, never client-supplied), and delegates the decision
    to AuthorizationService.require. Returns the current_user dict on
    success.

    Routes declare what action on what resource they need; assigned
    policies decide who has it. No role ever enters this decision, and
    this dependency never inspects current_user["role"].
    """
    async def dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(database.get_session),
    ) -> dict:
        context = build_authorization_context(request)

        await authorization_service.require(
            user_email=current_user["email"],
            action=action,
            resource_type=resource_type,
            db=db,
            context=context,
        )

        return current_user

    return dependency


def require_any_authorization(checks: list[tuple[str, str]]) -> Callable[..., Awaitable[dict]]:
    """
    Returns a FastAPI dependency that allows the request through if the
    caller holds ANY ONE of the given (action, resource_type) pairs
    (FastAPI's `Depends` has no built-in OR, so this can't be composed
    from multiple require_authorization calls).

    For a route needed by more than one otherwise-independent action
    (e.g. GET /permissions/catalog, needed by both the Permissions page
    and the Policy form), gating behind a single action would wrongly
    deny a caller who only holds one of them. Each candidate is checked
    via the non-raising, non-logging `authorize_detailed()`: these are
    hypothetical probes, so a caller who only holds the last candidate
    doesn't get a "denied" audit row for the earlier ones they weren't
    really attempting. The one real decision is logged via `authorize()`
    once a match is found.
    """
    async def dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(database.get_session),
    ) -> dict:
        context = build_authorization_context(request)

        for action, resource_type in checks:
            decision = await authorization_service.authorize_detailed(
                user_email=current_user["email"],
                action=action,
                resource_type=resource_type,
                db=db,
                context=context,
            )
            if decision.allowed:
                # Re-check (and this time log) only the candidate that
                # actually succeeded, so the audit trail records the real
                # decision without the earlier candidates' spurious denials.
                await authorization_service.authorize(
                    user_email=current_user["email"],
                    action=action,
                    resource_type=resource_type,
                    db=db,
                    context=context,
                )
                return current_user

        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            detail="Insufficient permissions",
        )

    return dependency
