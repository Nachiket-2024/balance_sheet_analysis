#!/usr/bin/env bash
# Sets one or more fields across every real env file that already declares
# each key, leaving every other field untouched. For a value that's the
# same everywhere on purpose (SUPPORT_EMAIL, GOOGLE_CLIENT_ID,
# ...), instead of opening and editing five files by
# hand, one field at a time.
#
# Two ways to use it:
#
#   From a file (no arguments, easiest): copy shared-values.env.example
#   (next to this script) to shared-values.env, fill in whichever fields
#   you want set everywhere with a normal text editor, then run:
#
#     scripts/mystic_auth/env-tools/set-env-field/set-env-field.sh
#
#   For a field you added yourself (one only env/app/ declares), use the
#   parallel scripts/app/env-tools/set-env-field/shared-values.env.example
#   instead - same copy/fill/run steps, ships empty, upstream never edits
#   it. Both files are read in this mode; the app one wins on overlap.
#
#   Nothing here ever puts a value on the command line or asks you to
#   type it into a chat with an AI agent - shared-values.env is gitignored
#   and only this script's own output (field names, never values) needs to
#   be shared with anyone.
#
#   Direct (one-line, scriptable - what docs/agent prompts use):
#
#     scripts/mystic_auth/env-tools/set-env-field/set-env-field.sh KEY1=VALUE1 [KEY2=VALUE2 ...] [file ...]
#
#   Any argument containing "=" is a field assignment (only the first "="
#   splits key from value, so a value can itself contain "="). Any
#   argument without "=" is a target file - so file arguments can appear
#   anywhere, not just at the end.
#
# With no file arguments (either form), targets every env/mystic_auth/.env*
# and env/app/.env* file plus frontend/.env that actually exists. A file
# missing a given KEY= line is
# skipped for that field, not created or appended to - this only ever
# changes a value that's already there.
#
# Uses awk instead of sed so a value is never interpreted as a regex or a
# sed replacement pattern: slashes, ampersands, etc. in a URL or email
# address are safe to pass as-is.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../../.."

declare -A ASSIGNMENTS=()
KEY_ORDER=()
FILES=()

if [ "$#" -eq 0 ]; then
  VALUES_FILE="$SCRIPT_DIR/shared-values.env"
  APP_VALUES_FILE="scripts/app/env-tools/set-env-field/shared-values.env"
  if [ ! -f "$VALUES_FILE" ] && [ ! -f "$APP_VALUES_FILE" ]; then
    echo "No shared-values.env found." >&2
    echo "Copy scripts/mystic_auth/env-tools/set-env-field/shared-values.env.example to" >&2
    echo "scripts/mystic_auth/env-tools/set-env-field/shared-values.env (template fields)" >&2
    echo "and/or scripts/app/env-tools/set-env-field/shared-values.env.example to" >&2
    echo "scripts/app/env-tools/set-env-field/shared-values.env (your own fields)," >&2
    echo "fill in the fields you want set everywhere, then run this again." >&2
    exit 1
  fi

  # Read mystic_auth's file first, then app's - app wins on overlap, same
  # convention as env_file ordering elsewhere in this template.
  for values_file in "$VALUES_FILE" "$APP_VALUES_FILE"; do
    [ -f "$values_file" ] || continue
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in
        ''|'#'*) continue ;;
      esac
      [[ "$line" == *=* ]] || continue
      key="${line%%=*}"
      value="${line#*=}"
      [ -n "$value" ] || continue
      if [ -z "${ASSIGNMENTS[$key]+set}" ]; then
        KEY_ORDER+=("$key")
      fi
      ASSIGNMENTS["$key"]="$value"
    done < "$values_file"
  done

  if [ "${#KEY_ORDER[@]}" -eq 0 ]; then
    echo "Neither shared-values.env has any fields filled in. Edit one, then run this again." >&2
    exit 1
  fi
else
  for arg in "$@"; do
    if [[ "$arg" == *=* ]]; then
      key="${arg%%=*}"
      value="${arg#*=}"
      if ! [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]]; then
        echo "'$key' doesn't look like an env var name (uppercase letters, digits, underscores)." >&2
        exit 1
      fi
      if [ -z "${ASSIGNMENTS[$key]+set}" ]; then
        KEY_ORDER+=("$key")
      fi
      ASSIGNMENTS["$key"]="$value"
    else
      FILES+=("$arg")
    fi
  done

  if [ "${#KEY_ORDER[@]}" -eq 0 ]; then
    echo "No KEY=VALUE arguments given." >&2
    exit 1
  fi
fi

if [ "${#FILES[@]}" -eq 0 ]; then
  # Globs rather than a fixed list, so a fork's own new mode (e.g. a
  # hand-added env/app/.env.staging) is targeted too, with no edit to this
  # upstream-owned script ever required.
  for candidate in env/mystic_auth/.env* env/app/.env* frontend/.env; do
    case "$candidate" in
      *.example|*.bak|*.ci-created) continue ;;
    esac
    [ -f "$candidate" ] && FILES+=("$candidate")
  done
fi

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "No env files found. Run scripts/mystic_auth/env-tools/setup-env/setup-env.sh first." >&2
  exit 1
fi

declare -A SET_IN=()
MISSING_FILES=()

for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    MISSING_FILES+=("$f")
    continue
  fi

  tmp="$(mktemp)"
  cp "$f" "$tmp"
  # Preserve the source file's permission mode when replacing it. A plain
  # cp/mv sequence applies the process umask to the temporary file and can
  # silently turn a mode-600 credential file into mode 644, undoing the
  # secret-hygiene preflight's protection after an otherwise safe field edit.
  file_mode="$(stat -c '%a' "$f" 2>/dev/null || stat -f '%Lp' "$f" 2>/dev/null || true)"
  if [ -n "$file_mode" ]; then
    chmod "$file_mode" "$tmp"
  fi

  for key in "${KEY_ORDER[@]}"; do
    if grep -q "^${key}=" "$tmp"; then
      awk -v key="$key" -v val="${ASSIGNMENTS[$key]}" '
        BEGIN { pattern = "^" key "=" }
        $0 ~ pattern { print key "=" val; next }
        { print }
      ' "$tmp" > "${tmp}.next"
      mv "${tmp}.next" "$tmp"
      SET_IN["$key"]=1
    fi
  done

  mv "$tmp" "$f"
done

if [ "${#MISSING_FILES[@]}" -gt 0 ]; then
  echo "Not found, skipped: ${MISSING_FILES[*]}"
  echo
fi

# Column widths: widest key name (or the "Field" header, whichever is
# longer) and enough digits for the row count, so the table lines up the
# same regardless of how long an individual field name is.
FIELD_WIDTH=5
for key in "${KEY_ORDER[@]}"; do
  [ "${#key}" -gt "$FIELD_WIDTH" ] && FIELD_WIDTH="${#key}"
done
NO_WIDTH="${#KEY_ORDER[@]}"
NO_WIDTH="${#NO_WIDTH}"
[ "$NO_WIDTH" -lt 3 ] && NO_WIDTH=3

printf '%-*s  %-*s  Updated\n' "$NO_WIDTH" "No." "$FIELD_WIDTH" "Field"

UPDATED_COUNT=0
for i in "${!KEY_ORDER[@]}"; do
  key="${KEY_ORDER[$i]}"
  if [ -n "${SET_IN[$key]:-}" ]; then
    UPDATED_COUNT=$((UPDATED_COUNT + 1))
    printf '%-*d  %-*s  Yes\n' "$NO_WIDTH" "$((i + 1))" "$FIELD_WIDTH" "$key"
  else
    printf '%-*d  %-*s  No\n' "$NO_WIDTH" "$((i + 1))" "$FIELD_WIDTH" "$key"
  fi
done

echo
echo "${UPDATED_COUNT} of ${#KEY_ORDER[@]} field(s) updated."

if [ "$UPDATED_COUNT" -eq 0 ]; then
  echo "No target file declares any of: ${KEY_ORDER[*]}."
  exit 1
fi
