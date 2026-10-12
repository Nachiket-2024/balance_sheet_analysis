"""Company update authorization and hierarchy boundary integration tests."""

import pytest

from backend.app.access.permissions import COMPANY_UPDATE
from backend.app.companies.company_crud import create_company
from backend.app.companies.company_schema import CompanyCreate
from backend.mystic_auth.database.connection import database
from tests.backend.app.companies.company_access_helpers import (
    _create_verified_user_with_policy,
    _unique,
)


@pytest.mark.asyncio
async def test_company_scoped_user_can_update_their_own_company(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        company = await create_company(
            CompanyCreate(name="Old Name", ticker=_unique("OLD")), session
        )
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
async def test_company_scoped_user_cannot_update_a_company_outside_scope(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        own_company = await create_company(
            CompanyCreate(name="Mine", ticker=_unique("MINE")), session
        )
        other_company = await create_company(
            CompanyCreate(name="Not Mine", ticker=_unique("NOTMINE")), session
        )
    created_company_ids.extend([own_company.id, other_company.id])

    email = _unique("updater2") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_UPDATE], "company_id", own_company.id
    )

    resp = await client.patch(
        f"/companies/{other_company.id}", json={"name": "Hijacked"}
    )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_updating_a_company_to_a_duplicate_ticker_is_a_clean_400(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        existing = await create_company(
            CompanyCreate(name="Existing Co", ticker=_unique("DUPE2")), session
        )
        company = await create_company(
            CompanyCreate(name="Some Co", ticker=_unique("SOME2")), session
        )
    created_company_ids.extend([existing.id, company.id])

    email = _unique("updater3") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_UPDATE], "company_id", company.id
    )

    resp = await client.patch(
        f"/companies/{company.id}", json={"ticker": existing.ticker}
    )

    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a_company_cannot_be_set_as_its_own_parent(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        company = await create_company(
            CompanyCreate(name="Self Ref Co", ticker=_unique("SELFREF")), session
        )
    created_company_ids.append(company.id)

    email = _unique("updater4") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_UPDATE], "company_id", company.id
    )

    resp = await client.patch(
        f"/companies/{company.id}", json={"parent_company_id": company.id}
    )

    assert resp.status_code == 400
    assert "own parent" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reparenting_a_company_with_subsidiaries_is_a_clean_400(
    client, created_emails, created_company_ids
):
    async with database.async_session() as session:
        parent = await create_company(
            CompanyCreate(name="Parent Co", ticker=_unique("PARENT")), session
        )
        child = await create_company(
            CompanyCreate(
                name="Child Co", ticker=_unique("CHILD"), parent_company_id=parent.id
            ),
            session,
        )
        new_parent = await create_company(
            CompanyCreate(name="New Parent Co", ticker=_unique("NEWPARENT")), session
        )
    created_company_ids.extend([parent.id, child.id, new_parent.id])

    email = _unique("updater5") + "@example.com"
    await _create_verified_user_with_policy(
        client, created_emails, email, [COMPANY_UPDATE], "company_id", parent.id
    )

    resp = await client.patch(
        f"/companies/{parent.id}", json={"parent_company_id": new_parent.id}
    )

    assert resp.status_code == 400
    assert "subsidiary" in resp.json()["detail"]
