# tests/backend/mystic_auth/security/test_invalid_condition_payload_security.py
#
# Real-DB proof that invalid policy condition payloads are rejected before
# ever reaching the database (claude.md's "invalid payloads" / Policy
# Condition Validation: "Must happen before database writes").
import pytest
from backend.mystic_auth.authorization.repositories.policy_repository import policy_repository
from backend.mystic_auth.database.connection import database

from .conftest import create_system_user, unique_email, unique_policy_name


@pytest.mark.asyncio
async def test_unknown_condition_key_is_rejected_and_never_persisted(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "actions": ["sectest:view"],
            "resource_type": "sectest_resource",
            "conditions": {"totally_made_up_condition": True},
        },
    )

    assert resp.status_code == 422
    async with database.async_session() as session:
        assert await policy_repository.get_by_name(policy_name, session) is None


@pytest.mark.asyncio
async def test_malformed_time_condition_is_rejected(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "actions": ["sectest:view"],
            "resource_type": "sectest_resource",
            "conditions": {"time": "09:00-17:00"},  # must be an object, not a string
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_ip_in_network_condition_is_rejected(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "actions": ["sectest:view"],
            "resource_type": "sectest_resource",
            "conditions": {"network": {"allowed_ips": ["not-an-ip-address"]}},
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_timezone_is_rejected(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "actions": ["sectest:view"],
            "resource_type": "sectest_resource",
            "conditions": {"time": {"start": "09:00", "end": "17:00", "timezone": "Not/A_Real_Zone"}},
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_existing_policy_conditions_cannot_be_corrupted_via_update(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    create_resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "actions": ["sectest:view"],
            "resource_type": "sectest_resource",
            "conditions": {"self_only": True},
        },
    )
    assert create_resp.status_code == 201

    update_resp = await client.put(
        f"/authorization/policies/{policy_name}",
        json={"conditions": {"date_range": {"start": "not-a-date"}}},
    )
    assert update_resp.status_code == 422

    # Original, valid conditions must be untouched
    get_resp = await client.get(f"/authorization/policies/{policy_name}")
    assert get_resp.json()["conditions"] == {"self_only": True}
