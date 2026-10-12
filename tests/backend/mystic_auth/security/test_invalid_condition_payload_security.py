# Checks that invalid policy condition payloads are rejected before they
# ever reach the database.
import time

import pytest

from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database

from .conftest import create_system_user, unique_email, unique_policy_name

# ---------------------------- Adversarial size/shape ----------------------------
#
# Before condition_validator.py added _validate_size_and_depth, a
# resource_attributes/context_attributes dict had no cap on key count,
# nesting depth, or string length. That let through: a 150k-key dict that
# took over a second to write and would be re-walked on every future check;
# deeply nested dicts that crashed the response serializer instead of
# failing cleanly; and multi-megabyte strings accepted whole. These tests
# pin the fix: all three must now fail fast with an ordinary 422.
_FAST_REJECTION_SECONDS = 2.0


@pytest.mark.asyncio
async def test_huge_key_count_in_resource_attributes_is_rejected_fast(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    huge_dict = {str(i): i for i in range(150_000)}
    start = time.perf_counter()
    resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "actions": ["sectest:view"],
            "resource_type": "sectest_resource",
            "conditions": {"resource_attributes": huge_dict},
        },
    )
    elapsed = time.perf_counter() - start

    assert resp.status_code == 422
    assert elapsed < _FAST_REJECTION_SECONDS, f"took {elapsed:.2f}s to reject, should fail fast"
    async with database.async_session() as session:
        assert await policy_repository.get_by_name(policy_name, session) is None


@pytest.mark.asyncio
async def test_pathologically_deep_nesting_in_resource_attributes_is_rejected_not_crashed(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    # Raw JSON string, not a Python dict via client.post's `json=` - that
    # makes httpx's own recursive json.dumps encode all 5000 levels before
    # the request is even sent, which can RecursionError on a smaller
    # default thread stack (e.g. musl/Alpine), unrelated to the server.
    # A real attacker sends raw bytes anyway, so this is truer to the attack.
    nested_json = ('{"a":' * 5000) + '"leaf"' + ('}' * 5000)
    payload = (
        f'{{"name":"{policy_name}","actions":["sectest:view"],"resource_type":"sectest_resource",'
        f'"conditions":{{"resource_attributes":{{"field":{nested_json}}}}}}}'
    )

    start = time.perf_counter()
    resp = await client.post(
        "/authorization/policies",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    elapsed = time.perf_counter() - start

    # ordinary 422, not an unhandled 500 from the serializer
    assert resp.status_code == 422
    assert elapsed < _FAST_REJECTION_SECONDS, f"took {elapsed:.2f}s to reject, should fail fast"
    async with database.async_session() as session:
        assert await policy_repository.get_by_name(policy_name, session) is None


@pytest.mark.asyncio
async def test_multi_megabyte_string_in_resource_attributes_is_rejected_fast(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    start = time.perf_counter()
    resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "actions": ["sectest:view"],
            "resource_type": "sectest_resource",
            "conditions": {"resource_attributes": {"field": "x" * 5_000_000}},
        },
    )
    elapsed = time.perf_counter() - start

    assert resp.status_code == 422
    assert elapsed < _FAST_REJECTION_SECONDS, f"took {elapsed:.2f}s to reject, should fail fast"
    async with database.async_session() as session:
        assert await policy_repository.get_by_name(policy_name, session) is None


@pytest.mark.asyncio
async def test_reasonably_shaped_conditions_still_pass_the_size_guard(client, created_emails):
    """An ordinary conditions block, well within the size caps, should
    still be accepted."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "actions": ["sectest:view"],
            "resource_type": "sectest_resource",
            "conditions": {
                "time": {"start": "09:00", "end": "17:00", "timezone": "UTC"},
                "resource_attributes": {"status": "active", "owner": "someone"},
            },
        },
    )
    assert resp.status_code == 201


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
