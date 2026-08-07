# tests/backend/mystic_auth/integration/test_authorization_check_integration.py
#
# End-to-end coverage for authorization_check_routes.py (backend/
# mystic_auth/api/pbac_routes/) against the real ASGI app, real PostgreSQL,
# and real Redis. Split out of what used to be one 568-line
# test_authorization_routes_integration.py.
import pytest
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)

from .authorization_test_accounts import (
    cleanup_test_policies,
    create_system_user,
    create_verified_user,
    unique_email,
    unique_policy_name,
)

__all__ = ["cleanup_test_policies"]


@pytest.mark.asyncio
async def test_authorization_check_reports_allowed_and_granting_policy(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(
        client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME]
    )
    await create_system_user(client, created_emails, system_email)

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
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

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
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    conditioned_policy_name = unique_policy_name()
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
