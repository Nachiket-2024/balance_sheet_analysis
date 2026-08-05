from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

# Authentication-only dependency (no permission required) : used by
# /audit-log/me, where a user inspects their own decisions regardless of
# whether they hold policies:read
from ...auth.current_user.current_user_dependency import get_current_user
from ...authorization.repositories.audit_log_repository import audit_log_repository
from ...authorization.schemas.audit_log_schema import AuditLogEntryRead
from ...database.connection import database
from ...user_crud.user_crud_collector import user_crud
from ..get_or_404 import get_or_404
from .policy_permissions import READ_DEPENDENCY

router = APIRouter(prefix="/authorization", tags=["Authorization"])


_SORT_BY_DESCRIPTION = (
    "Column to sort by: created_at, user_email, action, resource_type, or allowed. "
    "Any other value (including unset) falls back to created_at."
)
_ACTION_DESCRIPTION = "Exact match on action (see authorization/permissions.py's Permission values)"
_RESOURCE_TYPE_DESCRIPTION = "Exact match on resource_type"
_ALLOWED_DESCRIPTION = "Exact match on allowed (true = Allowed, false = Denied)"


@router.get("/audit-log", response_model=list[AuditLogEntryRead])
async def list_audit_log(
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Case-insensitive substring match on user_email"),
    action: str | None = Query(default=None, description=_ACTION_DESCRIPTION),
    resource_type: str | None = Query(default=None, description=_RESOURCE_TYPE_DESCRIPTION),
    allowed: bool | None = Query(default=None, description=_ALLOWED_DESCRIPTION),
    sort_by: str | None = Query(default=None, description=_SORT_BY_DESCRIPTION),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Authorization decisions across every user, newest first by default.
    Every real authorize()/require() call anywhere in the app writes one of
    these rows automatically (see AuthorizationService._log_decision) :
    nothing needs to opt in."""
    # X-Total-Count (see list_all_users' identical pattern) lets the
    # frontend render numbered pages without a separate round trip. Computed
    # from the same filters so the page count always matches what's
    # actually being paged through.
    response.headers["X-Total-Count"] = str(
        await audit_log_repository.count(db, search=search, action=action, resource_type=resource_type, allowed=allowed)
    )
    return await audit_log_repository.get_all(
        db,
        limit=limit,
        offset=offset,
        search=search,
        action=action,
        resource_type=resource_type,
        allowed=allowed,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/audit-log/me", response_model=list[AuditLogEntryRead])
async def list_my_audit_log(
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, description=_ACTION_DESCRIPTION),
    resource_type: str | None = Query(default=None, description=_RESOURCE_TYPE_DESCRIPTION),
    allowed: bool | None = Query(default=None, description=_ALLOWED_DESCRIPTION),
    sort_by: str | None = Query(default=None, description=_SORT_BY_DESCRIPTION),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    The caller's own authorization decisions, newest first by default. No
    policies:read (or any other) permission required, since a user
    inspecting their own authorization history is not a privileged
    operation. Scoped server-side to current_user's email : the caller
    cannot request another user's entries through this endpoint (see
    list_audit_log_for_user for that, which does require policies:read).
    """
    response.headers["X-Total-Count"] = str(
        await audit_log_repository.count_for_user(
            current_user["email"], db, action=action, resource_type=resource_type, allowed=allowed
        )
    )
    return await audit_log_repository.get_for_user(
        current_user["email"],
        db,
        limit=limit,
        offset=offset,
        action=action,
        resource_type=resource_type,
        allowed=allowed,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/audit-log/users/{user_email}", response_model=list[AuditLogEntryRead])
async def list_audit_log_for_user(
    user_email: str,
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, description=_ACTION_DESCRIPTION),
    resource_type: str | None = Query(default=None, description=_RESOURCE_TYPE_DESCRIPTION),
    allowed: bool | None = Query(default=None, description=_ALLOWED_DESCRIPTION),
    sort_by: str | None = Query(default=None, description=_SORT_BY_DESCRIPTION),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Same as list_audit_log, scoped to a single user's decisions."""

    await get_or_404(user_crud.get_by_email(user_email, db), "User not found")

    response.headers["X-Total-Count"] = str(
        await audit_log_repository.count_for_user(
            user_email, db, action=action, resource_type=resource_type, allowed=allowed
        )
    )
    return await audit_log_repository.get_for_user(
        user_email,
        db,
        limit=limit,
        offset=offset,
        action=action,
        resource_type=resource_type,
        allowed=allowed,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
