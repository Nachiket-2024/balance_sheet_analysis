#!/usr/bin/env bash
# Rotates SECRET_KEY and/or BUGSINK_SECRET_KEY in place in one or more real
# env/mystic_auth/.env* files, generating a fresh random value for each.
# Also rotates any of your own env/app/ secret fields declared in
# scripts/app/env-tools/rotate-secrets/fields.env - see that file's own
# header. Ships empty, so by default this script only ever touches the two
# mystic_auth fields below.
#
# Scope is deliberately narrow: these two fields are the only secrets safe
# to rotate by just editing the file and restarting. Every other secret
# field (POSTGRES_PASSWORD, APP_DB_PASSWORD, BUGSINK_SUPERUSER_PASSWORD,
# VALKEY_PASSWORD) is backed by state a live service already has: Postgres
# only applies POSTGRES_PASSWORD on first volume init, so editing the file
# after that does nothing to the role's real password and just breaks
# DATABASE_URL; Bugsink's admin password lives in its own database, not
# this file. Rotating those safely means changing them at the live service
# (ALTER ROLE, Bugsink's own admin tools) first, not something this script
# attempts. The same reasoning applies to whatever you list in
# fields.env - only list a field there if editing the file and restarting
# is genuinely enough to rotate it.
#
# Usage:
#   scripts/mystic_auth/env-tools/rotate-secrets/rotate-secrets.sh [--field NAME] [file ...]
#
# With no file arguments, rotates every env/mystic_auth/.env* file, plus
# every env/app/.env* file if fields.env declares at least one field.
# With no --field, rotates every applicable field wherever present in a
# given file.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../../.."

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required to generate secrets." >&2
  exit 1
fi

gen_secret() {
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

# mystic_auth's own fields (fixed lengths, always in scope) plus whatever
# a fork declared in its own fields.env (name:length pairs).
declare -A FIELD_LENGTHS=(
  [SECRET_KEY]=40
  [BUGSINK_SECRET_KEY]=60
)

APP_FIELDS_FILE="scripts/app/env-tools/rotate-secrets/fields.env"
if [ -f "$APP_FIELDS_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    length="${line#*=}"
    [ -n "$length" ] || length=40
    FIELD_LENGTHS["$key"]="$length"
  done < "$APP_FIELDS_FILE"
fi

FIELD=""
FILES=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --field)
      FIELD="$2"
      shift 2
      ;;
    *)
      FILES+=("$1")
      shift
      ;;
  esac
done

if [ -n "$FIELD" ] && [ -z "${FIELD_LENGTHS[$FIELD]+set}" ]; then
  echo "Unknown --field '$FIELD'. Known fields: ${!FIELD_LENGTHS[*]}." >&2
  echo "Add your own to scripts/app/env-tools/rotate-secrets/fields.env to extend this." >&2
  exit 1
fi

if [ "${#FILES[@]}" -eq 0 ]; then
  # Globs rather than a fixed list, so a fork's own new mode (e.g. a
  # hand-added env/mystic_auth/.env.staging) is rotated too.
  GLOB_DIRS=("env/mystic_auth")
  [ -f "$APP_FIELDS_FILE" ] && GLOB_DIRS+=("env/app")
  for dir in "${GLOB_DIRS[@]}"; do
    for candidate in "$dir"/.env*; do
      case "$candidate" in
        *.example|*.bak|*.ci-created) continue ;;
      esac
      [ -f "$candidate" ] && FILES+=("$candidate")
    done
  done
fi

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "No env files found to rotate. Run scripts/mystic_auth/env-tools/setup-env/setup-env.sh first." >&2
  exit 1
fi

ROTATED_ANY=0

for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "skip (not found): $f"
    continue
  fi

  rotated_here=()

  for key in "${!FIELD_LENGTHS[@]}"; do
    if { [ -z "$FIELD" ] || [ "$FIELD" = "$key" ]; } && grep -q "^${key}=" "$f"; then
      sed_inplace "s|^${key}=.*|${key}=$(gen_secret "${FIELD_LENGTHS[$key]}")|" "$f"
      rotated_here+=("$key")
    fi
  done

  if [ "${#rotated_here[@]}" -gt 0 ]; then
    echo "rotated in $f: ${rotated_here[*]}"
    ROTATED_ANY=1
  else
    echo "nothing to rotate in $f"
  fi
done

if [ "$ROTATED_ANY" -eq 1 ]; then
  echo
  echo "Restart whichever stack reads the rotated file(s) for the new value to take effect."
  echo "Rotating SECRET_KEY invalidates every outstanding access/refresh token and session:"
  echo "everyone gets logged out. Rotating BUGSINK_SECRET_KEY invalidates Bugsink's own"
  echo "signed sessions/cookies the same way."
fi
