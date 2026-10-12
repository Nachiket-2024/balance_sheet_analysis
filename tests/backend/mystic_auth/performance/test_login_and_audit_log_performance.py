# tests/backend/mystic_auth/performance/test_login_and_audit_log_performance.py
#
# Two more hot paths, same generous-threshold smoke-level intent as
# test_authorization_performance.py: concurrent login (connection pool /
# password hashing under parallel load) and the audit log listing endpoint
# against a large table (proves the composite user_email/created_at index
# is actually used rather than a sort step or table scan).
import asyncio
import time

import pytest

from backend.mystic_auth.auth.password_logic.password_service import password_service
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)
from tests.backend.mystic_auth.security.conftest import PASSWORD, create_verified_user

from .conftest import (
    bulk_seed_audit_log,
    bulk_seed_verified_users,
    cleanup_perftest_rows,
    unique_tag,
)

# Argon2 verification is deliberately CPU/memory expensive. A 5s absolute
# budget was below the normal variance of WSL2 and shared GitHub runners for
# 25 concurrent verifications, creating false alarms without indicating
# request serialization. Keep this as an advisory regression ceiling rather
# than weakening the password-hashing parameters.
_CONCURRENT_LOGIN_MAX_SECONDS = 10.0
_AUDIT_LOG_LIST_MAX_SECONDS = 3.0
_CONCURRENT_LOGINS = 25
_MANY_AUDIT_ROWS = 5000
_SECURITY_AUDIT_READ_POLICIES = [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME]


@pytest.mark.asyncio
async def test_concurrent_logins_stay_fast(client):
    """N distinct users logging in at once must not serialize on a shared
    resource (DB connection pool, password hashing threadpool): total
    wall time for all of them in parallel should stay close to one
    login's time, not N times it. Users are seeded directly (like
    bulk_seed_users), not via signup/verify-account: this test measures
    login, and the HTTP signup/verify dance is both slow (deliberately
    expensive password hashing on signup too) and irrelevant here."""
    tag = unique_tag()
    hashed_password = await password_service.hash_password(PASSWORD)
    emails = await bulk_seed_verified_users(_CONCURRENT_LOGINS, tag, hashed_password)
    try:
        start = time.perf_counter()
        responses = await asyncio.gather(
            *(client.post("/auth/login", json={"email": email, "password": PASSWORD}) for email in emails)
        )
        elapsed = time.perf_counter() - start

        assert all(resp.status_code == 200 for resp in responses)
        assert elapsed < _CONCURRENT_LOGIN_MAX_SECONDS, f"took {elapsed:.3f}s for {_CONCURRENT_LOGINS} concurrent logins"
    finally:
        await cleanup_perftest_rows(tag)


@pytest.mark.asyncio
async def test_audit_log_listing_stays_fast_with_many_rows(client, created_emails):
    """The system-wide audit log listing (used by the Audit Log page) must
    stay fast as the table grows large: proves get_all's default
    created_at/id ordering rides an index rather than a table-wide sort."""
    tag = unique_tag()
    await bulk_seed_audit_log(_MANY_AUDIT_ROWS, tag)
    try:
        email = f"auditperf_{tag}@example.com"
        await create_verified_user(client, created_emails, email, _SECURITY_AUDIT_READ_POLICIES)

        start = time.perf_counter()
        resp = await client.get("/audit/security-log", params={"limit": 100})
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < _AUDIT_LOG_LIST_MAX_SECONDS, f"took {elapsed:.3f}s with {_MANY_AUDIT_ROWS} audit rows"
    finally:
        await cleanup_perftest_rows(tag)


@pytest.mark.asyncio
async def test_audit_log_filtered_search_stays_fast_with_many_rows(client, created_emails):
    """Same as above but with the ILIKE user_email search filter active,
    the most expensive filter this endpoint supports."""
    tag = unique_tag()
    await bulk_seed_audit_log(_MANY_AUDIT_ROWS, tag)
    try:
        email = f"auditsearchperf_{tag}@example.com"
        await create_verified_user(client, created_emails, email, _SECURITY_AUDIT_READ_POLICIES)

        start = time.perf_counter()
        resp = await client.get("/audit/security-log", params={"limit": 100, "search": "auditsearchperf"})
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < _AUDIT_LOG_LIST_MAX_SECONDS, f"took {elapsed:.3f}s searching {_MANY_AUDIT_ROWS} audit rows"
    finally:
        await cleanup_perftest_rows(tag)
