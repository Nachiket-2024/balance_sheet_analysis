# Checks that a caller holding only policies:create/update/assign (not
# system_superuser) can't mint, edit, or hand out a sensitive action they
# don't already hold. (Unit tests already cover this with mocks; these hit
# the real API and DB.)
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
            "actions": ["users:delete_any"],  # caller doesn't hold this
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
    """A caller with only policies:assign tries to grant themselves
    system_superuser."""
    email = unique_email("assign-escalate")
    await create_user_with_custom_policy(client, created_emails, email, ["policies:assign"])

    resp = await client.post(
        f"/authorization/users/{email}/policies",
        json={"policy_name": SYSTEM_SUPERUSER_POLICY_NAME},
    )
    assert resp.status_code == 403

    # confirm it didn't take: still can't list policies (needs
    # policies:read, which system_superuser grants)
    check_resp = await client.get("/authorization/policies")
    assert check_resp.status_code == 403


@pytest.mark.asyncio
async def test_policies_update_only_cannot_rollback_to_a_revision_holding_an_unheld_sensitive_action(
    client, created_emails
):
    """Rollback restores a full historical policy definition, so it needs the
    same assert_authorized_to_grant check as a direct PUT. Otherwise a caller
    with only policies:update could roll a policy back to an old revision
    that held a sensitive action, re-granting it without holding it."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    policy_name = unique_policy_name()
    create_resp = await client.post(
        "/authorization/policies",
        json={"name": policy_name, "actions": ["users:delete_any"], "resource_type": "users"},
    )
    assert create_resp.status_code == 201

    # downgrade away from the sensitive action; this is the revision an
    # attacker will try to roll back past
    downgrade_resp = await client.put(
        f"/authorization/policies/{policy_name}", json={"actions": ["users:read_own"]}
    )
    assert downgrade_resp.status_code == 200

    history_resp = await client.get(f"/authorization/policies/{policy_name}/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    # find the entry whose restorable definition (new_definition) still
    # holds the sensitive action: the original "create" entry, not the
    # later "downgrade" one
    target_entry = next(
        entry for entry in history
        if entry["new_definition"] and "users:delete_any" in entry["new_definition"]["actions"]
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
async def test_policies_update_only_cannot_rollback_a_policy_it_does_not_currently_hold(
    client, created_emails
):
    """The other half of the rollback guard: update_policy checks both the
    policy's current actions and the target actions, but rollback used to
    check only the target (post-rollback) actions. A caller holding the
    target actions but not the policy's current actions must still be
    blocked, otherwise policies:update alone could roll a widely-assigned
    policy back to a weaker definition and strip every holder's access."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    policy_name = unique_policy_name()
    # rollback target: a revision granting only a benign action the
    # attacker will hold
    create_resp = await client.post(
        "/authorization/policies",
        json={"name": policy_name, "actions": ["policies:update"], "resource_type": "policies"},
    )
    assert create_resp.status_code == 201

    history_resp = await client.get(f"/authorization/policies/{policy_name}/history")
    assert history_resp.status_code == 200
    target_entry = next(
        entry for entry in history_resp.json()
        if entry["new_definition"] and entry["new_definition"]["actions"] == ["policies:update"]
    )

    # upgrade to the policy's current definition: a sensitive action the
    # attacker will never hold
    upgrade_resp = await client.put(
        f"/authorization/policies/{policy_name}", json={"actions": ["users:delete_any"]}
    )
    assert upgrade_resp.status_code == 200

    attacker_email = unique_email("rollback-strip")
    await create_user_with_custom_policy(
        client, created_emails, attacker_email, ["policies:update", "policies:read"]
    )

    # attacker holds the target actions (policies:update) but not the
    # policy's current actions (users:delete_any): must still be blocked
    rollback_resp = await client.post(
        f"/authorization/policies/{policy_name}/history/{target_entry['id']}/rollback"
    )
    assert rollback_resp.status_code == 403

    # confirm it didn't take: policy is still on its current (sensitive)
    # definition, not rolled back to the attacker-held one
    get_resp = await client.get(f"/authorization/policies/{policy_name}")
    assert get_resp.status_code == 200
    assert get_resp.json()["actions"] == ["users:delete_any"]


@pytest.mark.asyncio
async def test_policies_update_only_cannot_repoint_resource_type_to_activate_a_dormant_sensitive_action(
    client, created_emails
):
    """A policy's actions can already contain a sensitive action while its
    resource_type keeps it inert for real routes. Changing only
    resource_type must still be guarded, otherwise policies:update alone
    could make a dormant grant live without the caller holding it."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    policy_name = unique_policy_name()
    create_resp = await client.post(
        "/authorization/policies",
        json={"name": policy_name, "actions": ["users:delete_any"], "resource_type": "policies"},
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
    """Negative control: a genuine system_superuser holder is not blocked,
    proving this is a privilege check, not a broken endpoint."""
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    create_resp = await client.post(
        "/authorization/policies",
        json={"name": unique_policy_name(), "actions": ["users:delete_any"], "resource_type": "users"},
    )
    assert create_resp.status_code == 201
