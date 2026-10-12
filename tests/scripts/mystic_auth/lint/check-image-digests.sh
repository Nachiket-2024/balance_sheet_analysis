#!/usr/bin/env bash
# Regression guard for malformed pinned-image digests:
# docker-compose.local-prod-ngrok.yml once had a geoipupdate digest one hex
# character short (63 chars instead of 64), copied into all four
# production-shaped compose files. `docker pull`/`docker compose ...
# --profile geoip up` fails outright on a clean host with "invalid checksum
# digest length", and nothing short of actually pulling the image caught it:
# `docker compose config` happily accepts a malformed digest string.
#
# Scans every docker/{mystic_auth,app}/compose/docker-compose.*.yml for an
# `@sha256:<hex>` image pin and asserts the hex portion is exactly 64
# characters.
#
# Usage: tests/scripts/mystic_auth/lint/check-image-digests.sh
# Exit 0: every pinned digest is 64 hex characters. Exit 1: one or more
# aren't, listed.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

BAD=()

while IFS= read -r -d '' f; do
  while IFS=: read -r line_no digest; do
    [ -n "$digest" ] || continue
    len=${#digest}
    if [ "$len" -ne 64 ]; then
      BAD+=("$f:$line_no: digest is $len hex characters, not 64 ($digest)")
    fi
  done < <(grep -noP '@sha256:\K[0-9a-fA-F]+' "$f" 2>/dev/null)
done < <(find docker/mystic_auth/compose docker/app/compose -type f -name "docker-compose.*.yml" -print0 2>/dev/null)

if [ "${#BAD[@]}" -eq 0 ]; then
  echo "OK: every pinned image digest across docker/{mystic_auth,app}/compose/*.yml is a valid 64-character sha256."
  exit 0
fi

echo "ERROR: ${#BAD[@]} malformed image digest(s) found:"
echo
printf '  %s\n' "${BAD[@]}"
echo
echo "A malformed digest fails 'docker pull'/'docker compose up' outright on"
echo "any host without the (wrong) image already cached. Get the correct"
echo "digest with: docker pull <image>:<tag> && docker inspect <image>:<tag>"
echo "--format '{{index .RepoDigests 0}}'"
exit 1
