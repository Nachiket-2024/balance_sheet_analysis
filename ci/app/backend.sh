#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  echo "Usage: $0 {lint|typecheck|security|unit}" >&2
  exit 2
}

case "${1:-}" in
  lint)
    (cd backend && ruff check app ../tests/backend/app)
    ;;
  typecheck)
    (cd backend && mypy app)
    ;;
  security)
    (cd backend && bandit -r app -c pyproject.toml)
    ;;
  unit)
    python -m pytest tests/backend/app -q
    ;;
  *)
    usage
    ;;
esac
