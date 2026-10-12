from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ....audit_log.audit_log_service import USER_ROLE_CHANGED
from ....authorization.context.request_context_builder import build_authorization_context
from ....authorization.dependencies.authorization_dependency import require_authorization
from ....authorization.permissions import Permission
from ....authorization.schemas.bulk_schema import BulkItemResult, BulkResponse, BulkRoleRequest, bulk_error, summarize
from ....authorization.services.authorization_service import authorization_service
from ....authorization.services.bulk_notification import log_and_notify_bulk_success
from ....database.connection import database
from ....user.user_crud_collector import user_crud
from ....user.user_model import User, UserRole

router = APIRouter(prefix="/authorization", tags=["Authorization"])

_RESOURCE_TYPE = "users"


@router.post("/bulk/users/role", response_model=BulkResponse)
async def bulk_update_role(
    body: BulkRoleRequest,
    request: Request,
    current_user: dict = Depends(require_authorization(Permission.USERS_ASSIGN_ROLE.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Sets the (display/grouping-only, non-PBAC) role field for up to 200
    users in one request, best-effort per item. Re-applies the same
    safeguards as update_user_role (user_management_update_routes.py) per
    item: a `system`-role user's role can never be changed, and assigning
    `system` itself requires the separate users:assign_system_role action,
    and the caller can never change their own role (holding users:assign_role
    alone must not let someone self-promote), since the batch may mix
    system, self, and other targets.
    """
    users_by_email = await user_crud.get_by_emails([item.user_email for item in body.items], db)
    context = build_authorization_context(request)

    valid_items: list[tuple[User, UserRole]] = []
    error_results: list[BulkItemResult] = []
    for item in body.items:
        user = users_by_email.get(item.user_email)
        if user is None:
            error_results.append(bulk_error(item.user_email, item.role, "USER_NOT_FOUND"))
            continue

        try:
            role = UserRole(item.role)
        except ValueError:
            error_results.append(bulk_error(item.user_email, item.role, "INVALID_ROLE"))
            continue

        if user.role == UserRole.system:
            error_results.append(bulk_error(item.user_email, item.role, "SYSTEM_USER_ROLE_CANNOT_BE_CHANGED"))
            continue

        if item.user_email == current_user["email"]:
            error_results.append(bulk_error(item.user_email, item.role, "CANNOT_CHANGE_OWN_ROLE"))
            continue

        if role == UserRole.system:
            allowed = await authorization_service.authorize(
                current_user["email"], Permission.USERS_ASSIGN_SYSTEM_ROLE.value, _RESOURCE_TYPE, db,
                context=context,
            )
            if not allowed:
                error_results.append(bulk_error(item.user_email, item.role, "CANNOT_GRANT_UNHELD_ACTION"))
                continue

        valid_items.append((user, role))

    repo_results = await user_crud.bulk_update_role(valid_items, db)

    await log_and_notify_bulk_success(
        repo_results, USER_ROLE_CHANGED, db,
        actor_email=current_user["email"], actor_field="changed_by", identifier_field="new_role",
        notify_permissions_changed=False,
    )

    return summarize(error_results + repo_results)
