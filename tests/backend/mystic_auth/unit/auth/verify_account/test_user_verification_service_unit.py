"""Verification idempotency and default-policy assignment tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.verify_account.user_verification_service import (
    UserVerificationService,
)

MODULE = "backend.mystic_auth.auth.verify_account.user_verification_service"


@pytest.mark.asyncio
async def test_missing_user_returns_false_without_update_or_policy_assignment(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=None)
    update = mocker.patch(f"{MODULE}.user_crud.update_by_email", new_callable=AsyncMock)
    assign = mocker.patch(f"{MODULE}.assign_app_default_policies", new_callable=AsyncMock)

    assert await UserVerificationService.mark_user_verified("missing@example.com", object()) is False
    update.assert_not_awaited()
    assign.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_verified_user_is_idempotent(mocker):
    mocker.patch(
        f"{MODULE}.user_crud.get_by_email",
        new_callable=AsyncMock,
        return_value=SimpleNamespace(id=1, is_verified=True),
    )
    update = mocker.patch(f"{MODULE}.user_crud.update_by_email", new_callable=AsyncMock)
    assign = mocker.patch(f"{MODULE}.assign_app_default_policies", new_callable=AsyncMock)

    assert await UserVerificationService.mark_user_verified("user@example.com", object()) is False
    update.assert_not_awaited()
    assign.assert_not_awaited()


@pytest.mark.asyncio
async def test_unverified_user_is_updated_then_gets_default_policies(mocker):
    user = SimpleNamespace(id=42, is_verified=False)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=user)
    update = mocker.patch(f"{MODULE}.user_crud.update_by_email", new_callable=AsyncMock)
    assign = mocker.patch(f"{MODULE}.assign_app_default_policies", new_callable=AsyncMock)

    assert await UserVerificationService.mark_user_verified("user@example.com", "db") is True
    update.assert_awaited_once_with("user@example.com", {"is_verified": True}, "db")
    assign.assert_awaited_once_with(42, "db")


@pytest.mark.asyncio
async def test_policy_assignment_failure_is_fail_closed_to_caller(mocker):
    user = SimpleNamespace(id=42, is_verified=False)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=user)
    mocker.patch(f"{MODULE}.user_crud.update_by_email", new_callable=AsyncMock)
    mocker.patch(
        f"{MODULE}.assign_app_default_policies",
        new_callable=AsyncMock,
        side_effect=RuntimeError("database unavailable"),
    )

    assert await UserVerificationService.mark_user_verified("user@example.com", "db") is False
