# Server-side search/resource_type/is_active/sort_by/sort_dir/X-Total-Count
# behavior for GET /authorization/policies, which PoliciesPage.tsx relies on.
import uuid

import pytest

from .authorization_test_accounts import (
    cleanup_test_policies,
    create_system_user,
    unique_email,
    unique_policy_name,
)

__all__ = ["cleanup_test_policies"]


@pytest.mark.asyncio
async def test_list_policies_search_matches_name_or_description_case_insensitively(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    token = uuid.uuid4().hex

    name_match = f"test_policy_namematch_{token}"
    description_match = unique_policy_name()
    no_match = unique_policy_name()

    await client.post(
        "/authorization/policies",
        json={"name": name_match, "actions": ["projects:read"], "resource_type": "projects"},
    )
    await client.post(
        "/authorization/policies",
        json={
            "name": description_match,
            "description": f"mentions {token} in its description",
            "actions": ["projects:read"],
            "resource_type": "projects",
        },
    )
    await client.post(
        "/authorization/policies",
        json={"name": no_match, "actions": ["projects:read"], "resource_type": "projects"},
    )

    # Uppercased, to prove the match is case-insensitive (ILIKE), not just
    # a lucky exact-case substring.
    resp = await client.get("/authorization/policies", params={"search": token.upper(), "limit": 100})
    assert resp.status_code == 200
    matched_names = {p["name"] for p in resp.json()}

    assert matched_names == {name_match, description_match}
    assert no_match not in matched_names


@pytest.mark.asyncio
async def test_list_policies_filters_by_resource_type_exactly(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    token = uuid.uuid4().hex
    resource_type = f"widgets_{token}"

    matching = unique_policy_name()
    other = unique_policy_name()
    await client.post(
        "/authorization/policies",
        json={"name": matching, "actions": ["widgets:read"], "resource_type": resource_type},
    )
    await client.post(
        "/authorization/policies",
        # Same token prefix in the resource_type, but not an exact match -
        # proves this filter is exact-match, not a substring search like
        # `search` above.
        json={"name": other, "actions": ["widgets:read"], "resource_type": f"{resource_type}_other"},
    )

    resp = await client.get("/authorization/policies", params={"resource_type": resource_type, "limit": 100})
    assert resp.status_code == 200
    matched_names = {p["name"] for p in resp.json()}

    assert matched_names == {matching}


@pytest.mark.asyncio
async def test_list_policies_filters_by_is_active(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    active_name = unique_policy_name()
    inactive_name = unique_policy_name()
    await client.post(
        "/authorization/policies",
        json={"name": active_name, "actions": ["projects:read"], "resource_type": "projects"},
    )
    await client.post(
        "/authorization/policies",
        json={"name": inactive_name, "actions": ["projects:read"], "resource_type": "projects"},
    )
    deactivate_resp = await client.put(f"/authorization/policies/{inactive_name}", json={"is_active": False})
    assert deactivate_resp.status_code == 200

    active_resp = await client.get(
        "/authorization/policies", params={"search": "test_policy_", "is_active": True, "limit": 1000}
    )
    inactive_resp = await client.get(
        "/authorization/policies", params={"search": "test_policy_", "is_active": False, "limit": 1000}
    )
    assert active_resp.status_code == 200
    assert inactive_resp.status_code == 200

    active_names = {p["name"] for p in active_resp.json()}
    inactive_names = {p["name"] for p in inactive_resp.json()}

    assert active_name in active_names
    assert active_name not in inactive_names
    assert inactive_name in inactive_names
    assert inactive_name not in active_names


@pytest.mark.asyncio
async def test_list_policies_filters_by_contains_action_exactly(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    token = uuid.uuid4().hex
    target_action = f"widgets_{token}:void"

    matching = unique_policy_name()
    other = unique_policy_name()
    await client.post(
        "/authorization/policies",
        json={"name": matching, "actions": [target_action, "widgets:read"], "resource_type": f"widgets_{token}"},
    )
    await client.post(
        "/authorization/policies",
        # Same resource type prefix, but doesn't grant the target action -
        # proves this filter matches on the actions array, not resource_type.
        json={"name": other, "actions": ["widgets:read"], "resource_type": f"widgets_{token}"},
    )

    resp = await client.get("/authorization/policies", params={"contains_action": target_action, "limit": 100})
    assert resp.status_code == 200
    matched_names = {p["name"] for p in resp.json()}

    assert matched_names == {matching}


@pytest.mark.asyncio
async def test_list_policies_contains_action_x_total_count_matches_filtered_total(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    token = uuid.uuid4().hex
    target_action = f"gadgets_{token}:void"

    await client.post(
        "/authorization/policies",
        json={"name": unique_policy_name(), "actions": [target_action], "resource_type": f"gadgets_{token}"},
    )
    await client.post(
        "/authorization/policies",
        json={"name": unique_policy_name(), "actions": ["gadgets:read"], "resource_type": f"gadgets_{token}"},
    )

    resp = await client.get(
        "/authorization/policies", params={"contains_action": target_action, "limit": 1000}
    )
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "1"
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_policies_sorts_by_name_ascending(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    # Common prefix isolates this test's rows from other entries in the table.
    prefix = f"test_policy_sorttest_{uuid.uuid4().hex}"
    name_a = f"{prefix}_aaa"
    name_b = f"{prefix}_bbb"
    # Created in reverse (b before a) order, so a correct result proves the
    # response is actually sorted, not just returned in insertion order.
    await client.post(
        "/authorization/policies",
        json={"name": name_b, "actions": ["projects:read"], "resource_type": "projects"},
    )
    await client.post(
        "/authorization/policies",
        json={"name": name_a, "actions": ["projects:read"], "resource_type": "projects"},
    )

    resp = await client.get(
        "/authorization/policies",
        params={"search": prefix, "sort_by": "name", "sort_dir": "asc", "limit": 100},
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]

    assert names == [name_a, name_b]


@pytest.mark.asyncio
async def test_list_policies_unrecognized_sort_by_falls_back_to_id_instead_of_erroring(client, created_emails):
    # A request for a non-existent/unsupported sort column must still succeed, not 400/500.
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    resp = await client.get(
        "/authorization/policies", params={"sort_by": "not_a_real_column", "sort_dir": "asc", "limit": 5}
    )

    assert resp.status_code == 200
    assert len(resp.json()) <= 5


@pytest.mark.asyncio
async def test_list_policies_x_total_count_reflects_filtered_total_not_just_this_page(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    prefix = f"test_policy_pagetest_{uuid.uuid4().hex}"
    names = [f"{prefix}_{i}" for i in range(3)]
    for name in names:
        create_resp = await client.post(
            "/authorization/policies",
            json={"name": name, "actions": ["projects:read"], "resource_type": "projects"},
        )
        assert create_resp.status_code == 201

    # One page at a time (limit=1), sorted deterministically by name so each
    # offset lands on a known row.
    seen_names = []
    for offset in range(3):
        resp = await client.get(
            "/authorization/policies",
            params={"search": prefix, "sort_by": "name", "sort_dir": "asc", "limit": 1, "offset": offset},
        )
        assert resp.status_code == 200
        # Reports every matching row (3), not this page's size (1).
        assert resp.headers["x-total-count"] == "3"
        body = resp.json()
        assert len(body) == 1
        seen_names.append(body[0]["name"])

    assert seen_names == names
