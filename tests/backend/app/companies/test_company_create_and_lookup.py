"""Company creation and ticker lookup authorization integration tests."""

import pytest

from backend.app.access.permissions import COMPANY_CREATE, COMPANY_READ
from backend.app.companies.company_crud import create_company
from backend.app.companies.company_schema import CompanyCreate
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from tests.backend.app.companies.company_access_helpers import (
    _create_verified_user_with_policy,
    _unique,
)


@pytest.mark.asyncio
async def test_user_with_create_permission_can_create_a_company(
    client, created_emails, created_company_ids
):
    email = _unique("creator") + "@example.com"
    # Unconditional grant (no resource_attributes): creating a company isn't
    # scoped to an existing resource, see company_routes.py's own comment.
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_CREATE], "company_id", -1
    )
    # Broaden the just-created policy to an unconditional grant so creation
    # (which has nothing to scope against yet) actually succeeds.
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        policy = next(
            p for p in policies if p.name.startswith("test_policy_company_scope")
        )
        await policy_repository.update(policy, {"conditions": None}, session)

    ticker = _unique("NEWCO")
    resp = await client.post("/companies/", json={"name": "New Co", "ticker": ticker})

    assert resp.status_code == 201
    body = resp.json()
    assert body["ticker"] == ticker
    assert body["group_root_id"] == body["id"]  # root company: its own group
    created_company_ids.append(body["id"])


@pytest.mark.asyncio
async def test_ticker_lookup_requires_create_permission(
    client, created_emails, created_company_ids
):
    email = _unique("nolookup") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_READ], "company_id", -1
    )

    resp = await client.get("/companies/lookup/AAPL")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ticker_lookup_returns_the_yfinance_name(
    client, created_emails, created_company_ids, mocker
):
    mocker.patch(
        "backend.app.companies.company_crud._lookup_company_name_by_ticker_sync",
        return_value="Apple Inc.",
    )

    email = _unique("lookup") + "@example.com"
    # Unconditional grant, same reasoning as test_user_with_create_permission_can_create_a_company:
    # require_authorization is called with no resource=, so a conditional
    # (resource-scoped) policy would never match here.
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_CREATE], "company_id", -1
    )
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        policy = next(
            p for p in policies if p.name.startswith("test_policy_company_scope")
        )
        await policy_repository.update(policy, {"conditions": None}, session)

    resp = await client.get("/companies/lookup/AAPL")
    assert resp.status_code == 200
    assert resp.json() == {"ticker": "AAPL", "name": "Apple Inc."}


@pytest.mark.asyncio
async def test_ticker_lookup_yfinance_failure_is_a_clean_502(
    client, created_emails, created_company_ids, mocker
):
    mocker.patch(
        "backend.app.companies.company_crud.yf.Ticker",
        side_effect=ConnectionError("network unreachable"),
    )

    email = _unique("lookupfail") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_CREATE], "company_id", -1
    )
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        policy = next(
            p for p in policies if p.name.startswith("test_policy_company_scope")
        )
        await policy_repository.update(policy, {"conditions": None}, session)

    resp = await client.get("/companies/lookup/AAPL")
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_creating_a_company_with_a_duplicate_ticker_is_a_clean_400(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        existing = await create_company(
            CompanyCreate(name="Existing Co", ticker=_unique("DUPE")), session
        )
    created_company_ids.append(existing.id)

    email = _unique("creator2") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_CREATE], "company_id", -1
    )
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        policy = next(
            p for p in policies if p.name.startswith("test_policy_company_scope")
        )
        await policy_repository.update(policy, {"conditions": None}, session)

    resp = await client.post(
        "/companies/", json={"name": "Duplicate Co", "ticker": existing.ticker}
    )

    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]
