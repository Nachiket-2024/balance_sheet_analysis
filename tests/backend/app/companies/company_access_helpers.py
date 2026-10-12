"""Shared setup for company authorization integration tests."""

import uuid

from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud
from backend.mystic_auth.valkey.client import valkey_client

PASSWORD = "StrongPass123!"


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


async def _create_verified_user_with_policy(
    client, created_emails, email, actions, condition_key, condition_value
):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)

        self_service = await policy_repository.get_by_name(
            SELF_SERVICE_POLICY_NAME, session
        )
        await policy_repository.assign_policy_to_user(
            user.id, self_service.id, session, assigned_by="test"
        )

        policy = await policy_repository.create(
            {
                "name": _unique("test_policy_company_scope"),
                "actions": actions,
                "resource_type": "*",
                "conditions": {"resource_attributes": {condition_key: condition_value}},
            },
            session,
        )
        await policy_repository.assign_policy_to_user(
            user.id, policy.id, session, assigned_by="test"
        )

    login_resp = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200
    return client
