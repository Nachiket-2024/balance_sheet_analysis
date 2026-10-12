#!/usr/bin/env bash
# Regression test for backend-host-run.sh's host URL derivation. Uses fake
# executables and a temporary env tree so it never starts services or reads the
# repository's real env files.
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin" "$TMP/backend" "$TMP/env/mystic_auth" "$TMP/env/app"

cat > "$TMP/env/mystic_auth/.env.dev" <<'EOF'
POSTGRES_HOST_PORT=15432
VALKEY_HOST_PORT=16379
DATABASE_URL=postgresql+asyncpg://postgres:12345@postgres:5432/example_app_db
APP_DATABASE_URL=postgresql+asyncpg://mystic_auth_app:67890@postgres:5432/example_app_db
VALKEY_URL=redis://valkey:6379/0
EOF
touch "$TMP/env/app/.env.dev"

cat > "$TMP/bin/docker" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

cat > "$TMP/bin/alembic" <<'EOF'
#!/usr/bin/env bash
case "$DATABASE_URL" in
  postgresql+asyncpg://postgres:12345@localhost:15432/example_app_db) ;;
  *) exit 1 ;;
esac
case "$APP_DATABASE_URL" in
  postgresql+asyncpg://mystic_auth_app:67890@localhost:15432/example_app_db) ;;
  *) exit 1 ;;
esac
case "$VALKEY_URL" in
  redis://localhost:16379/0) ;;
  *) exit 1 ;;
esac
EOF

cat > "$TMP/bin/uvicorn" <<'EOF'
#!/usr/bin/env bash
case "$DATABASE_URL" in
  *'@localhost:15432/'*) ;;
  *) exit 1 ;;
esac
case "$VALKEY_URL" in
  *'//localhost:16379/'*) ;;
  *) exit 1 ;;
esac
exit 0
EOF
chmod +x "$TMP/bin/docker" "$TMP/bin/alembic" "$TMP/bin/uvicorn"

BACKEND_HOST_RUN_ROOT="$TMP" PATH="$TMP/bin:$PATH" \
  "$BASE/scripts/mystic_auth/docker/dev/backend-host-run.sh" --port 8765
echo "PASS: backend-host-run derives host URLs from configured ports without touching env files"
