# tests/backend/app/companies/test_company_pagination.py
#
# GET /companies/ moved from "load the whole backend-scoped list in one shot"
# to real server-side pagination/search/filter/sort (see company_crud.py's
# list_companies_in_scope), since an admin-scoped user can see every company
# in the system, unlike e.g. mystic_auth's own PoliciesPage. This covers the
# paging mechanics themselves, plus the "root"/"subsidiary" hierarchy filter,
# the parent_name join, and GET /companies/stats. The older
# access-boundary tests exercise.
import uuid

import pytest
import pytest_asyncio
from backend.app.access.permissions import COMPANY_READ
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
                "name": _unique("test_policy_company_pagination"),
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
            if policy.name.startswith("test_policy_company_pagination"):
                await policy_repository.delete(policy, session)


@pytest.mark.asyncio
async def test_list_companies_paginates_and_reports_total_count(client, created_emails, created_company_ids):
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
    created_company_ids.extend([reliance.id, jio.id, retail.id])

    exec_email = _unique("groupexec") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, exec_email, [COMPANY_READ], "group_root_id", reliance.id
    )

    page1 = await client.get("/companies/", params={"limit": 2, "offset": 0, "sort_by": "name", "sort_dir": "asc"})
    assert page1.status_code == 200
    assert page1.headers["X-Total-Count"] == "3"
    assert len(page1.json()) == 2

    page2 = await client.get("/companies/", params={"limit": 2, "offset": 2, "sort_by": "name", "sort_dir": "asc"})
    assert page2.status_code == 200
    assert page2.headers["X-Total-Count"] == "3"
    assert len(page2.json()) == 1

    all_ids_across_pages = {c["id"] for c in page1.json()} | {c["id"] for c in page2.json()}
    assert all_ids_across_pages == {reliance.id, jio.id, retail.id}


@pytest.mark.asyncio
async def test_list_companies_includes_parent_name(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        reliance = await create_company(
            CompanyCreate(name="Reliance Industries", ticker=_unique("RELIANCE")), session
        )
        jio = await create_company(
            CompanyCreate(name="Jio Platforms", ticker=_unique("JIO"), parent_company_id=reliance.id), session
        )
    created_company_ids.extend([reliance.id, jio.id])

    exec_email = _unique("groupexec") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, exec_email, [COMPANY_READ], "group_root_id", reliance.id
    )

    resp = await client.get("/companies/")
    assert resp.status_code == 200
    by_id = {c["id"]: c for c in resp.json()}
    assert by_id[reliance.id]["parent_name"] is None
    assert by_id[jio.id]["parent_name"] == "Reliance Industries"


@pytest.mark.asyncio
async def test_list_companies_hierarchy_filter(client, created_emails, created_company_ids):
    async with database.async_session() as session:
        reliance = await create_company(
            CompanyCreate(name="Reliance Industries", ticker=_unique("RELIANCE")), session
        )
        jio = await create_company(
            CompanyCreate(name="Jio Platforms", ticker=_unique("JIO"), parent_company_id=reliance.id), session
        )
    created_company_ids.extend([reliance.id, jio.id])

    exec_email = _unique("groupexec") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, exec_email, [COMPANY_READ], "group_root_id", reliance.id
    )

    roots = await client.get("/companies/", params={"hierarchy": "root"})
    assert roots.status_code == 200
    assert {c["id"] for c in roots.json()} == {reliance.id}

    subsidiaries = await client.get("/companies/", params={"hierarchy": "subsidiary"})
    assert subsidiaries.status_code == 200
    assert {c["id"] for c in subsidiaries.json()} == {jio.id}


@pytest.mark.asyncio
async def test_company_stats_scoped_to_caller(client, created_emails, created_company_ids):
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

    resp = await client.get("/companies/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats == {"total": 3, "group_roots": 1, "subsidiaries": 2}
