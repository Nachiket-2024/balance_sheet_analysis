from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_repository import audit_log_repository
from ...audit_log.audit_log_schema import AuditLogEntryRead, LoginTrendPoint

# Authentication-only dependency (no permission required), used by
# /security-log/me, where a user inspects their own security events regardless
# of whether they hold security_audit:read.
from ...auth.current_user.current_user_dependency import get_current_user
from ...authorization.dependencies.authorization_dependency import require_authorization
from ...authorization.permissions import Permission
from ...database.connection import database

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

# Admin/system-only dependency, mirroring api/pbac_routes/policy_permissions.py's
# READ_DEPENDENCY pattern.
_READ_DEPENDENCY = Depends(require_authorization(Permission.SECURITY_AUDIT_READ.value, "security_audit"))


_SORT_BY_DESCRIPTION = (
    "Column to sort by: created_at, user_email, event_type, ip_address, or success. "
    "Any other value (including unset) falls back to created_at."
)
_EVENT_TYPE_DESCRIPTION = "Exact match on event_type (see audit_log_service.py's event-type constants)"
_IP_ADDRESS_DESCRIPTION = "Case-insensitive substring match on ip_address"
_SUCCESS_DESCRIPTION = "Exact match on success (true = Success, false = Failed)"


@router.get("/security-log", response_model=list[AuditLogEntryRead])
async def list_security_audit_log(
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Case-insensitive substring match on user_email"),
    event_type: str | None = Query(default=None, description=_EVENT_TYPE_DESCRIPTION),
    ip_address: str | None = Query(default=None, description=_IP_ADDRESS_DESCRIPTION),
    success: bool | None = Query(default=None, description=_SUCCESS_DESCRIPTION),
    sort_by: str | None = Query(default=None, description=_SORT_BY_DESCRIPTION),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: dict = _READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Security events across every user, newest first by default."""
    # X-Total-Count (see list_all_users' identical pattern) lets the
    # frontend render numbered pages without a separate round trip. Computed
    # from the same filters so the page count always matches what's
    # actually being paged through.
    response.headers["X-Total-Count"] = str(
        await audit_log_repository.count(db, search=search, event_type=event_type, ip_address=ip_address, success=success)
    )
    return await audit_log_repository.get_all(
        db,
        limit=limit,
        offset=offset,
        search=search,
        event_type=event_type,
        ip_address=ip_address,
        success=success,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/security-log/login-trend", response_model=list[LoginTrendPoint])
async def get_login_trend(
    days: int = Query(default=14, ge=1, le=90),
    current_user: dict = _READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Daily login success/failure counts across every user, for the Audit
    Log page's trend chart."""
    return await audit_log_repository.get_login_trend(db, days=days)


@router.get("/security-log/me/login-trend", response_model=list[LoginTrendPoint])
async def get_my_login_trend(
    days: int = Query(default=14, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """The caller's own daily login success/failure counts, no
    security_audit:read required - same self-scoped reasoning as
    /security-log/me."""
    return await audit_log_repository.get_login_trend(db, days=days, user_email=current_user["email"])


@router.get("/security-log/me", response_model=list[AuditLogEntryRead])
async def list_my_security_audit_log(
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None, description=_EVENT_TYPE_DESCRIPTION),
    ip_address: str | None = Query(default=None, description=_IP_ADDRESS_DESCRIPTION),
    success: bool | None = Query(default=None, description=_SUCCESS_DESCRIPTION),
    sort_by: str | None = Query(default=None, description=_SORT_BY_DESCRIPTION),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    The caller's own security events, newest first by default. Scoped
    server-side to current_user's email, no security_audit:read permission
    is required since inspecting one's own history isn't a privileged
    operation, and the caller cannot request another user's entries through
    this endpoint.
    """
    response.headers["X-Total-Count"] = str(
        await audit_log_repository.count_for_user(
            current_user["email"], db, event_type=event_type, ip_address=ip_address, success=success
        )
    )
    return await audit_log_repository.get_for_user(
        current_user["email"],
        db,
        limit=limit,
        offset=offset,
        event_type=event_type,
        ip_address=ip_address,
        success=success,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
