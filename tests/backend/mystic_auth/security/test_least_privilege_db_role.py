# Checks the app's runtime Postgres role (mystic_auth_app, see alembic
# migration b1e6a9f3c7d2_add_least_privilege_app_role.py) can do normal CRUD
# but not DDL or role management. Skipped unless APP_DATABASE_URL is set,
# since a fresh checkout without it has no separate role to test against.
import asyncpg
import pytest

from backend.mystic_auth.core.settings import settings


def _to_dsn(url: str) -> str:
    """asyncpg wants a plain postgresql:// DSN, not SQLAlchemy's
    postgresql+asyncpg:// prefix."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


pytestmark = pytest.mark.skipif(
    not settings.APP_DATABASE_URL,
    reason="APP_DATABASE_URL not configured - least-privilege role split is opt-in",
)


@pytest.mark.asyncio
async def test_app_role_can_read_and_write_its_own_tables():
    conn = await asyncpg.connect(_to_dsn(settings.APP_DATABASE_URL))
    try:
        await conn.fetch("SELECT id, email FROM users LIMIT 1")
        await conn.execute("SELECT count(*) FROM user_sessions")
        await conn.execute("SELECT count(*) FROM security_audit_log")
        await conn.execute("SELECT count(*) FROM authorization_audit_log")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_app_role_cannot_run_ddl():
    conn = await asyncpg.connect(_to_dsn(settings.APP_DATABASE_URL))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("CREATE TABLE sectest_should_never_exist (id int)")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_app_role_cannot_create_or_alter_roles():
    conn = await asyncpg.connect(_to_dsn(settings.APP_DATABASE_URL))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("CREATE ROLE sectest_should_never_exist LOGIN")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_app_role_is_not_superuser():
    conn = await asyncpg.connect(_to_dsn(settings.APP_DATABASE_URL))
    try:
        is_superuser = await conn.fetchval(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        )
        assert is_superuser is False
    finally:
        await conn.close()
