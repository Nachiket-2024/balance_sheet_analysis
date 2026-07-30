# tests/backend/mystic_auth/integration/test_authorization_routes_integration.py
#
# End-to-end coverage for the PBAC policy management API
# (backend/mystic_auth/api/pbac_routes/) against the real ASGI app, real
# PostgreSQL, and real Redis. Per claude.md: "All management actions must
# themselves use PBAC authorization": these tests prove that gate, and
# that assigning/removing a policy via this API actually changes what an
# account can do (the real end-to-end point of the whole system).
import uuid

import pytest
import pytest_asyncio
from backend.mystic_auth.auth.verify_account.account_verification_service import account_verification_service
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import policy_repository
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.redis.client import redis_client
from backend.mystic_auth.user_crud.user_crud_collector import user_crud

PASSWORD = "StrongPass123!"


def _unique_email(prefix: str = "inttest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


def _unique_policy_name() -> str:
    return f"test_policy_{uuid.uuid4().hex}"


async def _create_verified_user(client, created_emails, email, policy_names):
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


async def _create_system_user(client, created_emails, email):
    return await _create_verified_user(
        client, created_emails, email,
        [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


async def _create_user_with_custom_policy_actions(client, created_emails, email, actions):
    """Creates a user holding a single, freshly-created policy granting
    exactly `actions` on resource_type="policies", used to prove the
    fine-grained policies:read/create/update/delete/assign/revoke actions
    are each independently enforced, rather than all-or-nothing like the
    old coarse policies:manage."""
    policy_name = _unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {"name": policy_name, "actions": actions, "resource_type": "policies", "conditions": None},
            session,
        )
    return await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, policy_name])


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_test_policies():
    """Every policy created by these tests is prefixed 'test_policy_';
    delete them on teardown so repeated runs don't accumulate rows."""
    yield
    async with database.async_session() as session:
        policies = await policy_repository.get_all(session)
        for policy in policies:
            if policy.name.startswith("test_policy_"):
                await policy_repository.delete(policy, session)


# ---------------------------- Authorization gate on management routes ----------------------------

@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(client):
    resp = await client.get("/authorization/policies")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_manage_policies(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/authorization/policies")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_without_policies_read_cannot_manage_policies(client, created_emails):
    # user_administration does not include policies:read (or any of the
    # other fine-grained policies:* actions); only system_superuser does.
    # An ordinary admin must be denied here.
    email = _unique_email("admin")
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME])

    resp = await client.get("/authorization/policies")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_policies_respects_limit_query_param(client, created_emails):
    # Regression guard: GET /authorization/policies previously read the
    # whole table unconditionally, unlike every other list endpoint in the
    # app. The baseline seeded policies (self_service, user_administration,
    # system_superuser, ...) guarantee more than one row exists already.
    email = _unique_email("system")
    await _create_verified_user(client, created_emails, email, [SYSTEM_SUPERUSER_POLICY_NAME])

    resp = await client.get("/authorization/policies?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------------------------- Fine-grained policies:* action separation ----------------------------
# Proves the old coarse "policies:manage" is genuinely gone: a caller
# holding only one of policies:read/create/update/delete/assign/revoke is
# authorized on the matching route(s) only, and denied (403) on every
# other policy-management route.

async def _attempt_policy_routes(client, target_email):
    """As the currently logged-in caller, attempts every policy-management
    route against a disposable policy, returning {action: status_code}.
    A 403 means the authorization dependency denied the caller; any other
    status (200/201/404/409/...) means the caller was authorized to reach
    the route handler, regardless of the handler's functional outcome."""
    policy_name = _unique_policy_name()

    create_resp = await client.post(
        "/authorization/policies",
        json={"name": policy_name, "actions": ["projects:read"], "resource_type": "projects"},
    )
    statuses = {"create": create_resp.status_code}

    # The remaining checks need a real policy row to target regardless of
    # whether "create" itself was authorized: create it directly via the
    # repository, bypassing the API, if the API call was denied.
    if create_resp.status_code != 201:
        async with database.async_session() as session:
            await policy_repository.create(
                {
                    "name": policy_name,
                    "actions": ["projects:read"],
                    "resource_type": "projects",
                    "conditions": None,
                },
                session,
            )

    statuses["read_list"] = (await client.get("/authorization/policies")).status_code
    statuses["read_get"] = (await client.get(f"/authorization/policies/{policy_name}")).status_code
    statuses["update"] = (
        await client.put(f"/authorization/policies/{policy_name}", json={"description": "updated"})
    ).status_code
    statuses["assign"] = (
        await client.post(f"/authorization/users/{target_email}/policies", json={"policy_name": policy_name})
    ).status_code
    statuses["revoke"] = (
        await client.delete(f"/authorization/users/{target_email}/policies/{policy_name}")
    ).status_code
    statuses["delete"] = (await client.delete(f"/authorization/policies/{policy_name}")).status_code
    return statuses


@pytest.mark.asyncio
async def test_policies_read_only_can_read_but_not_write(client, created_emails):
    email = _unique_email("read-only")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_user_with_custom_policy_actions(client, created_emails, email, ["policies:read"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["read_list"] != 403
    assert statuses["read_get"] != 403
    for action in ("create", "update", "delete", "assign", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_create_only_cannot_read_update_delete_assign_or_revoke(client, created_emails):
    email = _unique_email("create-only")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_user_with_custom_policy_actions(client, created_emails, email, ["policies:create"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["create"] != 403
    for action in ("read_list", "read_get", "update", "delete", "assign", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_update_only_cannot_read_create_delete_assign_or_revoke(client, created_emails):
    email = _unique_email("update-only")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_user_with_custom_policy_actions(client, created_emails, email, ["policies:update"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["update"] != 403
    for action in ("read_list", "read_get", "create", "delete", "assign", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_delete_only_cannot_read_create_update_assign_or_revoke(client, created_emails):
    email = _unique_email("delete-only")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_user_with_custom_policy_actions(client, created_emails, email, ["policies:delete"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["delete"] != 403
    for action in ("read_list", "read_get", "create", "update", "assign", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_assign_only_cannot_read_create_update_delete_or_revoke(client, created_emails):
    email = _unique_email("assign-only")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_user_with_custom_policy_actions(client, created_emails, email, ["policies:assign"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["assign"] != 403
    for action in ("read_list", "read_get", "create", "update", "delete", "revoke"):
        assert statuses[action] == 403


@pytest.mark.asyncio
async def test_policies_revoke_only_cannot_read_create_update_delete_or_assign(client, created_emails):
    email = _unique_email("revoke-only")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_user_with_custom_policy_actions(client, created_emails, email, ["policies:revoke"])

    statuses = await _attempt_policy_routes(client, target_email)
    assert statuses["revoke"] != 403
    for action in ("read_list", "read_get", "create", "update", "delete", "assign"):
        assert statuses[action] == 403


# ---------------------------- Policy CRUD ----------------------------

@pytest.mark.asyncio
async def test_system_user_can_create_list_update_and_delete_a_policy(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    policy_name = _unique_policy_name()

    create_resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "description": "A test-only policy",
            "actions": ["projects:read"],
            "resource_type": "projects",
        },
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["name"] == policy_name
    assert body["is_active"] is True
    assert body["created_by"] == system_email

    list_resp = await client.get("/authorization/policies")
    assert list_resp.status_code == 200
    assert any(p["name"] == policy_name for p in list_resp.json())

    update_resp = await client.put(
        f"/authorization/policies/{policy_name}", json={"is_active": False}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False

    delete_resp = await client.delete(f"/authorization/policies/{policy_name}")
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"/authorization/policies/{policy_name}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_creating_a_duplicate_named_policy_is_rejected(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    policy_name = _unique_policy_name()

    payload = {
        "name": policy_name,
        "actions": ["projects:read"],
        "resource_type": "projects",
    }
    first = await client.post("/authorization/policies", json=payload)
    assert first.status_code == 201

    second = await client.post("/authorization/policies", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_renaming_a_policy_to_an_existing_name_is_rejected(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)

    first_name = _unique_policy_name()
    second_name = _unique_policy_name()

    first = await client.post(
        "/authorization/policies",
        json={"name": first_name, "actions": ["projects:read"], "resource_type": "projects"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/authorization/policies",
        json={"name": second_name, "actions": ["projects:read"], "resource_type": "projects"},
    )
    assert second.status_code == 201

    rename_resp = await client.put(f"/authorization/policies/{first_name}", json={"name": second_name})
    assert rename_resp.status_code == 409

    # Confirm it actually didn't take: the original policy is still reachable under its old name
    get_resp = await client.get(f"/authorization/policies/{first_name}")
    assert get_resp.status_code == 200


# ---------------------------- Policy assignment actually changes access ----------------------------

@pytest.mark.asyncio
async def test_assigning_user_administration_via_the_api_actually_grants_list_all_access(
    client, created_emails
):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    # Before assignment: target cannot list users. Log in as target to check.
    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    denied = await client.get("/users/")
    assert denied.status_code == 403

    # Assign, acting as the system user
    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assign_resp = await client.post(
        f"/authorization/users/{target_email}/policies",
        json={"policy_name": USER_ADMINISTRATION_POLICY_NAME},
    )
    assert assign_resp.status_code == 200

    # After assignment: target can list users, no new login/token needed,
    # since authorization is evaluated fresh from the DB on every request.
    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    allowed = await client.get("/users/")
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_removing_a_policy_via_the_api_actually_revokes_access(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(
        client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME]
    )
    await _create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    allowed = await client.get("/users/")
    assert allowed.status_code == 200

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    remove_resp = await client.delete(
        f"/authorization/users/{target_email}/policies/{USER_ADMINISTRATION_POLICY_NAME}"
    )
    assert remove_resp.status_code == 200

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    denied = await client.get("/users/")
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_removing_a_policy_the_user_does_not_hold_returns_404(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    resp = await client.delete(
        f"/authorization/users/{target_email}/policies/{USER_ADMINISTRATION_POLICY_NAME}"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_user_policies_reports_currently_assigned_policies(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(
        client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME]
    )
    await _create_system_user(client, created_emails, system_email)

    resp = await client.get(f"/authorization/users/{target_email}/policies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_email"] == target_email
    names = {p["name"] for p in body["policies"]}
    assert names == {SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME}


@pytest.mark.asyncio
async def test_users_me_policies_returns_the_callers_own_policies_without_policies_read(
    client, created_emails
):
    """The frontend's getUserPolicies() calls this self-service endpoint:
    a plain self_service-only user (no policies:read) must be able to see
    their own assignments, unlike the admin GET /users/{email}/policies."""
    email = _unique_email()
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/authorization/users/me/policies")

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_email"] == email
    names = {p["name"] for p in body["policies"]}
    assert names == {SELF_SERVICE_POLICY_NAME}


@pytest.mark.asyncio
async def test_users_me_policies_is_not_shadowed_by_the_admin_route(client, created_emails):
    """Registration-order regression guard: /users/me/policies must not be
    swallowed by /users/{user_email}/policies (which would otherwise try
    to look up a real user named "me" and 404, or require policies:read)."""
    email = _unique_email()
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/authorization/users/me/policies")

    assert resp.status_code == 200
    assert resp.json()["user_email"] == email  # never the literal string "me"


# ---------------------------- Effective authorization / inspection ----------------------------

@pytest.mark.asyncio
async def test_authorization_check_reports_allowed_and_granting_policy(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(
        client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME]
    )
    await _create_system_user(client, created_emails, system_email)

    resp = await client.post(
        f"/authorization/users/{target_email}/authorization-check",
        json={"action": "users:list_all", "resource_type": "users"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorized"] is True
    assert USER_ADMINISTRATION_POLICY_NAME in body["granting_policies"]
    assert USER_ADMINISTRATION_POLICY_NAME in body["candidate_policies"]


@pytest.mark.asyncio
async def test_authorization_check_reports_denied_with_no_candidate_policy(client, created_emails):
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    resp = await client.post(
        f"/authorization/users/{target_email}/authorization-check",
        json={"action": "users:list_all", "resource_type": "users"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorized"] is False
    assert body["granting_policies"] == []
    assert body["candidate_policies"] == []


@pytest.mark.asyncio
async def test_authorization_check_distinguishes_candidate_from_granting_when_conditions_fail(
    client, created_emails
):
    # A policy can be a "candidate" (matches action + resource_type) while
    # still failing the actual grant because its conditions reject this
    # specific resource; the inspection endpoint's whole point is
    # surfacing that distinction (see evaluate_detailed's docstring).
    system_email = _unique_email("system")
    target_email = _unique_email("target")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    conditioned_policy_name = _unique_policy_name()
    create_resp = await client.post(
        "/authorization/policies",
        json={
            "name": conditioned_policy_name,
            "actions": ["documents:publish"],
            "resource_type": "documents",
            "conditions": {"resource_attributes": {"status": "draft"}},
        },
    )
    assert create_resp.status_code == 201

    assign_resp = await client.post(
        f"/authorization/users/{target_email}/policies",
        json={"policy_name": conditioned_policy_name},
    )
    assert assign_resp.status_code == 200

    # Resource fails the condition (already published, not draft)
    denied_resp = await client.post(
        f"/authorization/users/{target_email}/authorization-check",
        json={
            "action": "documents:publish",
            "resource_type": "documents",
            "resource": {"status": "published"},
        },
    )
    assert denied_resp.status_code == 200
    denied_body = denied_resp.json()
    assert denied_body["authorized"] is False
    assert conditioned_policy_name in denied_body["candidate_policies"]
    assert conditioned_policy_name not in denied_body["granting_policies"]

    # Same policy, resource this time satisfies the condition
    allowed_resp = await client.post(
        f"/authorization/users/{target_email}/authorization-check",
        json={
            "action": "documents:publish",
            "resource_type": "documents",
            "resource": {"status": "draft"},
        },
    )
    assert allowed_resp.status_code == 200
    allowed_body = allowed_resp.json()
    assert allowed_body["authorized"] is True
    assert conditioned_policy_name in allowed_body["granting_policies"]
