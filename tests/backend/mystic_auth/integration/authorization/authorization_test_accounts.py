# tests/backend/mystic_auth/integration/authorization_test_accounts.py
#
# Shared account/policy helpers for the PBAC policy-management integration
# test files (test_policy_crud_integration.py,
# test_policy_action_separation_integration.py,
# test_policy_assignment_integration.py,
# test_authorization_check_integration.py): all four need the same
# verified-user/system-user setup and a disposable, uniquely-named policy
# to test against without colliding with the baseline seeded policies.
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


def unique_email(prefix: str = "inttest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


def unique_policy_name() -> str:
    return f"test_policy_{uuid.uuid4().hex}"


async def create_verified_user(client, created_emails, email, policy_names):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD}
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
                user_id=user.id, policy_id=policy.id, db=session, assigned_by="test"
            )

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200
    return login_resp


async def create_system_user(client, created_emails, email):
    return await create_verified_user(
        client, created_emails, email,
        [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


async def create_user_with_custom_policy_actions(client, created_emails, email, actions):
    """Creates a user holding a single, freshly-created policy granting
    exactly `actions` on resource_type="policies", used to prove the
    fine-grained policies:read/create/update/delete/assign/revoke actions
    are each independently enforced, rather than all-or-nothing like the
    old coarse policies:manage."""
    policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": actions, "resource_type": "policies", "conditions": None},
            session,
        )
    return await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, policy_name])


@pytest_asyncio.fixture(autouse=True)
async def cleanup_test_policies():
    """Every policy created by these tests is prefixed 'test_policy_';
    delete them on teardown so repeated runs don't accumulate rows."""
    yield
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        for policy in policies:
            if policy.name.startswith("test_policy_"):
                await policy_repository.delete(policy, session)
