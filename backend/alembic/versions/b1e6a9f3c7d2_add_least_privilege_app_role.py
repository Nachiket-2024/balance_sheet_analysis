"""add least-privilege app db role

Revision ID: b1e6a9f3c7d2
Revises: 44a59c2f57a3
Create Date: 2026-08-20 00:00:00.000000

Creates `mystic_auth_app`, a non-superuser Postgres LOGIN role the
request-serving app and background task bodies connect as (via
APP_DATABASE_URL, see core/settings.py and database/connection.py), instead
of the DATABASE_URL role migrations run as (which stays superuser/
DDL-capable). This role gets only CRUD (SELECT/INSERT/UPDATE/DELETE) on
application tables - no CREATE/ALTER/DROP/TRUNCATE, no CREATEROLE/CREATEDB,
no superuser.

This is deliberately *not* Row-Level Security: this app is single-tenant
with no per-row ownership dimension (no tenant_id/org_id anywhere), and all
authorization (including admin overrides) is already fully enforced in
Python by the PBAC engine (authorization/services/authorization_service.py)
against already-fetched rows, not via SQL predicates. Re-deriving that
logic as row policies would duplicate business logic in two places and
risk drift. What this migration buys instead is blast-radius reduction for
anything that reaches Postgres *outside* that one enforced code path - a
compromised dependency reusing the app's live DB connection, a bad
migration/script run by mistake, a leaked runtime credential - none of
which can do schema-destroying DDL or role/privilege escalation with this
role, even though (like any role that needs to serve real app traffic) it
still has full CRUD on the app's own data. See
docs/mystic_auth/security/decisions-infra.md for the full writeup,
including what this does and does not protect against.

Requires the APP_DB_PASSWORD environment variable to be set wherever this
migration runs (e.g. `docker compose run -e APP_DB_PASSWORD=... alembic`) -
the password is read from the environment and bound as a query parameter,
never embedded in this file or logged.
"""
import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1e6a9f3c7d2'
down_revision: str | Sequence[str] | None = '44a59c2f57a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "mystic_auth_app"


def upgrade() -> None:
    password = os.environ.get("APP_DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "APP_DB_PASSWORD must be set in the environment to run this "
            "migration (it sets the password for the new least-privilege "
            f"'{APP_ROLE}' Postgres role). Never stored in this file."
        )

    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    CREATE ROLE {APP_ROLE} LOGIN;
                END IF;
            END
            $$;
            """
        )
    )

    # ALTER ROLE ... PASSWORD is DDL: Postgres doesn't accept a protocol-level
    # bind parameter there (asyncpg/SQLAlchemy would raise a syntax error on
    # "PASSWORD $1"), so the value has to be embedded as a SQL string
    # literal. Escaped by doubling embedded single quotes (the standard SQL
    # string-literal escape), same as Postgres's own quote_literal(). The
    # password itself still never appears in this file - it's read from the
    # environment above, only its already-escaped form is interpolated here.
    escaped_password = password.replace("'", "''")
    op.execute(f"ALTER ROLE {APP_ROLE} WITH PASSWORD '{escaped_password}'")

    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                EXECUTE format('GRANT CONNECT ON DATABASE %I TO {APP_ROLE}', current_database());
            END
            $$;
            """
        )
    )

    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")

    # So tables created by future migrations (run under the DDL-capable
    # DATABASE_URL role) are automatically readable/writable by APP_ROLE
    # without a per-table grant in every future migration.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}"
    )


def downgrade() -> None:
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM {APP_ROLE}', current_database());
            END
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    DROP ROLE {APP_ROLE};
                END IF;
            END
            $$;
            """
        )
    )
