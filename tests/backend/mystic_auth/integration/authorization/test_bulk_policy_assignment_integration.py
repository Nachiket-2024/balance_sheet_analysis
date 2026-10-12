# tests/backend/mystic_auth/integration/authorization/test_bulk_policy_assignment_integration.py
#
# End-to-end coverage for backend/mystic_auth/api/pbac_routes/bulk/bulk_policy_routes.py:
# fanning one chosen policy out across many users in one request. Proves the
# best-effort contract (bulk_schema.py): valid items commit and take real
# effect, invalid ones report a per-item error without blocking the rest of
# the batch, and an item that changed nothing (the user already held the
# policy) is reported "already_held" rather than a plain "success" - see
# PolicyAssignmentRepository.bulk_assign_policies's own docstring.
#
# Permission/role counterparts live in their own sibling files
# (test_bulk_permission_assignment_integration.py /
# test_bulk_role_assignment_integration.py) - split out from one combined
# file to keep each under ~300 lines and grouped by the same domain
# boundary the route/repository files themselves use.
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_assignment_repository import (
    policy_assignment_repository,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud

from .authorization_test_accounts import (
    PASSWORD,
    cleanup_test_policies,
    create_system_user,
    create_verified_user,
    unique_email,
    unique_policy_name,
)

__all__ = ["cleanup_test_policies"]


@pytest.mark.asyncio
async def test_bulk_assign_policies_grants_access_to_every_selected_user(client, created_emails):
    system_email = unique_email("system")
    target_a = unique_email("bulk-a")
    target_b = unique_email("bulk-b")
    await create_verified_user(client, created_emails, target_a, [SELF_SERVICE_POLICY_NAME])
    await create_verified_user(client, created_emails, target_b, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/policies/assign",
        json={"items": [
            {"user_email": target_a, "policy_name": USER_MANAGEMENT_POLICY_NAME},
            {"user_email": target_b, "policy_name": USER_MANAGEMENT_POLICY_NAME},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 2
    assert body["error_count"] == 0
    statuses = {r["user_email"]: r["status"] for r in body["results"]}
    assert statuses[target_a] == "success"
    assert statuses[target_b] == "success"

    for target in (target_a, target_b):
        await client.post("/auth/login", json={"email": target, "password": PASSWORD})
        allowed = await client.get("/users/")
        assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_bulk_assign_policies_is_best_effort_not_all_or_nothing(client, created_emails):
    """One item targets a nonexistent user, one is genuinely valid: the
    valid one must still commit and take effect, the invalid one must
    report an error - never the whole batch rolling back together."""
    system_email = unique_email("system")
    target = unique_email("bulk-valid")
    await create_verified_user(client, created_emails, target, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/policies/assign",
        json={"items": [
            {"user_email": target, "policy_name": USER_MANAGEMENT_POLICY_NAME},
            {"user_email": unique_email("bulk-missing"), "policy_name": USER_MANAGEMENT_POLICY_NAME},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    statuses = {r["user_email"]: r["status"] for r in body["results"]}
    assert statuses[target] == "success"

    await client.post("/auth/login", json={"email": target, "password": PASSWORD})
    allowed = await client.get("/users/")
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_bulk_assign_policies_reports_already_held_without_duplicating_the_row(client, created_emails):
    """Assigning a policy a user already holds must not error and must not
    add a second row - it's reported "already_held", distinct from a fresh
    "success", so a bulk-assign-across-many-users UI can tell an admin
    which selected users this action actually changed anything for (see
    BulkOperationResultList.tsx)."""
    system_email = unique_email("system")
    target = unique_email("bulk-already-held")
    already_holding_target = unique_email("bulk-already-held-2")
    await create_verified_user(client, created_emails, target, [SELF_SERVICE_POLICY_NAME])
    await create_verified_user(
        client, created_emails, already_holding_target, [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME]
    )
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/policies/assign",
        json={"items": [
            {"user_email": target, "policy_name": USER_MANAGEMENT_POLICY_NAME},
            {"user_email": already_holding_target, "policy_name": USER_MANAGEMENT_POLICY_NAME},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    # already_held counts as a success (it's a no-op, not a failure) -
    # see bulk_schema.py's summarize().
    assert body["success_count"] == 2
    assert body["error_count"] == 0
    statuses = {r["user_email"]: r["status"] for r in body["results"]}
    assert statuses[target] == "success"
    assert statuses[already_holding_target] == "already_held"

    # Re-assigning must not have created a duplicate UserPolicy row.
    async with database.async_session() as session:
        assigned = await policy_assignment_repository.get_policies_for_user(already_holding_target, session)
    assert sum(1 for p in assigned if p.name == USER_MANAGEMENT_POLICY_NAME) == 1


@pytest.mark.asyncio
async def test_bulk_assign_policies_reports_policy_not_found_without_blocking_other_items(client, created_emails):
    system_email = unique_email("system")
    target = unique_email("bulk-policy-not-found")
    await create_verified_user(client, created_emails, target, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/policies/assign",
        json={"items": [
            {"user_email": target, "policy_name": "this_policy_does_not_exist"},
            {"user_email": target, "policy_name": USER_MANAGEMENT_POLICY_NAME},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    outcomes = {r["identifier"]: (r["status"], r["error"]) for r in body["results"]}
    assert outcomes["this_policy_does_not_exist"] == ("error", "POLICY_NOT_FOUND")
    assert outcomes[USER_MANAGEMENT_POLICY_NAME][0] == "success"


@pytest.mark.asyncio
async def test_concurrent_bulk_assigns_of_the_same_pair_do_not_fail_the_whole_batch(created_emails):
    """Regression for a real race in bulk_assign_policies: it used to read
    existing_pairs once, then stage every non-held item's insert, and
    commit the whole batch in one shot. Two concurrent bulk-assign requests
    that both include the same (user, policy) pair would each see "not
    already held" from their own pre-read, both stage an insert, and the
    loser's db.commit() hit the uq_user_policy unique constraint -
    previously reported as "commit_failed" for the *entire* batch,
    including unrelated pairs that never conflicted with anything.

    Uses two independent authenticated clients (real cookie sessions, real
    Postgres) firing concurrently: one shared (user, policy) pair plus one
    distinct, non-conflicting pair per request, exactly like two different
    admins in two different browser tabs each bulk-assigning an overlapping
    selection.
    """
    system_email = unique_email("system")
    shared_target = unique_email("race-shared")
    distinct_a = unique_email("race-distinct-a")
    distinct_b = unique_email("race-distinct-b")

    async def _new_client():
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="https://testserver", follow_redirects=False)

    setup_client = await _new_client()
    try:
        await create_system_user(setup_client, created_emails, system_email)
        await create_verified_user(setup_client, created_emails, shared_target, [SELF_SERVICE_POLICY_NAME])
        await create_verified_user(setup_client, created_emails, distinct_a, [SELF_SERVICE_POLICY_NAME])
        await create_verified_user(setup_client, created_emails, distinct_b, [SELF_SERVICE_POLICY_NAME])
    finally:
        await setup_client.aclose()

    client_a = await _new_client()
    client_b = await _new_client()
    try:
        await client_a.post("/auth/login", json={"email": system_email, "password": PASSWORD})
        await client_b.post("/auth/login", json={"email": system_email, "password": PASSWORD})

        responses = await asyncio.gather(
            client_a.post(
                "/authorization/bulk/policies/assign",
                json={"items": [
                    {"user_email": shared_target, "policy_name": USER_MANAGEMENT_POLICY_NAME},
                    {"user_email": distinct_a, "policy_name": USER_MANAGEMENT_POLICY_NAME},
                ]},
            ),
            client_b.post(
                "/authorization/bulk/policies/assign",
                json={"items": [
                    {"user_email": shared_target, "policy_name": USER_MANAGEMENT_POLICY_NAME},
                    {"user_email": distinct_b, "policy_name": USER_MANAGEMENT_POLICY_NAME},
                ]},
            ),
        )
        assert all(r.status_code == 200 for r in responses)

        # Neither request's batch may fail wholesale: every item in both
        # batches must resolve to a genuine success/already_held, never the
        # old blanket "commit_failed" caused by the other request's win on
        # the shared pair.
        for resp in responses:
            body = resp.json()
            assert body["error_count"] == 0, body
            assert all(r["status"] in ("success", "already_held") for r in body["results"])

        # The shared pair must have landed exactly once, whichever request
        # actually won the race to insert it first.
        async with database.async_session() as session:
            shared_policies = await policy_assignment_repository.get_policies_for_user(shared_target, session)
        assert sum(1 for p in shared_policies if p.name == USER_MANAGEMENT_POLICY_NAME) == 1

        # Each request's own distinct, non-conflicting pair must also have
        # landed - proof the race on the shared pair didn't take the rest
        # of either batch down with it.
        for target in (distinct_a, distinct_b):
            await client_a.post("/auth/login", json={"email": target, "password": PASSWORD})
            allowed = await client_a.get("/users/")
            assert allowed.status_code == 200
    finally:
        await client_a.aclose()
        await client_b.aclose()


@pytest.mark.asyncio
async def test_bulk_remove_policies_revokes_access_from_every_selected_user(client, created_emails):
    system_email = unique_email("system")
    target_a = unique_email("bulk-remove-a")
    target_b = unique_email("bulk-remove-b")
    await create_verified_user(
        client, created_emails, target_a, [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME]
    )
    await create_verified_user(
        client, created_emails, target_b, [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME]
    )
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/policies/remove",
        json={"items": [
            {"user_email": target_a, "policy_name": USER_MANAGEMENT_POLICY_NAME},
            {"user_email": target_b, "policy_name": USER_MANAGEMENT_POLICY_NAME},
        ]},
    )
    assert resp.status_code == 200
    assert resp.json()["success_count"] == 2

    for target in (target_a, target_b):
        await client.post("/auth/login", json={"email": target, "password": PASSWORD})
        denied = await client.get("/users/")
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_bulk_remove_policies_only_own_escalation_guard_blocks_a_policy_not_held_by_caller(
    client, created_emails
):
    """The bulk *remove* path re-applies the same assert_authorized_to_grant
    guard as bulk assign - a caller holding only policies:revoke (never
    system_superuser) cannot remove a policy carrying an action they don't
    hold themselves."""
    system_email = unique_email("system")
    escalator = unique_email("bulk-revoke-escalate")
    target = unique_email("bulk-revoke-target")
    await create_system_user(client, created_emails, system_email)
    await create_verified_user(
        client, created_emails, target, [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME]
    )
    await create_verified_user(client, created_emails, escalator, [SELF_SERVICE_POLICY_NAME])

    async with database.async_session() as session:
        narrow_policy = await policy_repository.create(
            {"name": unique_policy_name(), "actions": ["policies:revoke"], "resource_type": "policies", "conditions": None},
            session,
        )
        user = await user_crud.get_by_email(escalator, session)
        await policy_repository.assign_policy_to_user(
            user_id=user.id, policy_id=narrow_policy.id, db=session, assigned_by="test"
        )

    await client.post("/auth/login", json={"email": escalator, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/policies/remove",
        json={"items": [{"user_email": target, "policy_name": USER_MANAGEMENT_POLICY_NAME}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error_count"] == 1
    assert body["results"][0]["error"] == "CANNOT_GRANT_UNHELD_ACTION"
