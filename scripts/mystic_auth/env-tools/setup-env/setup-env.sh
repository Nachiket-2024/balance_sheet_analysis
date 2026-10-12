#!/usr/bin/env bash
# Bootstraps every env/mystic_auth/.env* and env/app/.env* file (plus
# frontend/.env) from its .example,
# generating a distinct random value for every secret/password field and
# applying one app name / brand color across all of them, plus Google
# OAuth / Gmail sending credentials if you answer those two optional
# prompts. Never touches a file that already exists - safe to re-run
# after filling in your own per-mode fields (domain, tunnel tokens) by
# hand.
#
# See docs/mystic_auth/template-usage/overview.md for what's still yours to
# fill in after this runs.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../../.."

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required to generate secrets." >&2
  exit 1
fi

gen_secret() {
  # $1 = length. Alnum-only so it's always safe embedded in a URL or sed pattern.
  openssl rand -base64 "$(( $1 * 2 ))" | tr -dc 'A-Za-z0-9' | head -c "$1"
}

sed_inplace() {
  # Portable `sed -i` across GNU and BSD sed, via a temp file rather than
  # `-i.bak`: that flag's fixed ".bak" suffix would collide with (and
  # delete) a same-named backup a caller made on purpose, e.g. the
  # env/mystic_auth/.env.dev.bak convention scripts/mystic_auth/env-tools/copy-env-values/ expects.
  local tmp
  tmp="$(mktemp)"
  sed "$1" "$2" > "$tmp" && mv "$tmp" "$2"
}

env_value_from_file() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 0
  awk -F= -v wanted="$key" '$1 == wanted { sub(/^[^=]*=/, ""); value=$0 } END { print value }' "$file"
}

configured_value() {
  local key="$1" value file
  # During an upstream sync the real env files are temporarily .bak files.
  # Prefer the app-owned copy, then the MysticAuth copy, so regeneration does
  # not silently revert a downstream brand or database name to the template
  # defaults before copy-env-values restores the remaining fields.
  for file in env/app/.env.dev.bak env/mystic_auth/.env.dev.bak \
              env/app/.env.dev env/mystic_auth/.env.dev; do
    value="$(env_value_from_file "$file" "$key")"
    if [ -n "$value" ]; then
      printf '%s' "$value"
      return 0
    fi
  done
}

rewrite_database_urls() {
  local file="$1" database_name="$2" tmp
  tmp="$(mktemp)"
  awk -F= -v db="$database_name" '
    /^[# ]*(DATABASE_URL|APP_DATABASE_URL)=/ {
      prefix = substr($0, 1, index($0, "="))
      url = substr($0, index($0, "=") + 1)
      sub(/\/[^\/[:space:]#]+$/, "/" db, url)
      print prefix url
      next
    }
    { print }
  ' "$file" > "$tmp" && mv "$tmp" "$file"
}

APP_NAME_DEFAULT="$(configured_value APP_NAME)"
APP_NAME_DEFAULT="${APP_NAME_DEFAULT:-MysticAuth}"
BRAND_COLOR_DEFAULT="$(configured_value BRAND_COLOR)"
BRAND_COLOR_DEFAULT="${BRAND_COLOR_DEFAULT:-#b5533c}"
read -rp "App name [$APP_NAME_DEFAULT]: " APP_NAME_INPUT || true
APP_NAME_INPUT="${APP_NAME_INPUT:-$APP_NAME_DEFAULT}"
read -rp "Brand color hex [$BRAND_COLOR_DEFAULT]: " BRAND_COLOR_INPUT || true
BRAND_COLOR_INPUT="${BRAND_COLOR_INPUT:-$BRAND_COLOR_DEFAULT}"

# Optional: the two things nothing else in this script can generate for
# you. Skippable (default No) since it's fine to fill these in later by
# hand, or never, if you don't need Google login/outgoing email locally -
# see docs/mystic_auth/template-usage/quickstart.md.
GOOGLE_CLIENT_ID_INPUT=""
GOOGLE_CLIENT_SECRET_INPUT=""
read -rp "Set up Google OAuth now? [y/N]: " SETUP_OAUTH || true
if [[ "$SETUP_OAUTH" =~ ^[Yy] ]]; then
  read -rp "  GOOGLE_CLIENT_ID: " GOOGLE_CLIENT_ID_INPUT || true
  read -rp "  GOOGLE_CLIENT_SECRET: " GOOGLE_CLIENT_SECRET_INPUT || true
fi

FROM_EMAIL_INPUT=""
GMAIL_APP_PASSWORD_INPUT=""
read -rp "Set up email sending now (Gmail)? [y/N]: " SETUP_EMAIL || true
if [[ "$SETUP_EMAIL" =~ ^[Yy] ]]; then
  read -rp "  FROM_EMAIL (Gmail address): " FROM_EMAIL_INPUT || true
  read -rp "  GMAIL_APP_PASSWORD (from https://myaccount.google.com/apppasswords): " GMAIL_APP_PASSWORD_INPUT || true
fi

# src:dst pairs, auto-discovered by globbing every env/{mystic_auth,app}/.env*.example
# rather than a fixed list, so a fork's own new mode (e.g. a hand-added
# env/app/.env.staging.example) gets bootstrapped too, with no edit to this
# upstream-owned script ever required.
PAIRS=()
for src in env/mystic_auth/.env*.example env/app/.env*.example; do
  [ -f "$src" ] || continue
  PAIRS+=("$src:${src%.example}")
done
PAIRS+=("frontend/.env.example:frontend/.env")

STILL_NEEDED=()

for pair in "${PAIRS[@]}"; do
  src="${pair%%:*}"
  dst="${pair##*:}"

  [ -f "$src" ] || continue

  if [ -f "$dst" ]; then
    echo "skip (already exists): $dst"
    continue
  fi

  cp "$src" "$dst"

  # App name / brand color, backend and frontend spellings.
  sed_inplace "s|^APP_NAME=.*|APP_NAME=${APP_NAME_INPUT}|" "$dst"
  sed_inplace "s|^BRAND_COLOR=.*|BRAND_COLOR=${BRAND_COLOR_INPUT}|" "$dst"
  sed_inplace "s|^VITE_APP_NAME=.*|VITE_APP_NAME=${APP_NAME_INPUT}|" "$dst"
  sed_inplace "s|^VITE_BRAND_COLOR=.*|VITE_BRAND_COLOR=${BRAND_COLOR_INPUT}|" "$dst"

  # Only if you answered the OAuth/email prompts above - never overwrites
  # with a blank, so an unanswered prompt leaves the shipped placeholder
  # in place for you to fill in by hand later.
  if [ -n "$GOOGLE_CLIENT_ID_INPUT" ] && grep -q '^GOOGLE_CLIENT_ID=' "$dst"; then
    sed_inplace "s|^GOOGLE_CLIENT_ID=.*|GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID_INPUT}|" "$dst"
  fi
  if [ -n "$GOOGLE_CLIENT_SECRET_INPUT" ] && grep -q '^GOOGLE_CLIENT_SECRET=' "$dst"; then
    sed_inplace "s|^GOOGLE_CLIENT_SECRET=.*|GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET_INPUT}|" "$dst"
  fi
  if [ -n "$FROM_EMAIL_INPUT" ] && grep -q '^FROM_EMAIL=' "$dst"; then
    sed_inplace "s|^FROM_EMAIL=.*|FROM_EMAIL=${FROM_EMAIL_INPUT}|" "$dst"
  fi
  if [ -n "$GMAIL_APP_PASSWORD_INPUT" ] && grep -q '^GMAIL_APP_PASSWORD=' "$dst"; then
    sed_inplace "s|^GMAIL_APP_PASSWORD=.*|GMAIL_APP_PASSWORD=${GMAIL_APP_PASSWORD_INPUT}|" "$dst"
  fi

  # Distinct generated secrets, only for fields that ship a shared
  # "change_me_in_production..." placeholder. Each variable and each file
  # gets its own independently generated value - a leaked dev secret
  # doesn't compromise prod, and Postgres's superuser password never
  # matches the app role's or Bugsink's.
  if grep -q '^POSTGRES_PASSWORD=' "$dst"; then
    PG_PW="$(gen_secret 24)"
    sed_inplace "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PW}|" "$dst"
    sed_inplace "s|postgres:change_me_in_production@|postgres:${PG_PW}@|g" "$dst"
  fi

  if grep -q '^APP_DB_PASSWORD=' "$dst"; then
    APP_PW="$(gen_secret 24)"
    sed_inplace "s|^APP_DB_PASSWORD=.*|APP_DB_PASSWORD=${APP_PW}|" "$dst"
    sed_inplace "s|mystic_auth_app:change_me_in_production@|mystic_auth_app:${APP_PW}@|g" "$dst"
  fi

  # The database name is configuration, not a MysticAuth namespace. Keep
  # every active and commented local DATABASE_URL spelling aligned with the
  # POSTGRES_DB chosen in this file (including non-default names such as
  # example_app_db). Password replacement above intentionally remains separate.
  POSTGRES_DB_VALUE="$(env_value_from_file "$dst" POSTGRES_DB)"
  if [ -n "$POSTGRES_DB_VALUE" ]; then
    rewrite_database_urls "$dst" "$POSTGRES_DB_VALUE"
  fi

  if grep -q '^SECRET_KEY=' "$dst"; then
    sed_inplace "s|^SECRET_KEY=.*|SECRET_KEY=$(gen_secret 40)|" "$dst"
  fi

  if grep -q '^BUGSINK_SECRET_KEY=' "$dst"; then
    sed_inplace "s|^BUGSINK_SECRET_KEY=.*|BUGSINK_SECRET_KEY=$(gen_secret 60)|" "$dst"
  fi

  if grep -q '^BUGSINK_SUPERUSER_PASSWORD=' "$dst"; then
    sed_inplace "s|^BUGSINK_SUPERUSER_PASSWORD=.*|BUGSINK_SUPERUSER_PASSWORD=$(gen_secret 24)|" "$dst"
  fi

  if grep -q '^VALKEY_PASSWORD=' "$dst"; then
    VALKEY_PW="$(gen_secret 32)"
    sed_inplace "s|^VALKEY_PASSWORD=.*|VALKEY_PASSWORD=${VALKEY_PW}|" "$dst"
    if grep -q '^VALKEY_URL=' "$dst"; then
      sed_inplace "s|^VALKEY_URL=.*|VALKEY_URL=redis://:${VALKEY_PW}@valkey:6379/0|" "$dst"
    fi
  fi

  if grep -q '^BACKUP_ENCRYPTION_KEY=' "$dst"; then
    sed_inplace "s|^BACKUP_ENCRYPTION_KEY=.*|BACKUP_ENCRYPTION_KEY=$(gen_secret 64)|" "$dst"
  fi

  echo "created: $dst"

  placeholders="$(grep -oE '<your[a-z_-]*>|<your-domain>' "$dst" | sort -u || true)"
  if [ -n "$placeholders" ]; then
    STILL_NEEDED+=("$dst: $(echo "$placeholders" | tr '\n' ' ')")
  fi
done

echo
echo "Done. Secrets, APP_NAME, and BRAND_COLOR are filled in wherever a new file was created."
if [ "${#STILL_NEEDED[@]}" -gt 0 ]; then
  echo "Still needs your own values (Google OAuth, SMTP, domain, tunnel tokens):"
  for line in "${STILL_NEEDED[@]}"; do
    echo "  - $line"
  done
fi
echo "See docs/mystic_auth/template-usage/overview.md for OAuth/SMTP/tunnel setup."
