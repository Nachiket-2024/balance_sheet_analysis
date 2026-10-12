# Your Scripts

Nothing here yet. This is where your own project-specific scripts go, the
same way `backend/app/` and `frontend/src/app/` hold your own code: upstream
never adds anything under `scripts/app/`, so nothing here ever conflicts on
a `scripts/mystic_auth/upstream-sync/sync-upstream.sh` run.

Template scripts (env setup, Docker up/down, DB backup/restore, upstream
sync) live in `scripts/mystic_auth/` instead: see
[Using This Repository as a Template](../../docs/mystic_auth/template-usage/ownership-split.md).
