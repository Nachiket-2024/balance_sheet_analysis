#!/usr/bin/env bash
# Regression test for the env-file tooling (setup-env, check-env,
# rotate-secrets, set-env-field, copy-env-values), run against a throwaway
# copy of the repo's env/ and frontend/ trees under a temp dir. Never
# touches this repo's own real env files. Run manually after touching any
# of those scripts:
#   tests/scripts/mystic_auth/env-tools/test-env-tooling.sh
#
# Covers the real bug found manually during development: setup-env's and
# rotate-secrets' shared sed_inplace helper used to delete a caller's own
# env/mystic_auth/.env.dev.bak by colliding with sed -i.bak's own transient backup file.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
BASE="$(mktemp -d)"
trap 'rm -rf "$BASE"' EXIT

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

# Fresh copy of just what these scripts touch: the .example files, the
# scripts themselves (so relative script-to-repo-root paths still resolve
# the same way), and an empty frontend/ dir for frontend/.env.
mkdir -p "$BASE/env" "$BASE/frontend" "$BASE/scripts/mystic_auth/env-tools"
mkdir -p "$BASE/env/mystic_auth" "$BASE/env/app"
cp "$REPO_ROOT"/env/mystic_auth/.env*.example "$BASE/env/mystic_auth/"
cp "$REPO_ROOT"/env/app/.env*.example "$BASE/env/app/"
cp "$REPO_ROOT"/frontend/.env.example "$BASE/frontend/"
cp -r "$REPO_ROOT"/scripts/mystic_auth/env-tools/setup-env "$REPO_ROOT"/scripts/mystic_auth/env-tools/check-env \
      "$REPO_ROOT"/scripts/mystic_auth/env-tools/rotate-secrets "$REPO_ROOT"/scripts/mystic_auth/env-tools/set-env-field \
      "$REPO_ROOT"/scripts/mystic_auth/env-tools/copy-env-values "$BASE/scripts/mystic_auth/env-tools/"
chmod +x "$BASE"/scripts/mystic_auth/env-tools/*/*.sh
cd "$BASE"

# A downstream project may choose a product database name. Generation must
# derive URL paths from POSTGRES_DB rather than preserving the template's
# technical default.
sed -i.tmp 's/^POSTGRES_DB=.*/POSTGRES_DB=example_app_db/' env/mystic_auth/.env.dev.example
rm -f env/mystic_auth/.env.dev.example.tmp
sed -i.tmp 's/^APP_NAME=.*/APP_NAME=Example App/' env/mystic_auth/.env.dev.example
rm -f env/mystic_auth/.env.dev.example.tmp

echo "=== setup-env: bootstraps every file, skips none that don't exist yet ==="
printf 'TestApp\n\n' | scripts/mystic_auth/env-tools/setup-env/setup-env.sh >/dev/null
for f in env/mystic_auth/.env.dev env/mystic_auth/.env.prod env/mystic_auth/.env.local-prod-cloudflare env/mystic_auth/.env.local-prod-ngrok env/mystic_auth/.env.local-prod-tailscale frontend/.env; do
  [ -f "$f" ] || fail "setup-env: $f was not created"
done
pass "setup-env: created every expected file"

for f in env/mystic_auth/.env.dev env/mystic_auth/.env.prod env/mystic_auth/.env.local-prod-cloudflare env/mystic_auth/.env.local-prod-ngrok env/mystic_auth/.env.local-prod-tailscale env/app/.env.dev env/app/.env.prod frontend/.env; do
  if grep -q '^BRAND_COLOR=' "$f"; then
    grep -q '^BRAND_COLOR=#b5533c$' "$f" || fail "setup-env: $f has the wrong default BRAND_COLOR"
  fi
  if grep -q '^VITE_BRAND_COLOR=' "$f"; then
    grep -q '^VITE_BRAND_COLOR=#b5533c$' "$f" || fail "setup-env: $f has the wrong default VITE_BRAND_COLOR"
  fi
done
pass "setup-env: default brand color matches the canonical MysticAuth color"

DEV_SECRET_1="$(grep '^SECRET_KEY=' env/mystic_auth/.env.dev | cut -d= -f2)"
PROD_SECRET="$(grep '^SECRET_KEY=' env/mystic_auth/.env.prod | cut -d= -f2)"
[ "$DEV_SECRET_1" != "$PROD_SECRET" ] || fail "setup-env: SECRET_KEY reused across files"
pass "setup-env: SECRET_KEY is distinct per file"

PG_PW="$(grep '^POSTGRES_PASSWORD=' env/mystic_auth/.env.dev | cut -d= -f2)"
grep -q "postgres:${PG_PW}@" <(grep '^DATABASE_URL=' env/mystic_auth/.env.dev) || fail "setup-env: DATABASE_URL password out of sync with POSTGRES_PASSWORD"
pass "setup-env: DATABASE_URL password matches generated POSTGRES_PASSWORD"
grep -q '^DATABASE_URL=.*\/example_app_db$' env/mystic_auth/.env.dev || fail "setup-env: DATABASE_URL did not use POSTGRES_DB"
grep -q '^APP_DATABASE_URL=.*\/example_app_db$' env/mystic_auth/.env.dev || fail "setup-env: APP_DATABASE_URL did not use POSTGRES_DB"
pass "setup-env: database URLs use the configured POSTGRES_DB"
grep -q '^APP_NAME=TestApp$' env/mystic_auth/.env.dev || fail "setup-env: explicit branding prompt was not applied"

echo "=== setup-env: never overwrites an existing file ==="
BEFORE_DEV_FILE="$(cat env/mystic_auth/.env.dev)"
printf '\n\n' | scripts/mystic_auth/env-tools/setup-env/setup-env.sh >/dev/null
[ "$(cat env/mystic_auth/.env.dev)" = "$BEFORE_DEV_FILE" ] || fail "setup-env: overwrote an existing file"
pass "setup-env: left an existing file untouched"

# Regression test for the sed -i.bak / env/mystic_auth/.env.dev.bak collision bug.
cp env/mystic_auth/.env.local-prod-cloudflare.example env/mystic_auth/.env.local-prod-cloudflare.bak
echo "CANARY=should-survive" >> env/mystic_auth/.env.local-prod-cloudflare.bak
rm env/mystic_auth/.env.local-prod-cloudflare
printf '\n\n' | scripts/mystic_auth/env-tools/setup-env/setup-env.sh >/dev/null
grep -q "^CANARY=should-survive$" env/mystic_auth/.env.local-prod-cloudflare.bak \
  || fail "setup-env: a caller's own .bak file was clobbered (sed -i.bak collision regression)"
pass "setup-env: a caller's own .bak file survives (sed -i.bak collision regression guard)"
rm env/mystic_auth/.env.local-prod-cloudflare.bak

echo ""
echo "=== check-env: clean file only warns on shipped placeholders ==="
if scripts/mystic_auth/env-tools/check-env/check-env.sh env/mystic_auth/.env.dev > /tmp/check-env-out.$$; then
  grep -q "WARNING" /tmp/check-env-out.$$ || fail "check-env: expected placeholder warnings, got none"
  pass "check-env: exits 0 with placeholder warnings on a freshly generated dev file"
else
  fail "check-env: unexpectedly failed on a freshly generated dev file"
fi
rm -f /tmp/check-env-out.$$

echo "=== check-env: fails on a placeholder secret + ENVIRONMENT=production ==="
cp env/mystic_auth/.env.prod.example env/mystic_auth/.env.prod.broken
sed -i.tmp 's/^ENVIRONMENT=.*/ENVIRONMENT=production/' env/mystic_auth/.env.prod.broken && rm -f env/mystic_auth/.env.prod.broken.tmp
if scripts/mystic_auth/env-tools/check-env/check-env.sh env/mystic_auth/.env.prod.broken > /tmp/check-env-out2.$$ 2>&1; then
  fail "check-env: should have failed on an un-rotated production file"
else
  grep -q "ERROR" /tmp/check-env-out2.$$ || fail "check-env: failed, but without an ERROR line"
  pass "check-env: fails on a placeholder secret with ENVIRONMENT=production"
fi
rm -f /tmp/check-env-out2.$$ env/mystic_auth/.env.prod.broken

echo "=== check-env: fails early on incomplete production backup configuration ==="
cp env/mystic_auth/.env.prod env/mystic_auth/.env.prod.backup-test
sed -i.tmp 's/^BACKUP_ENCRYPTION_KEY=.*/BACKUP_ENCRYPTION_KEY=/' env/mystic_auth/.env.prod.backup-test && rm -f env/mystic_auth/.env.prod.backup-test.tmp
sed -i.tmp 's/^BACKUP_UPLOAD_COMMAND=.*/BACKUP_UPLOAD_COMMAND=/' env/mystic_auth/.env.prod.backup-test && rm -f env/mystic_auth/.env.prod.backup-test.tmp
if scripts/mystic_auth/env-tools/check-env/check-env.sh env/mystic_auth/.env.prod.backup-test > /tmp/check-env-backup.$$ 2>&1; then
  fail "check-env: should have failed on blank production backup prerequisites"
fi
grep -q "BACKUP_ENCRYPTION_KEY is blank" /tmp/check-env-backup.$$ || fail "check-env: did not identify blank BACKUP_ENCRYPTION_KEY"
grep -q "BACKUP_UPLOAD_COMMAND is blank" /tmp/check-env-backup.$$ || fail "check-env: did not identify blank BACKUP_UPLOAD_COMMAND"
pass "check-env: fails early with actionable production backup errors"
sed -i.tmp 's/^BACKUP_ENCRYPTION_KEY=.*/BACKUP_ENCRYPTION_KEY=generated-test-key/' env/mystic_auth/.env.prod.backup-test && rm -f env/mystic_auth/.env.prod.backup-test.tmp
sed -i.tmp 's/^BACKUP_UPLOAD_COMMAND=.*/BACKUP_UPLOAD_COMMAND=rclone copy "$${DUMP_FILE}" b2:example\/backups/' env/mystic_auth/.env.prod.backup-test && rm -f env/mystic_auth/.env.prod.backup-test.tmp
if scripts/mystic_auth/env-tools/check-env/check-env.sh env/mystic_auth/.env.prod.backup-test > /tmp/check-env-backup-valid.$$ 2>&1; then
  pass "check-env: accepts a production backup command that references DUMP_FILE"
else
  cat /tmp/check-env-backup-valid.$$ >&2
  fail "check-env: rejected a valid DUMP_FILE-referencing backup command"
fi
rm -f /tmp/check-env-backup.$$ /tmp/check-env-backup-valid.$$ env/mystic_auth/.env.prod.backup-test

echo "=== check-env: warns about a leftover .bak file ==="
cp env/mystic_auth/.env.dev env/mystic_auth/.env.dev.bak
if scripts/mystic_auth/env-tools/check-env/check-env.sh env/mystic_auth/.env.dev > /tmp/check-env-out3.$$; then
  grep -q "env/mystic_auth/.env.dev.bak still exists" /tmp/check-env-out3.$$ || fail "check-env: did not warn about a leftover env/mystic_auth/.env.dev.bak"
  pass "check-env: warns about a leftover .bak file"
else
  fail "check-env: unexpectedly failed just from a leftover .bak file existing"
fi
rm -f /tmp/check-env-out3.$$ env/mystic_auth/.env.dev.bak

echo ""
echo "=== check-env: warns about a blank/invalid BUGSINK_SUPERUSER_EMAIL ==="
# Regression guard: a blank/invalid value here isn't just insecure, it's a
# hard startup failure - Bugsink's own prestart hook rejects it and
# crash-loops, taking backend/frontend down with it via depends_on. Found
# live: this exact failure reproduced against a real docker-compose up.
cp env/mystic_auth/.env.dev env/mystic_auth/.env.dev.emailtest
sed -i.tmp 's/^BUGSINK_SUPERUSER_EMAIL=.*/BUGSINK_SUPERUSER_EMAIL=/' env/mystic_auth/.env.dev.emailtest && rm -f env/mystic_auth/.env.dev.emailtest.tmp
if scripts/mystic_auth/env-tools/check-env/check-env.sh env/mystic_auth/.env.dev.emailtest > /tmp/check-env-out4.$$; then
  grep -q "BUGSINK_SUPERUSER_EMAIL is blank or not a valid email" /tmp/check-env-out4.$$ || fail "check-env: did not warn about a blank BUGSINK_SUPERUSER_EMAIL"
  pass "check-env: warns about a blank BUGSINK_SUPERUSER_EMAIL"
else
  fail "check-env: unexpectedly failed just from a blank BUGSINK_SUPERUSER_EMAIL"
fi
sed -i.tmp 's/^BUGSINK_SUPERUSER_EMAIL=.*/BUGSINK_SUPERUSER_EMAIL=not-an-email/' env/mystic_auth/.env.dev.emailtest && rm -f env/mystic_auth/.env.dev.emailtest.tmp
if scripts/mystic_auth/env-tools/check-env/check-env.sh env/mystic_auth/.env.dev.emailtest > /tmp/check-env-out5.$$; then
  grep -q "BUGSINK_SUPERUSER_EMAIL is blank or not a valid email" /tmp/check-env-out5.$$ || fail "check-env: did not warn about a malformed BUGSINK_SUPERUSER_EMAIL"
  pass "check-env: warns about a malformed (no @/domain) BUGSINK_SUPERUSER_EMAIL"
else
  fail "check-env: unexpectedly failed just from a malformed BUGSINK_SUPERUSER_EMAIL"
fi
rm -f /tmp/check-env-out4.$$ /tmp/check-env-out5.$$ env/mystic_auth/.env.dev.emailtest

echo ""
echo "=== rotate-secrets: rotates SECRET_KEY/BUGSINK_SECRET_KEY, leaves other secrets alone ==="
BEFORE_PG="$(grep '^POSTGRES_PASSWORD=' env/mystic_auth/.env.dev)"
scripts/mystic_auth/env-tools/rotate-secrets/rotate-secrets.sh env/mystic_auth/.env.dev >/dev/null
DEV_SECRET_2="$(grep '^SECRET_KEY=' env/mystic_auth/.env.dev | cut -d= -f2)"
[ "$DEV_SECRET_2" != "$DEV_SECRET_1" ] || fail "rotate-secrets: SECRET_KEY did not change"
pass "rotate-secrets: SECRET_KEY rotated"
AFTER_PG="$(grep '^POSTGRES_PASSWORD=' env/mystic_auth/.env.dev)"
[ "$BEFORE_PG" = "$AFTER_PG" ] || fail "rotate-secrets: touched POSTGRES_PASSWORD, which is out of scope"
pass "rotate-secrets: left POSTGRES_PASSWORD untouched"

echo ""
echo "=== set-env-field: direct KEY=VALUE mode, special characters survive ==="
scripts/mystic_auth/env-tools/set-env-field/set-env-field.sh 'FROM_EMAIL=team@example.com' 'SUPPORT_EMAIL=a/b&c=d' >/dev/null
grep -qx "FROM_EMAIL=team@example.com" env/mystic_auth/.env.dev || fail "set-env-field: FROM_EMAIL not set in env/mystic_auth/.env.dev"
grep -qx "FROM_EMAIL=team@example.com" env/mystic_auth/.env.prod || fail "set-env-field: FROM_EMAIL not propagated to env/mystic_auth/.env.prod"
grep -qx 'SUPPORT_EMAIL=a/b&c=d' env/mystic_auth/.env.dev || fail "set-env-field: special characters mangled"
pass "set-env-field: direct mode sets fields across files, special characters intact"

echo "=== set-env-field: file-based mode skips blank fields ==="
cp scripts/mystic_auth/env-tools/set-env-field/shared-values.env.example scripts/mystic_auth/env-tools/set-env-field/shared-values.env
sed -i.tmp 's/^GOOGLE_CLIENT_ID=.*/GOOGLE_CLIENT_ID=file-mode-id/' scripts/mystic_auth/env-tools/set-env-field/shared-values.env
sed -i.tmp 's/^GEOIPUPDATE_ACCOUNT_ID=.*/GEOIPUPDATE_ACCOUNT_ID=file-mode-maxmind-id/' scripts/mystic_auth/env-tools/set-env-field/shared-values.env
sed -i.tmp 's/^USER_EXPORT_MAX_ROWS=.*/USER_EXPORT_MAX_ROWS=25000/' scripts/mystic_auth/env-tools/set-env-field/shared-values.env
sed -i.tmp 's/^BUGSINK_SUPERUSER_EMAIL=.*/BUGSINK_SUPERUSER_EMAIL=ops@example.com/' scripts/mystic_auth/env-tools/set-env-field/shared-values.env
rm -f scripts/mystic_auth/env-tools/set-env-field/shared-values.env.tmp
BEFORE_BUGSINK_PW="$(grep '^BUGSINK_SUPERUSER_PASSWORD=' env/mystic_auth/.env.dev)"
scripts/mystic_auth/env-tools/set-env-field/set-env-field.sh >/dev/null
grep -qx "GOOGLE_CLIENT_ID=file-mode-id" env/mystic_auth/.env.dev || fail "set-env-field: filled-in shared-values.env field not applied"
grep -qx "GEOIPUPDATE_ACCOUNT_ID=file-mode-maxmind-id" env/mystic_auth/.env.prod || fail "set-env-field: geolocation field not applied to a prod-shaped file"
grep -qx "USER_EXPORT_MAX_ROWS=25000" env/mystic_auth/.env.prod || fail "set-env-field: operational tuning field not applied"
grep -qx "BUGSINK_SUPERUSER_EMAIL=ops@example.com" env/mystic_auth/.env.prod || fail "set-env-field: BUGSINK_SUPERUSER_EMAIL not applied to a prod-shaped file"
[ "$(grep '^BUGSINK_SUPERUSER_PASSWORD=' env/mystic_auth/.env.dev)" = "$BEFORE_BUGSINK_PW" ] || fail "set-env-field: shared-values.env's excluded BUGSINK_SUPERUSER_PASSWORD was somehow touched"
grep -qx "GMAIL_APP_PASSWORD=<your_gmail_app_password>" env/mystic_auth/.env.dev || fail "set-env-field: blank shared-values.env field was applied anyway"
pass "set-env-field: file-based mode applies filled fields, skips blank ones"
rm -f scripts/mystic_auth/env-tools/set-env-field/shared-values.env

echo ""
echo "=== copy-env-values: copies real fields, skips freshly generated secrets ==="
cp env/mystic_auth/.env.dev env/mystic_auth/.env.dev.bak
sed -i.tmp 's/^SUPPORT_EMAIL=.*/SUPPORT_EMAIL=copied-value@example.com/' env/mystic_auth/.env.dev.bak && rm -f env/mystic_auth/.env.dev.bak.tmp
sed -i.tmp 's/^SECRET_KEY=.*/SECRET_KEY=SHOULD_NOT_SURVIVE/' env/mystic_auth/.env.dev.bak && rm -f env/mystic_auth/.env.dev.bak.tmp
scripts/mystic_auth/env-tools/copy-env-values/copy-env-values.sh env/mystic_auth/.env.dev.bak env/mystic_auth/.env.dev >/dev/null
grep -qx "SUPPORT_EMAIL=copied-value@example.com" env/mystic_auth/.env.dev || fail "copy-env-values: real field was not copied"
grep -qx "SECRET_KEY=SHOULD_NOT_SURVIVE" env/mystic_auth/.env.dev && fail "copy-env-values: copied an excluded (freshly generated) field" || pass "copy-env-values: excluded field left untouched"
pass "copy-env-values: non-excluded field copied from old file into new one"
rm -f env/mystic_auth/.env.dev.bak

cp env/mystic_auth/.env.prod.example env/mystic_auth/.env.prod.old-default-test
cp env/mystic_auth/.env.prod.example env/mystic_auth/.env.prod.new-default-test
sed -i.tmp 's/^BACKUP_UPLOAD_COMMAND=.*/BACKUP_UPLOAD_COMMAND=/' env/mystic_auth/.env.prod.old-default-test && rm -f env/mystic_auth/.env.prod.old-default-test.tmp
sed -i.tmp 's|^BACKUP_UPLOAD_COMMAND=.*|BACKUP_UPLOAD_COMMAND=rclone copyto "\$${DUMP_FILE}" b2:example/backups|' env/mystic_auth/.env.prod.new-default-test && rm -f env/mystic_auth/.env.prod.new-default-test.tmp
scripts/mystic_auth/env-tools/copy-env-values/copy-env-values.sh env/mystic_auth/.env.prod.old-default-test env/mystic_auth/.env.prod.new-default-test >/tmp/copy-env-default-test.log
grep -q 'BACKUP_UPLOAD_COMMAND' /tmp/copy-env-default-test.log || fail "copy-env-values: preserved default was not reported"
grep -q 'rclone copyto' env/mystic_auth/.env.prod.new-default-test || fail "copy-env-values: blank old hook overwrote new default"
pass "copy-env-values: blank old backup hook preserves new default"
rm -f env/mystic_auth/.env.prod.old-default-test env/mystic_auth/.env.prod.new-default-test /tmp/copy-env-default-test.log

echo ""
echo "All env-tooling regression checks passed."
