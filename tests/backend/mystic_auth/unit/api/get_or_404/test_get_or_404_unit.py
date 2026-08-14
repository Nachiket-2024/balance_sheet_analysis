# tests/backend/mystic_auth/unit/api/get_or_404/test_get_or_404_unit.py
#
# get_or_404 centralizes the "fetch by id/email/name, 404 if missing"
# pattern previously duplicated ~15 times across user_routes/ and the
# pbac_routes/ modules (Phase 6 architecture cleanup) : pinning its two
# behaviors directly guards every route that now depends on it.
import pytest
from backend.mystic_auth.api.get_or_404.get_or_404 import get_or_404
from fastapi import HTTPException


async def _fetch(value):
    return value


@pytest.mark.asyncio
async def test_get_or_404_returns_the_fetched_object_when_present():
    result = await get_or_404(_fetch({"id": 1}), "Not found", "NOT_FOUND")

    assert result == {"id": 1}


@pytest.mark.asyncio
async def test_get_or_404_raises_404_with_the_given_detail_and_code_when_missing():
    with pytest.raises(HTTPException) as exc_info:
        await get_or_404(_fetch(None), "Widget not found", "WIDGET_NOT_FOUND")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Widget not found"
    assert exc_info.value.code == "WIDGET_NOT_FOUND"
