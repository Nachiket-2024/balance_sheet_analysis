#!/bin/sh
# Runs as root (the image's default user) so it can fix ownership of
# /app/logs and /repo/backend/logs before handing off to the unprivileged
# `app` user. Needed because a `backend_logs` named volume created under an
# older image UID (e.g. before a base image migration changed the `app`
# user's UID) keeps that stale ownership across image rebuilds - a fresh
# volume already has the right owner, so this is a no-op there.
set -e

# Production images declare the non-root app user. Development Compose mounts
# host-owned source/log volumes and explicitly runs this entrypoint as root so
# it can normalize those mounts before dropping privileges.
if [ "$(id -u)" -ne 0 ]; then
    exec "$@"
fi

for dir in /app/logs /repo/backend/logs; do
    [ -d "$dir" ] && chown -R app:app "$dir"
done

exec su-exec app "$@"
