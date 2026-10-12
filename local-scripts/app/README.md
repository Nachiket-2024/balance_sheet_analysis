# Your Local Scripts

Nothing here yet. This is where your own project-specific local helper
scripts go (one-off dev conveniences, seed-data generators, whatever isn't
worth putting under `scripts/app/` because it only ever runs against one
compose mode). Upstream never adds anything under `local-scripts/app/`, so
nothing here ever conflicts on a `scripts/mystic_auth/upstream-sync/sync-upstream.sh` run.

Template scripts (`create-system-user` per compose mode) live in
`local-scripts/mystic_auth/` instead.
