# tests/backend/mystic_auth/integration/user_test_accounts.py
#
# Real signed-up, verified, policy-holding test accounts (via the actual
# HTTP surface: signup -> verify -> login), shared by
# test_user_self_service_routes_integration.py,
# test_user_list_and_update_integration.py, and
# test_user_account_lifecycle_integration.py: all three need the same tiers
# (plain user, admin, system, roleless) and the same refresh-token-cookie
# manipulation to simulate stale/reused/forged tokens.
import uuid

from backend.mystic_auth.auth.password_logic.password_service import password_service
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.redis.client import redis_client
from backend.mystic_auth.user_crud.user_crud_collector import user_crud
from backend.mystic_auth.user_table.user_model import UserRole

PASSWORD = "StrongPass123!"


def unique_email(prefix: str = "inttest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


# conftest.py's `client` fixture uses base_url="https://testserver", a
# dotless hostname, which CPython's http.cookiejar (what httpx's cookie jar
# is built on) normalizes to "testserver.local" internally for matching
# purposes. Cookies set manually here must match that (domain, path, name)
# key exactly, or they land as a second, separate jar entry instead of
# overwriting the real one from a prior response, see
# post_with_refresh_cookie's docstring below for why that matters.
_TEST_COOKIE_DOMAIN = "testserver.local"


async def post_with_refresh_cookie(client, url: str, refresh_token: str):
    """Posts to a refresh_token-cookie-gated endpoint with an explicit cookie
    value, independent of whatever the client's shared cookie jar currently
    holds, needed to simulate stale/reused/forged/cross-session tokens.
    httpx deprecated per-request `cookies=` in favor of setting cookies on
    the client itself, hence setting it here rather than passing `cookies=`.
    Both domain and path must match the real cookie's (see
    _TEST_COOKIE_DOMAIN above): the jar keys cookies by (domain, path,
    name), so an inexact match creates a second entry alongside the real one
    instead of overwriting it, which then survives the endpoint's own
    cookie-clearing response untouched."""
    client.cookies.set("refresh_token", refresh_token, domain=_TEST_COOKIE_DOMAIN, path="/auth")
    return await client.post(url)


async def assign_policies(email: str, policy_names: list[str]) -> None:
    """Grants real capability the same way the policy management API
    would (see backend/mystic_auth/api/pbac_routes/policy_assignment_routes.py):
    this is the ONLY thing that determines what an account can do under PBAC."""
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        for policy_name in policy_names:
            policy = await policy_repository.get_by_name(policy_name, session)
            await policy_repository.assign_policy_to_user(
                user_id=user.id, policy_id=policy.id, db=session, assigned_by="test"
            )


async def create_verified_user(
    client, created_emails, email: str, role: UserRole = UserRole.user, policy_names: list[str] | None = None
):
    """Signs up and verifies a user. `role` is set purely as display/
    grouping metadata (and, for system_email, to trigger the target-account
    protection invariant in user_management_update_routes.py/user_lifecycle_routes.py; see their module docstrings for
    why that's not an authorization decision). `policy_names` is what
    actually grants capability; defaults to just self_service, mirroring
    what real signup does (see signup_service.py)."""
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    if role != UserRole.user:
        async with database.async_session() as session:
            user = await user_crud.get_by_email(email, session)
            await user_crud.update_role(user, role, session)

    await assign_policies(email, policy_names if policy_names is not None else [SELF_SERVICE_POLICY_NAME])

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200
    return login_resp


async def create_admin(client, created_emails, email: str):
    return await create_verified_user(
        client, created_emails, email,
        role=UserRole.admin,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME],
    )


async def create_system_user(client, created_emails, email: str):
    return await create_verified_user(
        client, created_emails, email,
        role=UserRole.system,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


async def create_roleless_user(created_emails, email: str, policy_names: list[str]) -> None:
    """Creates a fully real, loggable-in account with role=None directly
    (signup_service always sets role="user" for display purposes, so a
    genuinely roleless account can only be produced this way today; there
    is no API to clear an existing role, which is out of scope here)."""
    async with database.async_session() as session:
        hashed_password = await password_service.hash_password(PASSWORD)
        user = await user_crud.create({
            "name": "Roleless User",
            "email": email,
            "hashed_password": hashed_password,
            "role": None,
            "is_verified": True,
            "is_active": True,
        }, session)
        created_emails.append(email)

        for policy_name in policy_names:
            policy = await policy_repository.get_by_name(policy_name, session)
            await policy_repository.assign_policy_to_user(
                user_id=user.id, policy_id=policy.id, db=session, assigned_by="test"
            )
