#!/usr/bin/env bash
# Keep the scheduled uploader connected to both the private database network
# and a non-internal egress network.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

for compose_file in \
  docker/mystic_auth/compose/docker-compose.prod.yml \
  docker/mystic_auth/compose/docker-compose.local-prod-ngrok.yml \
  docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml \
  docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml; do
  service_block="$(awk '
    /^  db_backup:/ { in_service=1 }
    in_service && /^  [A-Za-z0-9_-]+:/ && $0 !~ /^  db_backup:/ { exit }
    in_service { print }
  ' "$compose_file")"
  grep -Fq 'networks: [postgres_net, backup_egress_net]' <<<"$service_block"

  egress_block="$(awk '
    /^  backup_egress_net:/ { in_network=1 }
    in_network && started && /^  [A-Za-z0-9_-]+:/ { exit }
    in_network { started=1; print }
  ' "$compose_file")"
  if grep -Fq 'internal: true' <<<"$egress_block"; then
    echo "FAIL: backup egress network is internal in $compose_file" >&2
    exit 1
  fi
  echo "OK: backup egress network is configured in $compose_file"
done

echo "All backup Compose network checks passed."
