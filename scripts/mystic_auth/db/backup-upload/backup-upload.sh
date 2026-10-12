#!/usr/bin/env bash
# Compose env files use $${...} to preserve a dollar sign through Compose
# interpolation. Normalize that representation before executing the operator's
# upload hook with the verified dump path.
set -euo pipefail

DUMP_FILE="${1:?dump file is required}"
UPLOAD_COMMAND="$(printf '%s' "${BACKUP_UPLOAD_COMMAND:-}" | sed 's/\$\$/\$/g')"

[ -n "$UPLOAD_COMMAND" ] || exit 0
DUMP_FILE="$DUMP_FILE" sh -c "$UPLOAD_COMMAND"

# Ship the detached HMAC tag (see backup-hmac.sh) alongside the ciphertext -
# database-restore.sh needs it present at the same remote location to verify a
# downloaded backup wasn't tampered with before decrypting it.
if [ -f "${DUMP_FILE}.hmac" ]; then
  DUMP_FILE="${DUMP_FILE}.hmac" sh -c "$UPLOAD_COMMAND"
fi
