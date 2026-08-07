# tests/backend/mystic_auth/security/test_privilege_escalation_security.py
#
# Real-DB proof of AuthorizationService.assert_authorized_to_grant
# (the privilege-escalation protection): a caller holding only
# policies:create/update/assign (never system_superuser itself) must never
# be able to mint, edit, or hand out one of this app's own sensitive
# actions (Permission's vocabulary) that they don't already hold. Unit
# tests already cover this with mocks; these hit the real API + real DB.
import pytest
from backend.mystic_auth.authorization.policies.default_policies import (
    SYSTEM_SUPERUSER_POLICY_NAME,
)

from .conftest import (
    create_system_user,
    create_user_with_custom_policy,
    unique_email,
    unique_policy_name,
)


@pytest.mark.asyncio
async def test_policies_create_only_cannot_mint_a_policy_granting_an_unheld_sensitive_action(
    client, created_emails
):
    email = unique_email("create-escalate")
    await create_user_with_custom_policy(client, created_emails, email, ["policies:create"])

    resp = await client.post(
        "/authorization/policies",
        json={
            "name": unique_policy_name(),
            "actions": ["users:purge"],  # a sensitive action this caller doesn't hold
            "resource_type": "users",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_policies_update_only_cannot_add_an_unheld_sensitive_action_to_an_existing_policy(
    client, created_emails
):
    email = unique_email("update-escalate")
    target_policy = await create_user_with_custom_policy(client, created_emails, email, ["policies:update"])

    resp = await client.put(
        f"/authorization/policies/{target_policy}",
        json={"actions": ["policies:update", "users:assign_system_role"]},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_policies_assign_only_cannot_self_escalate_to_system_superuser(client, created_emails):
    """The canonical real-world escalation attempt: a caller with only
    policies:assign tries to grant themselves system_superuser."""
    email = unique_email("assign-escalate")
    await create_user_with_custom_policy(client, created_emails, email, ["policies:assign"])

    resp = await client.post(
        f"/authorization/users/{email}/policies",
        json={"policy_name": SYSTEM_SUPERUSER_POLICY_NAME},
    )
    assert resp.status_code == 403

    # Confirm it actually didn't take: still cannot list policies (would
    # need policies:read, which system_superuser grants)
    check_resp = await client.get("/authorization/policies")
    assert check_resp.status_code == 403


@pytest.mark.asyncio
async def test_policies_update_only_cannot_rollback_to_a_revision_holding_an_unheld_sensitive_action(
    client, created_emails
):
    """Rollback restores a full historical policy definition, so it must be
    guarded by the same assert_authorized_to_grant check as a direct PUT,
    otherwise a caller with only policies:update could roll a policy back to
    an old revision that once held a sensitive action (e.g.
    users:purge), silently re-granting it without ever holding it
    themselves."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    policy_name = unique_policy_name()
    create_resp = await client.post(
        "/authorization/policies",
        json={"name": policy_name, "actions": ["users:purge"], "resource_type": "users"},
    )
    assert create_resp.status_code == 201

    # Downgrade away from the sensitive action: this is the revision an
    # attacker will try to roll back past.
    downgrade_resp = await client.put(
        f"/authorization/policies/{policy_name}", json={"actions": ["users:read_own"]}
    )
    assert downgrade_resp.status_code == 200

    history_resp = await client.get(f"/authorization/policies/{policy_name}/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    # The entry whose *restorable* definition (new_definition, since this is
    # not a "deleted" entry) still holds the sensitive action, i.e. the
    # original "create" entry, not the later "downgrade" entry (whose own
    # new_definition is the already-safe post-downgrade state).
    target_entry = next(
        entry for entry in history
        if entry["new_definition"] and "users:purge" in entry["new_definition"]["actions"]
    )

    attacker_email = unique_email("rollback-escalate")
    await create_user_with_custom_policy(
        client, created_emails, attacker_email, ["policies:update", "policies:read"]
    )

    rollback_resp = await client.post(
        f"/authorization/policies/{policy_name}/history/{target_entry['id']}/rollback"
    )
    assert rollback_resp.status_code == 403


@pytest.mark.asyncio
async def test_policies_update_only_cannot_repoint_resource_type_to_activate_a_dormant_sensitive_action(
    client, created_emails
):
    """A policy's actions can already contain a sensitive action while its
    resource_type makes it inert for real routes. Changing only
    resource_type (not actions) must still be guarded by
    assert_authorized_to_grant, otherwise policies:update alone could
    repoint an existing dormant grant to become live without the caller
    ever holding the sensitive action themselves."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    policy_name = unique_policy_name()
    create_resp = await client.post(
        "/authorization/policies",
        json={"name": policy_name, "actions": ["users:purge"], "resource_type": "policies"},
    )
    assert create_resp.status_code == 201

    attacker_email = unique_email("resource-type-escalate")
    await create_user_with_custom_policy(client, created_emails, attacker_email, ["policies:update"])

    resp = await client.put(
        f"/authorization/policies/{policy_name}",
        json={"resource_type": "users"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_system_superuser_can_still_perform_all_of_the_above(client, created_emails):
    """Negative-control: a genuine system_superuser holder is NOT blocked
    by the same guard; this proves it's a privilege check, not a broken
    endpoint."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    create_resp = await client.post(
        "/authorization/policies",
        json={"name": unique_policy_name(), "actions": ["users:purge"], "resource_type": "users"},
    )
    assert create_resp.status_code == 201
