# tests/backend/mystic_auth/integration/audit_log/test_audit_log_query_edge_cases_integration.py
#
# Boundary/edge-case coverage for GET /authorization/audit-log, split out
# from test_audit_log_query_api_integration.py: pagination past the end of
# the result set, an unrecognized sort_by, and the limit query param's
# validated bounds.
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)

from .audit_log_test_accounts import (
    _cleanup_audit_log,
    create_system_user,
    create_verified_user,
    poll_for_entries,
    unique_email,
)

PASSWORD = "StrongPass123!"

__all__ = ["_cleanup_audit_log"]


@pytest.mark.asyncio
async def test_offset_past_the_end_of_results_returns_an_empty_list_not_an_error(client, created_emails):
    system_email = unique_email("audit-offset-sys")
    await create_system_user(client, created_emails, system_email)

    resp = await client.get("/authorization/audit-log", params={"limit": 100, "offset": 10_000_000})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_unrecognized_sort_by_falls_back_instead_of_erroring(client, created_emails):
    system_email = unique_email("audit-badsort-sys")
    await create_system_user(client, created_emails, system_email)

    resp = await client.get(
        "/authorization/audit-log", params={"sort_by": "not_a_real_column; drop table users;"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_limit_above_the_documented_maximum_is_rejected(client, created_emails):
    system_email = unique_email("audit-maxlimit-sys")
    await create_system_user(client, created_emails, system_email)

    resp = await client.get("/authorization/audit-log", params={"limit": 1001})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_limit_at_the_documented_maximum_is_accepted(client, created_emails):
    system_email = unique_email("audit-maxlimit-ok-sys")
    await create_system_user(client, created_emails, system_email)

    resp = await client.get("/authorization/audit-log", params={"limit": 1000})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_negative_offset_is_rejected(client, created_emails):
    system_email = unique_email("audit-negoffset-sys")
    await create_system_user(client, created_emails, system_email)

    resp = await client.get("/authorization/audit-log", params={"offset": -1})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_my_audit_log_offset_past_the_end_returns_an_empty_list(client, created_emails):
    email = unique_email("audit-myoffset")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    async def _fetch():
        resp = await client.get("/authorization/audit-log/me")
        assert resp.status_code == 200
        return resp.json()

    await poll_for_entries(_fetch, lambda es: len(es) >= 1)

    resp = await client.get("/authorization/audit-log/me", params={"offset": 10_000_000})
    assert resp.status_code == 200
    assert resp.json() == []
