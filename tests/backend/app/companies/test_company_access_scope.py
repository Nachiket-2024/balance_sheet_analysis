"""Company list and detail authorization scope integration tests."""

import pytest

from backend.app.access.permissions import COMPANY_READ
from backend.app.companies.company_crud import create_company
from backend.app.companies.company_schema import CompanyCreate
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.valkey.client import valkey_client
from tests.backend.app.companies.company_access_helpers import (
    PASSWORD,
    _create_verified_user_with_policy,
    _unique,
)


@pytest.mark.asyncio
async def test_company_scoped_user_sees_only_their_company(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        microsoft = await create_company(
            CompanyCreate(name="Microsoft Corporation", ticker=_unique("MSFT")), session
        )
        github = await create_company(
            CompanyCreate(
                name="GitHub, Inc.",
                ticker=_unique("GITHUB"),
                parent_company_id=microsoft.id,
            ),
            session,
        )
        unrelated = await create_company(
            CompanyCreate(name="Unrelated Co", ticker=_unique("UNREL")), session
        )
    created_company_ids.extend([microsoft.id, github.id, unrelated.id])

    ceo_email = _unique("ceo") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, ceo_email, [COMPANY_READ], "company_id", github.id
    )

    list_resp = await client.get("/companies/")
    assert list_resp.status_code == 200
    returned_ids = {c["id"] for c in list_resp.json()}
    assert returned_ids == {github.id}

    own_company_resp = await client.get(f"/companies/{github.id}")
    assert own_company_resp.status_code == 200

    sibling_resp = await client.get(f"/companies/{microsoft.id}")
    assert sibling_resp.status_code == 403

    unrelated_resp = await client.get(f"/companies/{unrelated.id}")
    assert unrelated_resp.status_code == 403


@pytest.mark.asyncio
async def test_group_scoped_user_sees_every_company_in_the_group(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        microsoft = await create_company(
            CompanyCreate(name="Microsoft Corporation", ticker=_unique("MSFT")), session
        )
        github = await create_company(
            CompanyCreate(
                name="GitHub, Inc.",
                ticker=_unique("GITHUB"),
                parent_company_id=microsoft.id,
            ),
            session,
        )
        linkedin = await create_company(
            CompanyCreate(
                name="LinkedIn Corporation",
                ticker=_unique("LINKEDIN"),
                parent_company_id=microsoft.id,
            ),
            session,
        )
        unrelated = await create_company(
            CompanyCreate(name="Unrelated Co", ticker=_unique("UNREL")), session
        )
    created_company_ids.extend([microsoft.id, github.id, linkedin.id, unrelated.id])

    exec_email = _unique("groupexec") + "@example.com"
    await _create_verified_user_with_policy(
        client,
        created_emails,
        exec_email,
        [COMPANY_READ],
        "group_root_id",
        microsoft.id,
    )

    list_resp = await client.get("/companies/")
    assert list_resp.status_code == 200
    returned_ids = {c["id"] for c in list_resp.json()}
    assert returned_ids == {microsoft.id, github.id, linkedin.id}

    for company_id in (microsoft.id, github.id, linkedin.id):
        resp = await client.get(f"/companies/{company_id}")
        assert resp.status_code == 200

    unrelated_resp = await client.get(f"/companies/{unrelated.id}")
    assert unrelated_resp.status_code == 403


@pytest.mark.asyncio
async def test_user_with_no_matching_policy_sees_nothing(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        company = await create_company(
            CompanyCreate(name="Some Co", ticker=_unique("SOME")), session
        )
    created_company_ids.append(company.id)

    # SELF_SERVICE_POLICY_NAME only, no company:read grant at all.
    email = _unique("noaccess") + "@example.com"
    signup_resp = await client.post(
        "/auth/signup", json={"name": "No Access", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    await client.post("/auth/verify-account", json={"token": token})

    login_resp = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200

    list_resp = await client.get("/companies/")
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    detail_resp = await client.get(f"/companies/{company.id}")
    assert detail_resp.status_code == 403
