"""Shared fixtures for company access boundary tests."""

import pytest
import pytest_asyncio

from backend.app.companies.company_model import Company
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database


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
