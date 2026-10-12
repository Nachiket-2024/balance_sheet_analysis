from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.seed import seed_base_policies, seed_demo_data


@pytest.mark.asyncio
async def test_seed_base_policies_creates_missing_policy_and_skips_existing(mocker):
    db = MagicMock()

    async def sessions():
        yield db

    mocker.patch.object(seed_base_policies.database, "get_session", sessions)
    mocker.patch.object(
        seed_base_policies.policy_repository,
        "get_by_name",
        AsyncMock(side_effect=[None, MagicMock(id=2)]),
    )
    create = mocker.patch.object(seed_base_policies.policy_repository, "create", AsyncMock())

    await seed_base_policies.seed_base_policies()

    create.assert_awaited_once()
    payload = create.await_args.args[0]
    assert payload["name"] == "role_company_viewer"
    assert payload["conditions"] == {}


@pytest.mark.asyncio
async def test_demo_balance_sheet_seed_is_idempotent_and_creates_two_years():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    db.flush = AsyncMock()

    await seed_demo_data._seed_demo_balance_sheets([11], db)

    assert db.add.call_count == 2
    years = [call.args[0].year for call in db.add.call_args_list]
    assert years == [2022, 2023]
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_demo_helpers_return_existing_records_without_creating(mocker):
    db = MagicMock()
    existing_company = MagicMock(id=10)
    mocker.patch.object(seed_demo_data, "get_company_by_ticker", AsyncMock(return_value=existing_company))
    create_company = mocker.patch.object(seed_demo_data, "create_company", AsyncMock())
    assert await seed_demo_data._get_or_create_company("Existing", "EX", None, db) == 10
    create_company.assert_not_awaited()

    existing_policy = MagicMock(id=20)
    mocker.patch.object(seed_demo_data.policy_repository, "get_by_name", AsyncMock(return_value=existing_policy))
    create_policy = mocker.patch.object(seed_demo_data.policy_repository, "create", AsyncMock())
    assert await seed_demo_data._get_or_create_scoped_policy("p", "d", ["x"], "company_id", 1, db) == 20
    create_policy.assert_not_awaited()


@pytest.mark.asyncio
async def test_demo_helpers_create_missing_user_and_scoped_policy(mocker):
    db = MagicMock()
    mocker.patch.object(seed_demo_data.user_crud, "get_by_email", AsyncMock(return_value=None))
    mocker.patch.object(seed_demo_data.password_service, "hash_password", AsyncMock(return_value="hashed"))
    mocker.patch.object(seed_demo_data.user_crud, "create", AsyncMock(return_value=MagicMock(id=31)))

    assert await seed_demo_data._get_or_create_user("new@example.com", "New User", "secret", db) == 31
    user_payload = seed_demo_data.user_crud.create.await_args.args[0]
    assert user_payload["hashed_password"] == "hashed"
    assert user_payload["is_verified"] is True

    mocker.patch.object(seed_demo_data.policy_repository, "get_by_name", AsyncMock(return_value=None))
    create = mocker.patch.object(seed_demo_data.policy_repository, "create", AsyncMock(return_value=MagicMock(id=41)))
    assert await seed_demo_data._get_or_create_scoped_policy("group", "description", ["company:read"], "group_root_id", 7, db) == 41
    payload = create.await_args.args[0]
    assert payload["resource_type"] == "*"
    assert payload["conditions"] == {"resource_attributes": {"group_root_id": 7}}


@pytest.mark.asyncio
async def test_demo_balance_sheet_seed_skips_existing_periods():
    db = MagicMock()
    db.scalar = AsyncMock(side_effect=[100, 101])
    db.flush = AsyncMock()

    await seed_demo_data._seed_demo_balance_sheets([11], db)

    db.add.assert_not_called()
    db.flush.assert_awaited_once()
