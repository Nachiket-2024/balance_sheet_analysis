#!/bin/bash
# Runs automatically on the postgres service's FIRST initialization only
# (the official postgres image executes every script under
# /docker-entrypoint-initdb.d/ exactly once, against a fresh, empty data
# directory — never again after that, even across container restarts).
#
# Creates a second database on the SAME Postgres server/container this
# template already runs, owned by the same $POSTGRES_USER, for the
# optional self-hosted Bugsink error-monitoring service (see
# docs/mystic_auth/error-monitoring/overview.md) to use — so enabling it doesn't require a
# second Postgres container, just a second database on this one.
#
# If you're enabling Bugsink against an ALREADY-INITIALIZED postgres_data
# volume (this script won't retroactively run), create the database
# manually instead:
#   docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "CREATE DATABASE bugsink;"
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE bugsink OWNER "$POSTGRES_USER";
EOSQL
