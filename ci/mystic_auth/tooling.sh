#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  echo "Usage: $0 {script-paths|split-paths|platform-wrappers|image-digests|log-rotation|action-pinning|readonly-rootfs|env-tools|upstream-sync|backup-freshness|backup-network|host-backend|backup-roundtrip|restore-drill}" >&2
  exit 2
}

case "${1:-}" in
  script-paths)
    tests/scripts/mystic_auth/lint/check-script-paths.sh
    ;;
  split-paths)
    tests/scripts/mystic_auth/lint/check-split-paths.sh
    ;;
  platform-wrappers)
    tests/scripts/mystic_auth/lint/check-platform-wrappers.sh
    ;;
  image-digests)
    tests/scripts/mystic_auth/lint/check-image-digests.sh
    ;;
  log-rotation)
    tests/scripts/mystic_auth/lint/check-log-rotation.sh
    ;;
  action-pinning)
    tests/scripts/mystic_auth/lint/check-ci-action-pinning.sh
    ;;
  readonly-rootfs)
    tests/scripts/mystic_auth/lint/check-readonly-rootfs.sh
    ;;
  env-tools)
    tests/scripts/mystic_auth/env-tools/test-env-tooling.sh
    ;;
  upstream-sync)
    tests/scripts/mystic_auth/upstream-sync/test-sync-upstream.sh
    ;;
  backup-freshness)
    tests/scripts/mystic_auth/db/test-backup-freshness.sh
    ;;
  backup-network)
    tests/scripts/mystic_auth/db/test-backup-compose-network.sh
    ;;
  host-backend)
    tests/scripts/mystic_auth/docker/test-backend-host-run.sh
    ;;
  backup-roundtrip)
    tests/scripts/mystic_auth/db/test-backup-roundtrip.sh
    ;;
  restore-drill)
    tests/scripts/mystic_auth/db/test-restore-drill.sh
    ;;
  *)
    usage
    ;;
esac
