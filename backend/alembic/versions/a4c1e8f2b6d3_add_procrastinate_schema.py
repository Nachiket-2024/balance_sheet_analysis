"""add procrastinate schema

Revision ID: a4c1e8f2b6d3
Revises: e5f6a7b8c9d0
Create Date: 2026-08-19 00:00:00.000000

Applies Procrastinate's own packaged schema SQL (procrastinate_jobs,
procrastinate_events, procrastinate_periodic_defers and their supporting
functions/triggers), read directly from the installed `procrastinate`
package rather than hand-transcribed, so it always matches the pinned
version's actual schema. Corresponds to procrastinate==3.10.0's
`procrastinate/sql/schema.sql`.

Replaces taskiq (Valkey Streams): background jobs now live as rows in this
same Postgres database instead of a separate Valkey broker. See
backend/mystic_auth/procrastinate_tasks/.
"""
from collections.abc import Sequence
from importlib import resources

import psycopg

from mystic_auth.core.settings import settings

revision: str = "a4c1e8f2b6d3"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _run_multi_statement_sql(sql: str) -> None:
    """Applies a raw, possibly multi-statement (including dollar-quoted
    CREATE FUNCTION/DO block) SQL script.

    Not done via `op.execute()`: env.py's async engine goes through
    SQLAlchemy's asyncpg dialect, which always prepares statements before
    executing them, and asyncpg refuses to prepare a string containing more
    than one command ("cannot insert multiple commands into a prepared
    statement") - fatal for a multi-statement script like Procrastinate's
    packaged schema.sql. A separate, synchronous psycopg connection (the
    same driver Procrastinate itself uses) runs the whole script as one
    simple-protocol query instead, sidestepping that restriction entirely.
    Reuses the same DATABASE_URL this migration run is already targeting,
    via the same postgresql+asyncpg -> postgresql translation
    settings.procrastinate_database_url applies for the running app.
    """
    with psycopg.connect(settings.procrastinate_database_url) as conn:
        conn.execute(sql)


def upgrade() -> None:
    schema_sql = resources.files("procrastinate").joinpath("sql/schema.sql").read_text()
    _run_multi_statement_sql(schema_sql)


def downgrade() -> None:
    # Function/procedure names carry versioned suffixes (_v1, _v2, ...) that
    # change across Procrastinate releases, so rather than hand-listing every
    # one (and having this downgrade silently rot on the next schema bump),
    # drop every routine and table this schema could plausibly have created
    # by querying the catalog for anything named procrastinate_*.
    _run_multi_statement_sql(
        """
        DO $$
        DECLARE
            r record;
        BEGIN
            FOR r IN
                SELECT p.oid::regprocedure AS signature, p.prokind
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate\\_%'
            LOOP
                EXECUTE format(
                    'DROP %s IF EXISTS %s CASCADE',
                    CASE r.prokind WHEN 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END,
                    r.signature
                );
            END LOOP;
        END $$;

        DROP TABLE IF EXISTS procrastinate_events CASCADE;
        DROP TABLE IF EXISTS procrastinate_periodic_defers CASCADE;
        DROP TABLE IF EXISTS procrastinate_jobs CASCADE;
        DROP TABLE IF EXISTS procrastinate_workers CASCADE;
        DROP TYPE IF EXISTS procrastinate_job_status CASCADE;
        DROP TYPE IF EXISTS procrastinate_job_event_type CASCADE;
        DROP TYPE IF EXISTS procrastinate_job_to_defer_v1 CASCADE;
        """
    )
