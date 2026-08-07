import asyncio

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...authorization.dependencies.authorization_dependency import require_authorization

# PBAC action vocabulary and policy-based authorization. Replaces the removed
# static role-permission helpers.
from ...authorization.permissions import Permission
from ...database.connection import database
from ...user_crud.user_crud_collector import UserStatus, user_crud
from ...user_table.user_model import UserRole
from ...user_table.user_schema import UserRead, UserStatsRead

# Read-only management views over the whole user table. Split out of the former
# user_management_routes.py alongside user_management_update_routes.py (field
# updates) and user_lifecycle_routes.py (account state transitions), mirroring
# api/pbac_routes/'s existing split-by-operation-type precedent.
# main.py registers this router after self-service routes so /{user_email}
# cannot shadow /users/me or /users/stats.
router = APIRouter(prefix="/users", tags=["Users"])

_RESOURCE_TYPE = "users"


@router.get("/stats", response_model=UserStatsRead)
async def get_user_stats(
    current_user: dict = Depends(require_authorization(Permission.USERS_LIST_ALL.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session),
):
    """Same permission as the list itself (users:list_all): this is purely
    a different view of that same data, not a separate resource. Four
    independent counts, run concurrently rather than one query each awaited
    in turn."""
    total, verified, unverified, inactive = await asyncio.gather(
        user_crud.count(db),
        user_crud.count(db, is_verified=True),
        user_crud.count(db, is_verified=False),
        user_crud.count(db, status="inactive"),
    )
    return UserStatsRead(total=total, verified=verified, unverified=unverified, inactive=inactive)


@router.get("/", response_model=list[UserRead])
async def list_all_users(
    response: Response,
    # Keep the historical "all users" default for API callers. The frontend
    # passes its own explicit limit and offset.
    limit: int = Query(default=1000, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Case-insensitive substring match on name or email"),
    role: UserRole | None = Query(default=None, description="Exact match on role"),
    is_verified: bool | None = Query(default=None, description="Exact match on is_verified"),
    status: UserStatus | None = Query(
        default=None, description="One of: active, inactive, deleted (see UsersPage.tsx's Status badge)"
    ),
    sort_by: str | None = Query(
        default=None,
        description="Column to sort by: name, email, role, is_verified, or created_at. "
        "Any other value (including unset) falls back to id.",
    ),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(require_authorization(Permission.USERS_LIST_ALL.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    # X-Total-Count (not part of the response body, response_model stays
    # list[UserRead]) lets the frontend render numbered pages without a
    # separate round trip: computed from the same filters so the page count
    # always matches what's actually being paged through.
    total = await user_crud.count(db, search=search, role=role, is_verified=is_verified, status=status)
    response.headers["X-Total-Count"] = str(total)
    return await user_crud.get_all(
        db,
        limit=limit,
        offset=offset,
        search=search,
        role=role,
        is_verified=is_verified,
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
