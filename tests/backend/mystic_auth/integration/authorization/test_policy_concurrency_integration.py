# Real-concurrency regressions for policy CRUD/assignment: two admins
# editing the same policy at once, an update racing a delete, and two
# admins concurrently revoking each other's system_superuser assignment.
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.mystic_auth.authorization.policies.default_policies import (
    SYSTEM_SUPERUSER_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_assignment_repository import (
    policy_assignment_repository,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database

from .authorization_test_accounts import (
    PASSWORD,
    cleanup_test_policies,
    create_system_user,
    unique_email,
    unique_policy_name,
)

__all__ = ["cleanup_test_policies"]


@pytest.mark.asyncio
async def test_concurrent_updates_to_the_same_policy_do_not_lose_writes_or_corrupt_history(
    client, created_emails
):
    """Regression: two admins editing the same policy concurrently used to
    both read the same pre-update row, so the second commit could silently
    discard the first's change. Fires two concurrent PUTs and asserts both
    changes land and history chains correctly."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    create_resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "description": "original description",
            "actions": ["projects:read"],
            "resource_type": "projects",
        },
    )
    assert create_resp.status_code == 201

    responses = await asyncio.gather(
        client.put(f"/authorization/policies/{policy_name}", json={"description": "changed by A"}),
        client.put(f"/authorization/policies/{policy_name}", json={"conditions": {"self_only": True}}),
    )
    assert all(r.status_code == 200 for r in responses)

    final = await client.get(f"/authorization/policies/{policy_name}")
    assert final.status_code == 200
    final_body = final.json()
    # Neither write should have been silently overwritten by stale data.
    assert final_body["description"] == "changed by A"
    assert final_body["conditions"] == {"self_only": True}

    history_resp = await client.get(f"/authorization/policies/{policy_name}/history")
    assert history_resp.status_code == 200
    entries = history_resp.json()
    updated_entries = [e for e in entries if e["change_type"] == "updated"]
    assert len(updated_entries) == 2
    # Read oldest-to-newest, each entry's previous_definition must match
    # the prior entry's new_definition, proof the second update saw the
    # first's committed row, not a stale snapshot.
    chain = list(reversed(updated_entries))
    assert chain[0]["previous_definition"]["description"] == "original description"
    assert chain[0]["previous_definition"]["conditions"] is None
    assert chain[1]["previous_definition"] == chain[0]["new_definition"]
    # Must carry both edits regardless of which request won the commit race.
    assert chain[1]["new_definition"]["description"] == "changed by A"
    assert chain[1]["new_definition"]["conditions"] == {"self_only": True}


@pytest.mark.asyncio
async def test_concurrent_update_racing_a_delete_of_the_same_policy_returns_404_not_500(
    client, created_emails
):
    """Regression: if a concurrent delete removes the policy while an
    update is blocked on the row lock, the update's re-fetch returns None.
    Without a check, that raised an uncaught AttributeError (500) instead
    of a clean error."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    create_resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "description": "original description",
            "actions": ["projects:read"],
            "resource_type": "projects",
        },
    )
    assert create_resp.status_code == 201

    responses = await asyncio.gather(
        client.put(f"/authorization/policies/{policy_name}", json={"description": "changed"}),
        client.delete(f"/authorization/policies/{policy_name}"),
        return_exceptions=True,
    )

    for resp in responses:
        assert not isinstance(resp, Exception)
        # Whichever wins the race, the loser must get a clean 4xx, never a 500.
        assert resp.status_code < 500, resp.text


@pytest.mark.asyncio
async def test_concurrent_bulk_removes_cannot_jointly_strip_every_superuser_holder(created_emails):
    """Regression for a TOCTOU race in the "can't remove the last
    system_superuser" lockout guard: two admins who are the only two
    holders could concurrently revoke each other's access, each pre-check
    only sees itself removing one of two, so both commit and every holder
    gets stripped.

    Uses two independent authenticated clients firing concurrently, like
    two admins in two browser tabs."""
    holder_a = unique_email("holder-a")
    holder_b = unique_email("holder-b")

    async def _new_client():
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="https://testserver", follow_redirects=False)

    setup_client = await _new_client()
    try:
        await create_system_user(setup_client, created_emails, holder_a)
        await create_system_user(setup_client, created_emails, holder_b)
    finally:
        await setup_client.aclose()

    client_a = await _new_client()
    client_b = await _new_client()
    try:
        await client_a.post("/auth/login", json={"email": holder_a, "password": PASSWORD})
        await client_b.post("/auth/login", json={"email": holder_b, "password": PASSWORD})

        # Each holder concurrently revokes the other's superuser assignment.
        responses = await asyncio.gather(
            client_a.post(
                "/authorization/bulk/policies/remove",
                json={"items": [{"user_email": holder_b, "policy_name": SYSTEM_SUPERUSER_POLICY_NAME}]},
            ),
            client_b.post(
                "/authorization/bulk/policies/remove",
                json={"items": [{"user_email": holder_a, "policy_name": SYSTEM_SUPERUSER_POLICY_NAME}]},
            ),
        )
        assert all(r.status_code == 200 for r in responses)

        outcomes = [r.json()["results"][0]["status"] for r in responses]
        # Exactly one removal must be blocked by the lockout guard (order
        # is non-deterministic, whichever wins the row lock removes the
        # other, and the second must refuse to leave zero holders).
        assert sorted(outcomes) == ["error", "success"]

        async with database.async_session() as session:
            superuser_policy = await policy_repository.get_by_name(SYSTEM_SUPERUSER_POLICY_NAME, session)
            remaining_holders = set(await policy_assignment_repository.get_holder_emails(superuser_policy.id, session))
        assert holder_a in remaining_holders or holder_b in remaining_holders
    finally:
        await client_a.aclose()
        await client_b.aclose()
