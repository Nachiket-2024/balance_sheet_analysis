#!/usr/bin/env bash
# Copies every KEY=VALUE from OLD_FILE into NEW_FILE, for keys present in
# both, skipping a fixed list of fields setup-env.sh generates fresh
# (secrets, plus the DB URLs that embed them) and the app name/brand color
# it just prompted for. Also skips any field you listed in
# scripts/app/env-tools/rotate-secrets/fields.env, since a field safe to
# rotate by editing the file is exactly a field that shouldn't be copied
# forward from an old one either - see that file's own header.
#
# Never prints a value, only key names: every line this script writes to
# stdout is safe to appear in an AI coding agent's own tool output/context,
# since the actual secret literals never pass through it. This is the
# building block scripts/upstream-sync's agent workflow uses to copy a
# real GOOGLE_CLIENT_SECRET/GMAIL_APP_PASSWORD/etc. from an old env file
# into a freshly regenerated one without an agent ever reading them - see
# docs/mystic_auth/template-usage/syncing-upstream/agent-prompt.md.
#
# Usage: scripts/mystic_auth/env-tools/copy-env-values/copy-env-values.sh OLD_FILE NEW_FILE
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../../.."

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 OLD_FILE NEW_FILE" >&2
  exit 1
fi

OLD_FILE="$1"
NEW_FILE="$2"

[ -f "$OLD_FILE" ] || { echo "Not found: $OLD_FILE" >&2; exit 1; }
[ -f "$NEW_FILE" ] || { echo "Not found: $NEW_FILE" >&2; exit 1; }

EXCLUDED_KEYS=(
  SECRET_KEY
  BUGSINK_SECRET_KEY
  POSTGRES_PASSWORD
  APP_DB_PASSWORD
  BUGSINK_SUPERUSER_PASSWORD
  DATABASE_URL
  APP_DATABASE_URL
  APP_NAME
  BRAND_COLOR
  VITE_APP_NAME
  VITE_BRAND_COLOR
)

APP_FIELDS_FILE="scripts/app/env-tools/rotate-secrets/fields.env"
if [ -f "$APP_FIELDS_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    [[ "$line" == *=* ]] || continue
    EXCLUDED_KEYS+=("${line%%=*}")
  done < "$APP_FIELDS_FILE"
fi

is_excluded() {
  local k="$1"
  for e in "${EXCLUDED_KEYS[@]}"; do
    [ "$k" = "$e" ] && return 0
  done
  return 1
}

copied=()
not_in_new=()
preserved_new_defaults=()

tmp="$(mktemp)"
cp "$NEW_FILE" "$tmp"

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    ''|'#'*) continue ;;
  esac
  [[ "$line" == *=* ]] || continue
  key="${line%%=*}"
  value="${line#*=}"

  is_excluded "$key" && continue

  # Keep a newly introduced production default when the old env file is blank.
  if [ "$key" = "BACKUP_UPLOAD_COMMAND" ] && [ -z "$value" ]; then
    new_line="$(grep -m1 "^${key}=" "$tmp" || true)"
    new_value="${new_line#*=}"
    if [ -n "$new_line" ] && [ -n "$new_value" ]; then
      preserved_new_defaults+=("$key")
      continue
    fi
  fi

  if grep -q "^${key}=" "$tmp"; then
    awk -v key="$key" -v val="$value" '
      BEGIN { pattern = "^" key "=" }
      $0 ~ pattern { print key "=" val; next }
      { print }
    ' "$tmp" > "${tmp}.next"
    mv "${tmp}.next" "$tmp"
    copied+=("$key")
  else
    not_in_new+=("$key")
  fi
done < "$OLD_FILE"

mv "$tmp" "$NEW_FILE"

ALL_FIELDS=("${copied[@]}" "${not_in_new[@]}")

echo "Copied from $OLD_FILE into $NEW_FILE (values not shown):"
echo

if [ "${#ALL_FIELDS[@]}" -eq 0 ]; then
  echo "(nothing to copy)"
else
  FIELD_WIDTH=5
  for key in "${ALL_FIELDS[@]}"; do
    [ "${#key}" -gt "$FIELD_WIDTH" ] && FIELD_WIDTH="${#key}"
  done
  NO_WIDTH="${#ALL_FIELDS[@]}"
  NO_WIDTH="${#NO_WIDTH}"
  [ "$NO_WIDTH" -lt 3 ] && NO_WIDTH=3

  printf '%-*s  %-*s  Copied\n' "$NO_WIDTH" "No." "$FIELD_WIDTH" "Field"
  n=0
  for key in "${copied[@]}"; do
    n=$((n + 1))
    printf '%-*d  %-*s  Yes\n' "$NO_WIDTH" "$n" "$FIELD_WIDTH" "$key"
  done
  for key in "${not_in_new[@]}"; do
    n=$((n + 1))
    printf '%-*d  %-*s  No\n' "$NO_WIDTH" "$n" "$FIELD_WIDTH" "$key"
  done

  echo
  echo "${#copied[@]} of ${#ALL_FIELDS[@]} field(s) copied."
  if [ "${#not_in_new[@]}" -gt 0 ]; then
    echo "\"No\" means present in $OLD_FILE but not in $NEW_FILE - upstream may have dropped or renamed it, review by hand."
  fi
fi

echo
echo "Not copied on purpose (freshly generated/prompted by setup-env): ${EXCLUDED_KEYS[*]}"
if [ "${#preserved_new_defaults[@]}" -gt 0 ]; then
  echo "Preserved non-blank defaults because the old value was blank (review): ${preserved_new_defaults[*]}"
fi
