# tests/backend/mystic_auth/security/test_policy_tampering_security.py
#
# Real-DB proof of the two "System policy protection" guarantees
# : baseline policies can never be deleted/renamed via the
# management API, and the last remaining system_superuser assignment can
# never be revoked : even by a genuine system_superuser holder. Unit
# tests already cover this with mocks; these hit the real API + real DB.
import pytest
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database

from .conftest import create_system_user, unique_email


@pytest.mark.asyncio
async def test_baseline_policies_cannot_be_deleted_even_by_system_superuser(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    for policy_name in (SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME):
        resp = await client.delete(f"/authorization/policies/{policy_name}")
        assert resp.status_code == 403, f"{policy_name} should be undeletable"

        # Confirm it's still actually there
        get_resp = await client.get(f"/authorization/policies/{policy_name}")
        assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_baseline_policies_cannot_be_renamed_even_by_system_superuser(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    resp = await client.put(
        f"/authorization/policies/{SYSTEM_SUPERUSER_POLICY_NAME}",
        json={"name": "hijacked_superuser_policy"},
    )
    assert resp.status_code == 403

    # The name is unchanged, and the "renamed" name doesn't exist
    get_resp = await client.get(f"/authorization/policies/{SYSTEM_SUPERUSER_POLICY_NAME}")
    assert get_resp.status_code == 200
    missing_resp = await client.get("/authorization/policies/hijacked_superuser_policy")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_last_system_superuser_assignment_cannot_be_removed(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    # Determine the real current holder count directly, so this test is
    # deterministic regardless of whatever else exists in this DB (e.g. a
    # real seeded system account from create_system_user.py).
    async with database.async_session() as session:
        superuser_policy = await policy_repository.get_by_name(SYSTEM_SUPERUSER_POLICY_NAME, session)
        holder_count = await policy_repository.count_assignments(superuser_policy.id, session)

    resp = await client.delete(
        f"/authorization/users/{system_email}/policies/{SYSTEM_SUPERUSER_POLICY_NAME}"
    )

    if holder_count <= 1:
        assert resp.status_code == 409
        # The assignment must genuinely still be held
        policies_resp = await client.get(f"/authorization/users/{system_email}/policies")
        names = {p["name"] for p in policies_resp.json()["policies"]}
        assert SYSTEM_SUPERUSER_POLICY_NAME in names
    else:
        # Other holders exist, so removing this one is legitimately allowed
        assert resp.status_code == 200
