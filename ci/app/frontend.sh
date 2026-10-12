#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR/frontend"

usage() {
  echo "Usage: $0 {audit|typecheck|lint|test-coverage|build}" >&2
  exit 2
}

case "${1:-}" in
  audit)
    npm audit --audit-level=high
    ;;
  typecheck)
    npm run typecheck
    ;;
  lint)
    npm run lint
    ;;
  test-coverage)
    npm run test:coverage
    ;;
  build)
    npm run build
    ;;
  *)
    usage
    ;;
esac
