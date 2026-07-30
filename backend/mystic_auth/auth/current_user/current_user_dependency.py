from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.connection import database
from .current_user_handler import current_user_handler


async def get_current_user(
    access_token: str = Cookie(None),
    db: AsyncSession = Depends(database.get_session),
) -> dict:
    """
    Shared FastAPI dependency that authenticates the caller from their
    access_token cookie and returns their user info dict (name, email,
    role, permissions, has_password), or raises 401/403 via
    current_user_handler.

    Centralized here, rather than redefined per router, so every router
    authenticates through the exact same path, and so the authorization
    layer (authorization.permission_checker.require_permission) has a
    single canonical dependency to build permission checks on top of.
    Authentication (who is calling) and authorization (what they're allowed
    to do) are kept as separate concerns: this module only answers the
    former.
    """
    return await current_user_handler.get_current_user(access_token, db)
