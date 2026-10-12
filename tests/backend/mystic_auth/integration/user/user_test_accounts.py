# tests/backend/mystic_auth/integration/user/user_test_accounts.py
#
# Shared helpers for creating real test accounts (signup -> verify -> login)
# used by the user integration tests: plain user, admin, system, and
# roleless tiers, plus refresh-token-cookie helpers for simulating
# stale/reused/forged tokens.
import uuid

from backend.mystic_auth.auth.password_logic.password_service import password_service
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud
from backend.mystic_auth.user.user_model import UserRole
from backend.mystic_auth.valkey.client import valkey_client

PASSWORD = "StrongPass123!"


def unique_email(prefix: str = "inttest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


# The `client` fixture uses base_url="https://testserver". Python's
# http.cookiejar normalizes that dotless hostname to "testserver.local", so
# cookies set manually here must use this domain to match the real one
# instead of landing as a separate jar entry.
_TEST_COOKIE_DOMAIN = "testserver.local"


async def post_with_refresh_cookie(client, url: str, refresh_token: str):
    """Posts to a refresh_token-cookie-gated endpoint with an explicit
    cookie value, overriding whatever the client's cookie jar currently
    holds. Used to simulate stale/reused/forged/cross-session tokens. Set
    directly on the client (httpx deprecated per-request `cookies=`), and
    must match the real cookie's domain and path exactly or it creates a
    second jar entry instead of overwriting the real one."""
    client.cookies.set("refresh_token", refresh_token, domain=_TEST_COOKIE_DOMAIN, path="/auth")
    return await client.post(url)


async def assign_policies(email: str, policy_names: list[str]) -> None:
    """Grants capability the same way the policy management API would.
    Under PBAC, this is the only thing that determines what an account can
    do."""
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        for policy_name in policy_names:
            policy = await policy_repository.get_by_name(policy_name, session)
            await policy_repository.assign_policy_to_user(
                user_id=user.id,
                policy_id=policy.id,
                db=session,
                assigned_by="test",
                user_email=email,
            )


async def create_verified_user(
    client, created_emails, email: str, role: UserRole = UserRole.user, policy_names: list[str] | None = None
):
    """Signs up and verifies a user. `role` is display/grouping metadata
    only (it also triggers target-account protection for system users; see
    user_management_update_routes.py). `policy_names` is what actually
    grants capability; defaults to self_service, same as real signup."""
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
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
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME],
    )


async def create_system_user(client, created_emails, email: str):
    return await create_verified_user(
        client, created_emails, email,
        role=UserRole.system,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


async def create_roleless_user(created_emails, email: str, policy_names: list[str]) -> None:
    """Creates a loggable-in account with role=None directly. Signup always
    sets role="user", and there's no API to clear it, so this is the only
    way to get a genuinely roleless account."""
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
                user_id=user.id,
                policy_id=policy.id,
                db=session,
                assigned_by="test",
                user_email=email,
            )
