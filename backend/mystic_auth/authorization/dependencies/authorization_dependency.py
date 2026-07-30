from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.current_user.current_user_dependency import get_current_user
from ...database.connection import database
from ..context.request_context_builder import build_authorization_context
from ..services.authorization_service import authorization_service


def require_authorization(action: str, resource_type: str):
    """
    Returns a FastAPI dependency usable as
    `Depends(require_authorization("users:list_all", "users"))` that
    authenticates the caller, builds the request's authorization context
    (real connection/server clock only, never anything client-supplied,
    see context/request_context_builder.py), and delegates the actual
    decision entirely to AuthorizationService.require. On success it
    returns the authenticated current_user dict for the route to use.

    This is the PBAC replacement for the RBAC-era
    authorization.permission_checker.require_permission (removed): routes
    declare *what action on what resource* they need; the authorization
    service and policy evaluation engine behind it decide *who currently
    has that*, based entirely on assigned policies. No role ever enters
    this decision, and this dependency itself never inspects
    current_user["role"].
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
