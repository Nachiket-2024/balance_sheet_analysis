# Reuses the real-dependency fixtures (client, created_emails, Valkey
# isolation) from tests/backend/integration/, since pytest walks up to find
# conftest.py files. This file just adds user-creation helpers for
# security/attack-scenario tests.
import uuid

import pytest_asyncio

from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud
from backend.mystic_auth.valkey.client import valkey_client

PASSWORD = "StrongPass123!"


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_sectest_policies():
    """Deletes every policy prefixed 'sectest_policy_' after each test, so
    repeated runs don't leave rows behind."""
    yield
    async with database.async_session() as session:
        for policy in await policy_repository.get_all(session):
            if policy.name.startswith("sectest_policy_"):
                await policy_repository.delete(policy, session)


def unique_email(prefix: str = "sectest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


def unique_policy_name() -> str:
    return f"sectest_policy_{uuid.uuid4().hex}"


async def create_verified_user(client, created_emails, email, policy_names):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Security Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        for policy_name in policy_names:
            policy = await policy_repository.get_by_name(policy_name, session)
            await policy_repository.assign_policy_to_user(
                user_id=user.id,
                policy_id=policy.id,
                db=session,
                assigned_by="test",
                user_email=email,
            )

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200
    return login_resp


async def create_system_user(client, created_emails, email):
    return await create_verified_user(
        client, created_emails, email,
        [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


async def create_user_with_custom_policy(client, created_emails, email, actions, resource_type="policies"):
    """Creates a user with only self_service plus one new policy granting
    `actions` on `resource_type`, for testing that a narrowly-scoped caller
    can't escalate beyond it."""
    policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": actions, "resource_type": resource_type, "conditions": None},
            session,
        )
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, policy_name])
    return policy_name
