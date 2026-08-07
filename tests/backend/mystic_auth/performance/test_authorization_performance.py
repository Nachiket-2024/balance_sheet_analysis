# tests/backend/mystic_auth/performance/test_authorization_performance.py
#
# Real-DB smoke-level performance coverage (many users and many
# policies, large authorization batches"). These are regression alarms
# against gross performance regressions (e.g. an accidental N+1, or a
# missing index), not a precise load-testing/benchmarking framework, so
# thresholds are deliberately generous.
import time
import uuid

import pytest
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.authorization.schemas.batch_authorization_schema import (
    MAX_BATCH_SIZE,
)

from tests.backend.mystic_auth.security.conftest import create_verified_user

from .conftest import (
    bulk_assign_policies_to_user,
    bulk_seed_policies,
    bulk_seed_users,
    cleanup_perftest_rows,
    unique_tag,
)

# Generous thresholds: these exist to catch a gross regression (e.g. an
# accidental N+1 query, or a dropped index), not to enforce a strict SLA.
_SINGLE_CHECK_MAX_SECONDS = 2.0
_LIST_POLICIES_MAX_SECONDS = 3.0
_LARGE_BATCH_MAX_SECONDS = 5.0

_MANY_USERS = 2000
_MANY_POLICIES = 200


@pytest.mark.asyncio
async def test_authorization_check_stays_fast_with_many_background_users(client, created_emails):
    """A real user's own authorization check must not slow down as the
    total users table grows: proves get_active_policies_for_user's join
    stays index-based rather than degrading toward a table scan."""
    tag = unique_tag()
    await bulk_seed_users(_MANY_USERS, tag)
    try:
        email = f"realuser_{tag}@example.com"
        await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

        start = time.perf_counter()
        resp = await client.get("/users/me")
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < _SINGLE_CHECK_MAX_SECONDS, f"took {elapsed:.3f}s with {_MANY_USERS} background users"
    finally:
        await cleanup_perftest_rows(tag)


@pytest.mark.asyncio
async def test_listing_policies_stays_reasonable_with_many_policies(client, created_emails):
    tag = unique_tag()
    await bulk_seed_policies(_MANY_POLICIES, tag)
    try:
        system_email = f"sysuser_{tag}@example.com"
        # Reuse the security suite's system-user helper indirectly: build
        # it here since it needs system_superuser + user_administration
        # too, not just self_service.
        from backend.mystic_auth.authorization.policies.default_policies import (
            SYSTEM_SUPERUSER_POLICY_NAME,
            USER_ADMINISTRATION_POLICY_NAME,
        )
        await create_verified_user(
            client, created_emails, system_email,
            [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
        )

        start = time.perf_counter()
        resp = await client.get("/authorization/policies")
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert len(resp.json()) >= _MANY_POLICIES
        assert elapsed < _LIST_POLICIES_MAX_SECONDS, f"took {elapsed:.3f}s with {_MANY_POLICIES} policies"
    finally:
        await cleanup_perftest_rows(tag)


@pytest.mark.asyncio
async def test_authorization_check_stays_fast_for_a_user_holding_many_policies(client, created_emails):
    """The 'many policies' scaling axis from the user's own side: holding
    dozens of assigned policies must not make evaluating one action slow:
    proves the evaluator's linear scan over a user's own (small) policy
    list is cheap, and fetching it is still one indexed query regardless
    of how many *other* policies exist system-wide."""
    tag = unique_tag()
    policy_names = await bulk_seed_policies(_MANY_POLICIES, tag)
    try:
        email = f"manypolicies_{tag}@example.com"
        await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])
        await bulk_assign_policies_to_user(email, policy_names)

        start = time.perf_counter()
        resp = await client.get("/users/me")
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < _SINGLE_CHECK_MAX_SECONDS, (
            f"took {elapsed:.3f}s for a user holding {_MANY_POLICIES} policies"
        )
    finally:
        await cleanup_perftest_rows(tag)


@pytest.mark.asyncio
async def test_large_authorization_batch_completes_quickly(client, created_emails):
    """MAX_BATCH_SIZE checks in one request: proves authorize_batch's
    single policy-fetch-then-loop design scales linearly in pure in-memory
    work, not in database round trips."""
    email = f"batchperf_{uuid.uuid4().hex}@example.com"
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    checks = [{"action": "users:read_own", "resource_type": "users"} for _ in range(MAX_BATCH_SIZE)]

    start = time.perf_counter()
    resp = await client.post("/authorization/batch-check", json={"checks": checks})
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    assert len(resp.json()["results"]) == MAX_BATCH_SIZE
    assert elapsed < _LARGE_BATCH_MAX_SECONDS, f"took {elapsed:.3f}s for a {MAX_BATCH_SIZE}-check batch"
