# tests/backend/app/companies/test_company_access_boundaries.py
#
# The whole point of this app's access-control design (see
# backend/app/access/scope.py's docstring): a company-scoped policy grants
# exactly one company, a group-scoped policy grants every company under
# that group_root_id, and neither ever leaks a company outside its scope.
# This is the one regression test that must never go red.
import uuid

import pytest
import pytest_asyncio
from backend.app.access.permissions import COMPANY_CREATE, COMPANY_READ, COMPANY_UPDATE
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
                "name": _unique("test_policy_company_scope"),
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
async def _cleanup_companies(created_company_ids):
    yield
    if not created_company_ids:
        return
    async with database.async_session() as session:
        for company_id in created_company_ids:
            company = await session.get(Company, company_id)
            if company:
                await session.delete(company)
        await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_test_policies():
    yield
    async with database.async_session() as session:
        for policy in await policy_repository.get_all(session):
            if policy.name.startswith("test_policy_company_scope"):
                await policy_repository.delete(policy, session)


@pytest.mark.asyncio
async def test_company_scoped_user_sees_only_their_company(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        reliance = await create_company(
            CompanyCreate(name="Reliance Industries", ticker=_unique("RELIANCE")), session
        )
        jio = await create_company(
            CompanyCreate(name="Jio Platforms", ticker=_unique("JIO"), parent_company_id=reliance.id), session
        )
        unrelated = await create_company(CompanyCreate(name="Unrelated Co", ticker=_unique("UNREL")), session)
    created_company_ids.extend([reliance.id, jio.id, unrelated.id])

    ceo_email = _unique("ceo") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, ceo_email, [COMPANY_READ], "company_id", jio.id
    )

    list_resp = await client.get("/companies/")
    assert list_resp.status_code == 200
    returned_ids = {c["id"] for c in list_resp.json()}
    assert returned_ids == {jio.id}

    own_company_resp = await client.get(f"/companies/{jio.id}")
    assert own_company_resp.status_code == 200

    sibling_resp = await client.get(f"/companies/{reliance.id}")
    assert sibling_resp.status_code == 403

    unrelated_resp = await client.get(f"/companies/{unrelated.id}")
    assert unrelated_resp.status_code == 403


@pytest.mark.asyncio
async def test_group_scoped_user_sees_every_company_in_the_group(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        reliance = await create_company(
            CompanyCreate(name="Reliance Industries", ticker=_unique("RELIANCE")), session
        )
        jio = await create_company(
            CompanyCreate(name="Jio Platforms", ticker=_unique("JIO"), parent_company_id=reliance.id), session
        )
        retail = await create_company(
            CompanyCreate(name="Reliance Retail Ventures", ticker=_unique("RRVL"), parent_company_id=reliance.id),
            session,
        )
        unrelated = await create_company(CompanyCreate(name="Unrelated Co", ticker=_unique("UNREL")), session)
    created_company_ids.extend([reliance.id, jio.id, retail.id, unrelated.id])

    exec_email = _unique("groupexec") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, exec_email, [COMPANY_READ], "group_root_id", reliance.id
    )

    list_resp = await client.get("/companies/")
    assert list_resp.status_code == 200
    returned_ids = {c["id"] for c in list_resp.json()}
    assert returned_ids == {reliance.id, jio.id, retail.id}

    for company_id in (reliance.id, jio.id, retail.id):
        resp = await client.get(f"/companies/{company_id}")
        assert resp.status_code == 200

    unrelated_resp = await client.get(f"/companies/{unrelated.id}")
    assert unrelated_resp.status_code == 403


@pytest.mark.asyncio
async def test_user_with_no_matching_policy_sees_nothing(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Some Co", ticker=_unique("SOME")), session)
    created_company_ids.append(company.id)

    # SELF_SERVICE_POLICY_NAME only, no company:read grant at all.
    email = _unique("noaccess") + "@example.com"
    signup_resp = await client.post("/auth/signup", json={"name": "No Access", "email": email, "password": PASSWORD})
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    await client.post("/auth/verify-account", json={"token": token})

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    list_resp = await client.get("/companies/")
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    detail_resp = await client.get(f"/companies/{company.id}")
    assert detail_resp.status_code == 403


@pytest.mark.asyncio
async def test_user_with_create_permission_can_create_a_company(client, created_emails, created_company_ids):
    email = _unique("creator") + "@example.com"
    # Unconditional grant (no resource_attributes): creating a company isn't
    # scoped to an existing resource, see company_routes.py's own comment.
    await _create_verified_user_with_policy(client, created_emails, email, [COMPANY_CREATE], "company_id", -1)
    # Broaden the just-created policy to an unconditional grant so creation
    # (which has nothing to scope against yet) actually succeeds.
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        policy = next(p for p in policies if p.name.startswith("test_policy_company_scope"))
        await policy_repository.update(policy, {"conditions": None}, session)

    ticker = _unique("NEWCO")
    resp = await client.post("/companies/", json={"name": "New Co", "ticker": ticker})

    assert resp.status_code == 201
    body = resp.json()
    assert body["ticker"] == ticker
    assert body["group_root_id"] == body["id"]  # root company: its own group
    created_company_ids.append(body["id"])


@pytest.mark.asyncio
async def test_ticker_lookup_requires_create_permission(client, created_emails, created_company_ids):
    email = _unique("nolookup") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, [COMPANY_READ], "company_id", -1)

    resp = await client.get("/companies/lookup/AAPL")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ticker_lookup_returns_the_yfinance_name(client, created_emails, created_company_ids, mocker):
    mocker.patch(
        "backend.app.companies.company_crud._lookup_company_name_by_ticker_sync",
        return_value="Apple Inc.",
    )

    email = _unique("lookup") + "@example.com"
    # Unconditional grant, same reasoning as test_user_with_create_permission_can_create_a_company:
    # require_authorization is called with no resource=, so a conditional
    # (resource-scoped) policy would never match here.
    await _create_verified_user_with_policy(client, created_emails, email, [COMPANY_CREATE], "company_id", -1)
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        policy = next(p for p in policies if p.name.startswith("test_policy_company_scope"))
        await policy_repository.update(policy, {"conditions": None}, session)

    resp = await client.get("/companies/lookup/AAPL")
    assert resp.status_code == 200
    assert resp.json() == {"ticker": "AAPL", "name": "Apple Inc."}


@pytest.mark.asyncio
async def test_ticker_lookup_yfinance_failure_is_a_clean_502(client, created_emails, created_company_ids, mocker):
    mocker.patch(
        "backend.app.companies.company_crud.yf.Ticker",
        side_effect=ConnectionError("network unreachable"),
    )

    email = _unique("lookupfail") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, [COMPANY_CREATE], "company_id", -1)
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        policy = next(p for p in policies if p.name.startswith("test_policy_company_scope"))
        await policy_repository.update(policy, {"conditions": None}, session)

    resp = await client.get("/companies/lookup/AAPL")
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_creating_a_company_with_a_duplicate_ticker_is_a_clean_400(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        existing = await create_company(CompanyCreate(name="Existing Co", ticker=_unique("DUPE")), session)
    created_company_ids.append(existing.id)

    email = _unique("creator2") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, [COMPANY_CREATE], "company_id", -1)
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        policy = next(p for p in policies if p.name.startswith("test_policy_company_scope"))
        await policy_repository.update(policy, {"conditions": None}, session)

    resp = await client.post("/companies/", json={"name": "Duplicate Co", "ticker": existing.ticker})

    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_company_scoped_user_can_update_their_own_company(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Old Name", ticker=_unique("OLD")), session)
    created_company_ids.append(company.id)

    email = _unique("updater") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_UPDATE], "company_id", company.id
    )

    resp = await client.patch(f"/companies/{company.id}", json={"name": "New Name"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New Name"
    assert body["ticker"] == company.ticker  # untouched field left as-is


@pytest.mark.asyncio
async def test_company_scoped_user_cannot_update_a_company_outside_scope(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        own_company = await create_company(CompanyCreate(name="Mine", ticker=_unique("MINE")), session)
        other_company = await create_company(CompanyCreate(name="Not Mine", ticker=_unique("NOTMINE")), session)
    created_company_ids.extend([own_company.id, other_company.id])

    email = _unique("updater2") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_UPDATE], "company_id", own_company.id
    )

    resp = await client.patch(f"/companies/{other_company.id}", json={"name": "Hijacked"})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_updating_a_company_to_a_duplicate_ticker_is_a_clean_400(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        existing = await create_company(CompanyCreate(name="Existing Co", ticker=_unique("DUPE2")), session)
        company = await create_company(CompanyCreate(name="Some Co", ticker=_unique("SOME2")), session)
    created_company_ids.extend([existing.id, company.id])

    email = _unique("updater3") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, [COMPANY_UPDATE], "company_id", company.id)

    resp = await client.patch(f"/companies/{company.id}", json={"ticker": existing.ticker})

    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a_company_cannot_be_set_as_its_own_parent(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Self Ref Co", ticker=_unique("SELFREF")), session)
    created_company_ids.append(company.id)

    email = _unique("updater4") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, [COMPANY_UPDATE], "company_id", company.id)

    resp = await client.patch(f"/companies/{company.id}", json={"parent_company_id": company.id})

    assert resp.status_code == 400
    assert "own parent" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reparenting_a_company_with_subsidiaries_is_a_clean_400(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        parent = await create_company(CompanyCreate(name="Parent Co", ticker=_unique("PARENT")), session)
        child = await create_company(
            CompanyCreate(name="Child Co", ticker=_unique("CHILD"), parent_company_id=parent.id), session
        )
        new_parent = await create_company(CompanyCreate(name="New Parent Co", ticker=_unique("NEWPARENT")), session)
    created_company_ids.extend([parent.id, child.id, new_parent.id])

    email = _unique("updater5") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, [COMPANY_UPDATE], "company_id", parent.id)

    resp = await client.patch(f"/companies/{parent.id}", json={"parent_company_id": new_parent.id})

    assert resp.status_code == 400
    assert "subsidiary" in resp.json()["detail"]
