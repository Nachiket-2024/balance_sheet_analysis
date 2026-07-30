# tests/backend/app/balance_sheets/test_balance_sheet_access_boundaries.py
#
# Balance-sheet reads/imports/deletes are checked against the SAME
# company_id/group_root_id scoping as companies themselves (see
# access/scope.py's resource_scope_dict). This proves that holds for a
# resource type other than "company", not just company reads.
import uuid

import pytest
import pytest_asyncio
from backend.app.access.permissions import BALANCE_SHEET_DELETE, BALANCE_SHEET_IMPORT, BALANCE_SHEET_READ
from backend.app.balance_sheets.balance_sheet_model import BalanceSheet
from backend.app.companies.company_crud import create_company
from backend.app.companies.company_model import Company
from backend.app.companies.company_schema import CompanyCreate
from backend.mystic_auth.auth.verify_account.account_verification_service import account_verification_service
from backend.mystic_auth.authorization.policies.default_policies import SELF_SERVICE_POLICY_NAME
from backend.mystic_auth.authorization.repositories.policy_repository import policy_repository
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.redis.client import redis_client
from backend.mystic_auth.user_crud.user_crud_collector import user_crud

PASSWORD = "StrongPass123!"


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


async def _create_verified_user_with_policy(client, created_emails, email, actions, condition_key, condition_value):
    signup_resp = await client.post("/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD})
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)

        self_service = await policy_repository.get_by_name(SELF_SERVICE_POLICY_NAME, session)
        await policy_repository.assign_policy_to_user(user.id, self_service.id, session, assigned_by="test")

        policy = await policy_repository.create(
            {
                "name": _unique("test_policy_bs_scope"),
                "actions": actions,
                "resource_type": "*",
                "conditions": {"resource_attributes": {condition_key: condition_value}},
            },
            session,
        )
        await policy_repository.assign_policy_to_user(user.id, policy.id, session, assigned_by="test")

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200
    return client


@pytest.fixture
def created_company_ids():
    ids: list[int] = []
    yield ids


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(created_company_ids):
    yield
    async with database.async_session() as session:
        for company_id in created_company_ids:
            await session.execute(BalanceSheet.__table__.delete().where(BalanceSheet.company_id == company_id))
            company = await session.get(Company, company_id)
            if company:
                await session.delete(company)
        await session.commit()
        for policy in await policy_repository.get_all(session):
            if policy.name.startswith("test_policy_bs_scope"):
                await policy_repository.delete(policy, session)


@pytest.mark.asyncio
async def test_reader_sees_only_their_companys_balance_sheets(mocker, client, created_emails, created_company_ids):
    async with database.async_session() as session:
        mine = await create_company(CompanyCreate(name="Mine Co", ticker=_unique("MINE")), session)
        other = await create_company(CompanyCreate(name="Other Co", ticker=_unique("OTHR")), session)
    created_company_ids.extend([mine.id, other.id])

    async with database.async_session() as session:
        session.add(BalanceSheet(company_id=mine.id, year=2023, total_assets=100.0))
        session.add(BalanceSheet(company_id=other.id, year=2023, total_assets=999.0))
        await session.commit()

    email = _unique("reader") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, [BALANCE_SHEET_READ], "company_id", mine.id)

    ok_resp = await client.get(f"/balance-sheets/company/{mine.id}")
    assert ok_resp.status_code == 200
    assert len(ok_resp.json()) == 1
    assert ok_resp.json()[0]["total_assets"] == 100.0

    forbidden_resp = await client.get(f"/balance-sheets/company/{other.id}")
    assert forbidden_resp.status_code == 403

    forbidden_year_resp = await client.get(f"/balance-sheets/{other.id}/2023")
    assert forbidden_year_resp.status_code == 403


@pytest.mark.asyncio
async def test_reader_without_import_permission_cannot_import(mocker, client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="ReadOnly Co", ticker=_unique("RO")), session)
    created_company_ids.append(company.id)

    email = _unique("readonly") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [BALANCE_SHEET_READ], "company_id", company.id
    )

    # Not mocking yfinance here, since a 403 (authorization) must come back before
    # any attempt to reach the network, proving the PBAC check runs first.
    resp = await client.post(f"/balance-sheets/{company.id}/2023")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_importer_can_import_and_scoped_out_user_cannot(mocker, client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Importable Co", ticker=_unique("IMPT")), session)
    created_company_ids.append(company.id)

    mocker.patch(
        "backend.app.balance_sheets.balance_sheet_crud._fetch_balance_sheet_row_sync",
        return_value={"total_assets": 42.0},
    )

    importer_email = _unique("importer") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, importer_email, [BALANCE_SHEET_IMPORT], "company_id", company.id
    )
    resp = await client.post(f"/balance-sheets/{company.id}/2023")
    assert resp.status_code == 201
    assert resp.json()["total_assets"] == 42.0

    outsider_email = _unique("outsider") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, outsider_email, [BALANCE_SHEET_IMPORT], "company_id", company.id + 1_000_000
    )
    resp = await client.post(f"/balance-sheets/{company.id}/2024")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reader_can_get_a_single_fiscal_year(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Single Year Co", ticker=_unique("SY")), session)
        session.add(BalanceSheet(company_id=company.id, year=2022, total_assets=555.0))
        await session.commit()
    created_company_ids.append(company.id)

    email = _unique("singleyear") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, [BALANCE_SHEET_READ], "company_id", company.id)

    resp = await client.get(f"/balance-sheets/{company.id}/2022")
    assert resp.status_code == 200
    assert resp.json()["total_assets"] == 555.0

    missing_resp = await client.get(f"/balance-sheets/{company.id}/1999")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_deleter_can_delete_and_scoped_out_user_cannot(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Deletable Co", ticker=_unique("DEL")), session)
        session.add(BalanceSheet(company_id=company.id, year=2021, total_assets=1.0))
        session.add(BalanceSheet(company_id=company.id, year=2022, total_assets=2.0))
        await session.commit()
    created_company_ids.append(company.id)

    outsider_email = _unique("delout") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, outsider_email, [BALANCE_SHEET_DELETE], "company_id", company.id + 1_000_000
    )
    forbidden_resp = await client.delete(f"/balance-sheets/{company.id}/2021")
    assert forbidden_resp.status_code == 403

    deleter_email = _unique("deleter") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, deleter_email, [BALANCE_SHEET_DELETE], "company_id", company.id
    )
    ok_resp = await client.delete(f"/balance-sheets/{company.id}/2022")
    assert ok_resp.status_code == 204

    missing_resp = await client.delete(f"/balance-sheets/{company.id}/2022")
    assert missing_resp.status_code == 404
