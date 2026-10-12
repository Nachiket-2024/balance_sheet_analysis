import asyncio

import pytest

from backend.mystic_auth.auth.security.login_protection_service import (
    login_protection_service,
)


@pytest.mark.asyncio
async def test_real_valkey_allows_only_one_concurrent_protected_action_reservation():
    key = "integration:protected-action:user@example.test"

    results = await asyncio.gather(
        *(login_protection_service.begin_protected_action(key) for _ in range(12))
    )

    assert sum(results) == 1
    await login_protection_service.release_protected_action(key)


@pytest.mark.asyncio
async def test_real_valkey_reservation_can_be_released_and_reacquired():
    key = "integration:protected-action:reacquire@example.test"

    assert await login_protection_service.begin_protected_action(key) is True
    assert await login_protection_service.begin_protected_action(key) is False

    await login_protection_service.release_protected_action(key)

    assert await login_protection_service.begin_protected_action(key) is True
    await login_protection_service.release_protected_action(key)
