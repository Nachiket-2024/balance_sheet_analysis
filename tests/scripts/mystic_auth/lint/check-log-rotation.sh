#!/usr/bin/env bash
# Regression guard for unbounded container logs. Each Compose service must
# set a json-file rotation limit so logs cannot fill the host disk.
#
# Asserts every service in every docker/{mystic_auth,app}/compose/
# docker-compose.*.yml resolves a `logging.options.max-size`, either set
# directly on the service or inherited through a YAML merge key (`<<:`).
#
# Usage: tests/scripts/mystic_auth/lint/check-log-rotation.sh
# Exit 0: every service has log rotation. Exit 1: one or more don't, listed.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

# GitHub-hosted ubuntu-latest runners ship PyYAML already; a local dev
# machine's system python3 may not. Fall back to a user-site install rather
# than requiring this script to be run from a venv that has it.
python3 -c "import yaml" 2>/dev/null || pip install --quiet --user pyyaml

python3 - <<'PYEOF'
import sys
import yaml
import glob

missing = []
for path in sorted(glob.glob("docker/mystic_auth/compose/docker-compose.*.yml")) + \
            sorted(glob.glob("docker/app/compose/docker-compose.*.yml")):
    with open(path) as f:
        doc = yaml.safe_load(f) or {}
    for name, svc in (doc.get("services") or {}).items():
        if not isinstance(svc, dict):
            continue
        options = ((svc.get("logging") or {}).get("options") or {})
        if "max-size" not in options:
            missing.append(f"{path}: service '{name}' has no logging.options.max-size")

if missing:
    print(f"ERROR: {len(missing)} service(s) with no log rotation configured:")
    print()
    for m in missing:
        print(f"  {m}")
    print()
    print("Add a `logging:` block (driver: json-file, options: {max-size, max-file})")
    print("directly on the service, or merge in a shared anchor that sets one -")
    print("see x-container-hardening in the local-prod-*/prod compose files, or")
    print("x-logging in docker-compose.dev.yml, for the existing pattern.")
    sys.exit(1)

print("OK: every compose service across docker/{mystic_auth,app}/compose/*.yml sets log rotation.")
PYEOF
