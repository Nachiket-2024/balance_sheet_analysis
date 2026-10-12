# tests/backend/mystic_auth/performance/conftest.py
#
# Shares the same real-dependency fixtures (client, created_emails, Valkey
# isolation) as tests/backend/integration/ and tests/backend/security/ :
# performance tests run against the same real Postgres/Valkey, seeded with
# realistic bulk volume via direct SQL (seeding hundreds of rows through
# the HTTP API one at a time would itself dominate the timing being
# measured).
import uuid

from sqlalchemy import text

from backend.mystic_auth.database.connection import database


def unique_tag() -> str:
    return uuid.uuid4().hex[:12]


async def bulk_seed_users(count: int, tag: str) -> list[str]:
    """Inserts `count` verified, active users directly (bypassing signup's
    password hashing, which is deliberately slow : irrelevant to what
    these tests measure) and returns their emails."""
    emails = [f"perftest_{tag}_{i}@example.com" for i in range(count)]
    async with database.async_session() as session:
        await session.execute(
            text(
                "INSERT INTO users (name, email, hashed_password, role, is_verified, is_active, created_at, updated_at) "
                "SELECT 'Perf User ' || i, 'perftest_' || :tag || '_' || i || '@example.com', NULL, 'user', true, true, now(), now() "
                "FROM generate_series(0, :count - 1) AS i"
            ),
            {"tag": tag, "count": count},
        )
        await session.commit()
    return emails


async def bulk_seed_verified_users(count: int, tag: str, hashed_password: str) -> list[str]:
    """Same as bulk_seed_users, but with a real, login-able password hash,
    for load tests that need to authenticate as the seeded users (e.g.
    concurrent login), not just have them exist as background rows."""
    emails = [f"perftest_{tag}_{i}@example.com" for i in range(count)]
    async with database.async_session() as session:
        await session.execute(
            text(
                "INSERT INTO users (name, email, hashed_password, role, is_verified, is_active, created_at, updated_at) "
                "SELECT 'Perf User ' || i, 'perftest_' || :tag || '_' || i || '@example.com', :hashed_password, "
                "'user', true, true, now(), now() FROM generate_series(0, :count - 1) AS i"
            ),
            {"tag": tag, "count": count, "hashed_password": hashed_password},
        )
        await session.commit()
    return emails


async def bulk_seed_policies(count: int, tag: str, resource_type: str = "perftest_resource") -> list[str]:
    names = [f"perftest_policy_{tag}_{i}" for i in range(count)]
    async with database.async_session() as session:
        await session.execute(
            text(
                "INSERT INTO policies (name, description, actions, resource_type, conditions, is_active, created_at, updated_at, created_by) "
                "SELECT 'perftest_policy_' || :tag || '_' || i, 'perf', ARRAY['perftest:action_' || i], :resource_type, NULL, true, now(), now(), 'perftest' "
                "FROM generate_series(0, :count - 1) AS i"
            ),
            {"tag": tag, "count": count, "resource_type": resource_type},
        )
        await session.commit()
    return names


async def bulk_assign_policies_to_user(email: str, policy_names: list[str]) -> None:
    async with database.async_session() as session:
        await session.execute(
            text(
                "INSERT INTO user_policies (user_id, policy_id, assigned_at, assigned_by) "
                "SELECT (SELECT id FROM users WHERE email = :email), p.id, now(), 'perftest' "
                "FROM policies p WHERE p.name = ANY(:policy_names)"
            ),
            {"email": email, "policy_names": policy_names},
        )
        await session.commit()


async def cleanup_perftest_rows(tag: str) -> None:
    async with database.async_session() as session:
        await session.execute(
            text(
                "DELETE FROM user_policies WHERE user_id IN (SELECT id FROM users WHERE email LIKE :pattern)"
            ),
            {"pattern": f"perftest_{tag}_%"},
        )
        await session.execute(text("DELETE FROM users WHERE email LIKE :pattern"), {"pattern": f"perftest_{tag}_%"})
        await session.execute(
            text("DELETE FROM policies WHERE name LIKE :pattern"), {"pattern": f"perftest_policy_{tag}_%"}
        )
        await session.execute(
            text("DELETE FROM security_audit_log WHERE request_id LIKE :pattern"), {"pattern": f"perftest_{tag}_%"}
        )
        await session.commit()


async def bulk_seed_audit_log(count: int, tag: str, user_email: str | None = None) -> None:
    """Inserts `count` security_audit_log rows directly. request_id carries
    the tag so cleanup_perftest_rows can find and delete them; real rows
    never look like `perftest_<tag>_<i>`, so this can't collide."""
    async with database.async_session() as session:
        await session.execute(
            text(
                "INSERT INTO security_audit_log "
                "(user_email, event_type, success, ip_address, request_id, created_at) "
                "SELECT :user_email, "
                "CASE WHEN i % 5 = 0 THEN 'login_failure' ELSE 'login_success' END, "
                "i % 5 != 0, '203.0.113.' || (i % 255), 'perftest_' || :tag || '_' || i, "
                "now() - (i || ' seconds')::interval "
                "FROM generate_series(0, :count - 1) AS i"
            ),
            {"tag": tag, "count": count, "user_email": user_email},
        )
        await session.commit()
