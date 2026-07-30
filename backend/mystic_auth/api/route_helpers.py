from collections.abc import Awaitable
from typing import TypeVar

from fastapi import HTTPException, status

T = TypeVar("T")


async def get_or_404(fetch: Awaitable[T | None], not_found_detail: str) -> T:
    """
    Awaits a repository lookup coroutine and raises HTTPException(404) if it
    returns None. Centralizes the `x = await repo.get_by_Y(...); if not x: raise
    HTTPException(404, ...)` pattern that used to be repeated at every entity
    lookup across user_routes.py and the pbac_routes/ modules.
    """
    obj = await fetch
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    return obj
