#!/usr/bin/env bash
# Regression guard for production-shaped Compose services that should run
# with a read-only root filesystem.
#
# Intentionally NOT required here: ngrok, cloudflared, tailscale, and caddy.
# Each is a third-party vendor image whose internal entrypoint writes to
# paths this repo doesn't control (ngrok rewrites its own config file into
# /var/lib/ngrok on every start - verified live: tmpfs-mounting that
# directory erases the image's baked-in default config and the container
# restart-loops), and cloudflared/tailscale/caddy need real provider
# credentials this session didn't have to test live. See each service's own
# comment in its compose file.
#
# Usage: tests/scripts/mystic_auth/lint/check-readonly-rootfs.sh
# Exit 0: every required service has read_only: true. Exit 1: one or more
# don't, listed.
#
# Scoped to the local-prod-*/prod compose files only: docker-compose.dev.yml
# bind-mounts live source into these same containers for hot-reload (npm
# install, editable installs), which a read-only rootfs would break, and
# dev's own threat model doesn't call for this hardening the way an
# internet-facing mode does.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

python3 -c "import yaml" 2>/dev/null || pip install --quiet --user pyyaml

REQUIRED_SERVICES="postgres valkey backend frontend procrastinate_worker alembic geoipupdate db_backup bugsink bugsink-seed"

python3 - "$REQUIRED_SERVICES" <<'PYEOF'
import sys
import yaml
import glob

required = set(sys.argv[1].split())
missing = []
paths = [p for p in sorted(glob.glob("docker/mystic_auth/compose/docker-compose.*.yml"))
         if "docker-compose.dev.yml" not in p]
for path in paths:
    with open(path) as f:
        doc = yaml.safe_load(f) or {}
    for name, svc in (doc.get("services") or {}).items():
        if name in required and isinstance(svc, dict) and svc.get("read_only") is not True:
            missing.append(f"{path}: service '{name}' has no read_only: true")

if missing:
    print(f"ERROR: {len(missing)} required service(s) without read_only rootfs:")
    print()
    for m in missing:
        print(f"  {m}")
    sys.exit(1)

print("OK: every required service across docker/mystic_auth/compose/*.yml has read_only: true.")
PYEOF
