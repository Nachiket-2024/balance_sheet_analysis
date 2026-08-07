# tests/backend/mystic_auth/security/conftest.py
#
# Shares the same real-dependency fixtures (client, created_emails, Redis
# isolation) as tests/backend/integration/ : security tests run against
# the exact same real Postgres/Redis, they just group a different concern
# (attack scenarios) rather than lifecycle coverage. Reusing the parent
# conftest.py's fixtures (pytest auto-discovers the nearest conftest.py up
# the directory tree first, then this one) plus a couple of small,
# security-suite-specific user-creation helpers.
import uuid

import pytest_asyncio
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.redis.client import redis_client
from backend.mystic_auth.user_crud.user_crud_collector import user_crud

PASSWORD = "StrongPass123!"


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_sectest_policies():
    """Every policy this suite creates (directly, or via a test hitting
    POST /authorization/policies) is prefixed 'sectest_policy_' : delete
    them on teardown so repeated runs don't accumulate rows."""
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
    await redis_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        for policy_name in policy_names:
            policy = await policy_repository.get_by_name(policy_name, session)
            await policy_repository.assign_policy_to_user(
                user_id=user.id, policy_id=policy.id, db=session, assigned_by="test", user_email=email
            )

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200
    return login_resp


async def create_system_user(client, created_emails, email):
    return await create_verified_user(
        client, created_emails, email,
        [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


async def create_user_with_custom_policy(client, created_emails, email, actions, resource_type="policies"):
    """A user holding exactly self_service + one freshly created policy
    granting `actions` on `resource_type` : used to prove a caller with
    only a narrow slice of policies:* actions can't escalate beyond it."""
    policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": actions, "resource_type": resource_type, "conditions": None},
            session,
        )
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, policy_name])
    return policy_name
