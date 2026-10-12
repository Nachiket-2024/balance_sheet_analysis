#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  echo "Usage: $0 {audit-dependencies|lint|typecheck|security|unit|integration|security-tests|performance}" >&2
  exit 2
}

case "${1:-}" in
  audit-dependencies)
    python -m pip install --no-cache-dir pip-audit
    python -m pip_audit -r backend/requirements.txt
    ;;
  lint)
    (cd backend && ruff check mystic_auth alembic ../tests/backend/mystic_auth)
    ;;
  typecheck)
    (cd backend && mypy mystic_auth)
    ;;
  security)
    (cd backend && bandit -r mystic_auth -c pyproject.toml)
    ;;
  unit)
    python -m pytest tests/backend/mystic_auth/unit -q --cov-append
    ;;
  integration)
    python -m pytest tests/backend/mystic_auth/integration -q --cov-append
    ;;
  security-tests)
    python -m pytest tests/backend/mystic_auth/security -q --cov-append --cov-fail-under=90
    ;;
  performance)
    python -m pytest tests/backend/mystic_auth/performance -q
    ;;
  *)
    usage
    ;;
esac
