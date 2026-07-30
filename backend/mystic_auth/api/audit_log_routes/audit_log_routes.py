from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_repository import audit_log_repository
from ...audit_log.audit_log_schema import AuditLogEntryRead

# Authentication-only dependency (no permission required), used by
# /security-log/me, where a user inspects their own security events regardless
# of whether they hold security_audit:read.
from ...auth.current_user.current_user_dependency import get_current_user
from ...authorization.dependencies.authorization_dependency import require_authorization
from ...authorization.permissions import Permission
from ...database.connection import database

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

# Admin/system-only dependency, mirroring api/pbac_routes/policy_shared.py's
# READ_DEPENDENCY pattern.
_READ_DEPENDENCY = Depends(require_authorization(Permission.SECURITY_AUDIT_READ.value, "security_audit"))


@router.get("/security-log", response_model=list[AuditLogEntryRead])
async def list_security_audit_log(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = _READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Recent security events across every user, newest first."""
    return await audit_log_repository.get_all(db, limit=limit, offset=offset)


@router.get("/security-log/me", response_model=list[AuditLogEntryRead])
async def list_my_security_audit_log(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    The caller's own security events, newest first. Scoped server-side to
    current_user's email, no security_audit:read permission is required
    since inspecting one's own history isn't a privileged operation, and the
    caller cannot request another user's entries through this endpoint.
    """
    return await audit_log_repository.get_for_user(current_user["email"], db, limit=limit, offset=offset)
