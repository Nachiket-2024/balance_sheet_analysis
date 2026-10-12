#!/usr/bin/env python
"""Seed a repeatable development-only user/authorization matrix.

This deliberately talks to the database instead of the HTTP signup/admin
routes: it creates no verification or password-reset email jobs.  Re-running
the script replaces only users whose email starts with ``matrix-``.

Run from the backend container, for example:
  python /repo/local-scripts/mystic_auth/seed-user-permission-matrix.py
"""

import asyncio
from datetime import UTC, datetime
from itertools import product
from secrets import SystemRandom

from argon2 import PasswordHasher
from mystic_auth.database.connection import database
from sqlalchemy import text

PREFIX = "matrix-"
PASSWORD = "MatrixPassw0rd!"

# Keep this realistic: ordinary accounts use one of the two non-system role
# labels.  The nullable role column supports PBAC edge-case tests, but a
# roleless account is not part of this fixture.
ROLES = ("user", "admin")
# Most development users should look like normal, usable accounts in the UI.
# Keep a smaller set of lifecycle edge cases so the filters and bulk actions
# remain represented without letting those edge cases dominate the fixture.
STATUS_PLAN = (
    *((True, True),) * 24,
    *((False, True),) * 4,
    *((True, False),) * 3,
    *((False, False),) * 1,
    # Keep the new policy bundle represented by login-capable accounts for
    # both roles and every direct-grant shape.
    *((True, True),) * 8,
)

POLICY_BUNDLES = (
    (),
    ("self_service",),
    ("self_service", "user_management"),
    ("policy_management", "rate_limit_management"),
    (
        "policy_maintainer",
        "security_audit_access",
        "user_lifecycle",
    ),
)

DIRECT_PERMISSION_BUNDLES = (
    (),
    (("users:read_own", "users"),),
    (("users:list_all", "users"),),
    (("users:read_own", "users"), ("policies:read", "policies")),
)

# The browser matrix's p4 accounts exercise lifecycle administration. Keep
# this contract beside the seed definition so a stale migration cannot turn
# a p4 account into a soft-delete account and make every real-account E2E test
# fail with a misleading permission-matrix diff.
REQUIRED_POLICY_ACTIONS = {
    "user_lifecycle": {"users:delete_any", "users:reactivate"},
}


async def seed() -> None:
    hasher = PasswordHasher()
    password_hash = hasher.hash(PASSWORD)
    random = SystemRandom()

    async with database.async_session() as session, session.begin():
            # The prefix is intentionally narrow so the existing system user
            # and all non-matrix development accounts remain untouched.
            await session.execute(
                text("DELETE FROM users WHERE email LIKE :prefix"),
                {"prefix": f"{PREFIX}%"},
            )

            policies = {
                row.name: row.id
                for row in (
                    await session.execute(
                        text("SELECT id, name FROM policies WHERE is_active = true")
                    )
                ).mappings()
            }

            expected_policies = {
                name for bundle in POLICY_BUNDLES for name in bundle
            }
            missing = expected_policies - policies.keys()
            if missing:
                raise RuntimeError(f"Missing active policies: {sorted(missing)}")
            policy_actions = {
                row.name: set(row.actions or [])
                for row in (
                    await session.execute(
                        text("SELECT name, actions FROM policies WHERE is_active = true")
                    )
                ).mappings()
            }
            for policy_name, required_actions in REQUIRED_POLICY_ACTIONS.items():
                actual_actions = policy_actions.get(policy_name, set())
                if not required_actions.issubset(actual_actions):
                    raise RuntimeError(
                        f"Policy {policy_name!r} has {sorted(actual_actions)}; "
                        f"expected at least {sorted(required_actions)}. "
                        "Run alembic upgrade head before seeding the browser matrix."
                    )

            count = 0
            # Vary the number of copies independently for each combination.
            # This intentionally does not produce a uniform duplicate count.
            # The status plan is indexed across the role/policy/grant matrix:
            # verified active users are the clear majority, with a few
            # unverified and deactivated accounts retained for UI coverage.
            for combination_index, (role, policy_bundle, grants) in enumerate(
                product(ROLES, POLICY_BUNDLES, DIRECT_PERMISSION_BUNDLES)
            ):
                verified, active = STATUS_PLAN[combination_index]
                copy_count = random.randint(1, 4)
                for duplicate in range(1, copy_count + 1):
                    role_code = role
                    state_code = "verified" if verified else "unverified"
                    active_code = "active" if active else "deactivated"
                    email = (
                        f"{PREFIX}{role_code}-{state_code}-{active_code}-"
                        f"p{POLICY_BUNDLES.index(policy_bundle)}-"
                        f"d{DIRECT_PERMISSION_BUNDLES.index(grants)}-copy{duplicate}"
                        "@example.com"
                    )
                    deleted_at = datetime.now(UTC) if not active else None
                    user = (
                        await session.execute(
                            text(
                                """
                                INSERT INTO users
                                    (name, email, hashed_password, role, is_verified,
                                     is_active, brand_color, deleted_at, last_login_at)
                                VALUES
                                    (:name, :email, :password, :role, :verified,
                                     :active, NULL, :deleted_at, NULL)
                                RETURNING id
                                """
                            ),
                            {
                                "name": f"Matrix {role_code} {state_code} {active_code} "
                                f"P{POLICY_BUNDLES.index(policy_bundle)} "
                                f"D{DIRECT_PERMISSION_BUNDLES.index(grants)} copy {duplicate}",
                                "email": email,
                                "password": password_hash,
                                "role": role,
                                "verified": verified,
                                "active": active,
                                "deleted_at": deleted_at,
                            },
                        )
                    ).scalar_one()

                    for policy_name in policy_bundle:
                        await session.execute(
                            text(
                                """
                                INSERT INTO user_policies (user_id, policy_id, assigned_by)
                                VALUES (:user_id, :policy_id, 'matrix-seed')
                                """
                            ),
                            {"user_id": user, "policy_id": policies[policy_name]},
                        )

                    for action, resource_type in grants:
                        await session.execute(
                            text(
                                """
                                INSERT INTO user_permissions
                                    (user_id, action, resource_type, conditions,
                                     is_active, assigned_by)
                                VALUES
                                    (:user_id, :action, :resource_type, NULL,
                                     true, 'matrix-seed')
                                """
                            ),
                            {
                                "user_id": user,
                                "action": action,
                                "resource_type": resource_type,
                            },
                        )
                    count += 1

    print(f"Seeded {count} matrix users.")
    print(f"Login password for every matrix user: {PASSWORD}")
    print("Existing non-matrix users, including the system user, were not changed.")


if __name__ == "__main__":
    asyncio.run(seed())
