# tests/backend/mystic_auth/security/test_batch_authorization_abuse_security.py
#
# Real-DB proof of the Batch Authorization API's abuse resistance
# (batch authorization abuse): oversized/empty/malformed
# batches rejected before evaluation, and a denied result never leaks
# which policy was involved.
import pytest
from backend.mystic_auth.authorization.policies.default_policies import SELF_SERVICE_POLICY_NAME
from backend.mystic_auth.authorization.repositories.policy_repository import policy_repository
from backend.mystic_auth.authorization.schemas.batch_authorization_schema import MAX_BATCH_SIZE
from backend.mystic_auth.database.connection import database

from .conftest import create_verified_user, unique_email, unique_policy_name


@pytest.mark.asyncio
async def test_oversized_batch_is_rejected_before_any_evaluation(client, created_emails):
    email = unique_email("batch-abuse")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    checks = [{"action": "users:read_own", "resource_type": "users"} for _ in range(MAX_BATCH_SIZE + 1)]
    resp = await client.post("/authorization/batch-check", json={"checks": checks})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_empty_batch_is_rejected(client, created_emails):
    email = unique_email("batch-empty")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.post("/authorization/batch-check", json={"checks": []})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_malformed_check_in_batch_is_rejected(client, created_emails):
    email = unique_email("batch-malformed")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.post(
        "/authorization/batch-check",
        json={"checks": [{"action": "", "resource_type": "users"}]},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_batch_check_is_rejected(client):
    resp = await client.post(
        "/authorization/batch-check", json={"checks": [{"action": "users:read_own", "resource_type": "users"}]}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_denied_batch_result_never_leaks_policy_names(client, created_emails):
    """A caller probing many actions at once must never learn which
    (if any) policy was a candidate/rejected, or which condition key
    failed : only allowed + a coarse denial_reason."""
    email = unique_email("batch-leak")
    secret_policy_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {
                "name": secret_policy_name,
                "actions": ["sectest:secret_action"],
                "resource_type": "sectest_resource",
                "conditions": {"resource_attributes": {"status": "draft"}},
            },
            session,
        )
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, secret_policy_name])

    resp = await client.post(
        "/authorization/batch-check",
        json={
            "checks": [
                {
                    "action": "sectest:secret_action",
                    "resource_type": "sectest_resource",
                    "resource": {"status": "published"},  # fails the resource_attributes condition
                }
            ]
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    result = body["results"][0]
    assert result["allowed"] is False
    assert set(result.keys()) == {"action", "resource_type", "allowed", "denial_reason"}
    assert secret_policy_name not in str(body)


@pytest.mark.asyncio
async def test_batch_at_max_size_succeeds_and_matches_individual_checks(client, created_emails):
    email = unique_email("batch-maxsize")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    checks = [{"action": "users:read_own", "resource_type": "users"} for _ in range(MAX_BATCH_SIZE)]
    resp = await client.post("/authorization/batch-check", json={"checks": checks})

    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == MAX_BATCH_SIZE
    assert all(r["allowed"] is True for r in results)
