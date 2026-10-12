from collections.abc import Awaitable

from fastapi import status

from ...core.errors import AppError


async def get_or_404[T](fetch: Awaitable[T | None], not_found_detail: str, code: str) -> T:
    """
    Awaits a repository lookup and raises AppError(404) if it returns None.
    Centralizes the "fetch, then 404 if missing" pattern used at every
    entity lookup in user_routes/ and pbac_routes/.
    """
    obj = await fetch
    if not obj:
        raise AppError(status_code=status.HTTP_404_NOT_FOUND, code=code, detail=not_found_detail)
    return obj
