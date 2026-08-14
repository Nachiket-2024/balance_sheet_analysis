from collections.abc import Awaitable

from fastapi import status

from ...core.errors import AppError


async def get_or_404[T](fetch: Awaitable[T | None], not_found_detail: str, code: str) -> T:
    """
    Awaits a repository lookup coroutine and raises AppError(404) if it
    returns None. Centralizes the `x = await repo.get_by_Y(...); if not x: raise
    AppError(404, ...)` pattern that used to be repeated at every entity
    lookup across user_routes/ and the pbac_routes/ modules.
    """
    obj = await fetch
    if not obj:
        raise AppError(status_code=status.HTTP_404_NOT_FOUND, code=code, detail=not_found_detail)
    return obj
