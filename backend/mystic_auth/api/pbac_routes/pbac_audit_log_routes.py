from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

# Authentication-only dependency (no permission required) : used by
# /audit-log/me, where a user inspects their own decisions regardless of
# whether they hold policies:read
from ...auth.current_user.current_user_dependency import get_current_user
from ...authorization.repositories.audit_log_repository import audit_log_repository
from ...authorization.schemas.audit_log_schema import AuditLogEntryRead
from ...database.connection import database
from ...user_crud.user_crud_collector import user_crud
from ..route_helpers import get_or_404
from .policy_shared import READ_DEPENDENCY

router = APIRouter(prefix="/authorization", tags=["Authorization"])


@router.get("/audit-log", response_model=list[AuditLogEntryRead])
async def list_audit_log(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Recent authorization decisions across every user, newest first.
    Every real authorize()/require() call anywhere in the app writes one of
    these rows automatically (see AuthorizationService._log_decision) :
    nothing needs to opt in."""
    return await audit_log_repository.get_all(db, limit=limit, offset=offset)


@router.get("/audit-log/me", response_model=list[AuditLogEntryRead])
async def list_my_audit_log(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    The caller's own authorization decisions, newest first. No
    policies:read (or any other) permission required, since a user
    inspecting their own authorization history is not a privileged
    operation. Scoped server-side to current_user's email : the caller
    cannot request another user's entries through this endpoint (see
    list_audit_log_for_user for that, which does require policies:read).
    """
    return await audit_log_repository.get_for_user(current_user["email"], db, limit=limit, offset=offset)


@router.get("/audit-log/users/{user_email}", response_model=list[AuditLogEntryRead])
async def list_audit_log_for_user(
    user_email: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Same as list_audit_log, scoped to a single user's decisions."""

    await get_or_404(user_crud.get_by_email(user_email, db), "User not found")

    return await audit_log_repository.get_for_user(user_email, db, limit=limit, offset=offset)
