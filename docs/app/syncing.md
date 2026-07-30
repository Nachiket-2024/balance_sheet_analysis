# Syncing with Upstream mystic-auth

[`docs/mystic_auth/template-usage/syncing-upstream.md`](../mystic_auth/template-usage/syncing-upstream.md)
describes `scripts/sync-upstream.sh`, the normal way to pull upstream
changes and, once run, commit the result. This repo hasn't used it yet: the
script requires a clean `git status` going in, and nothing in this repo has
been committed yet.

## Until this repo's history catches up

Syncing is done manually instead: diff `backend/mystic_auth/`,
`frontend/src/mystic_auth/`, `docs/mystic_auth/`, `tests/backend/mystic_auth/`,
`tests/frontend/mystic_auth/`, `backend/app/sdk.py`, `frontend/src/app/sdk.ts`,
and the root infra files mystic-auth also ships (`docker-compose*.yml`,
`docker/`, `.github/workflows/ci.yml`, `frontend/vite.config.ts`, `scripts/`)
against upstream's current `main`, then replace whatever changed. No git
operation touches this repo's own commit graph either way.

`backend/app/app_sdk.py`/`frontend/src/app/app_sdk.ts` are never replaced
this way, since upstream ships them empty and never touches them again, so ours
(with our own re-exports) are always the ones to keep.
`backend/app/main.py`/`frontend/src/app/App.tsx` are hand-merged: pull in
any new upstream lines, keep this app's own router/route additions.

**Currently synced to:** mystic-auth commit `50a04d5` (tracked in
`.mystic-auth-sync-state`, the same file `scripts/sync-upstream.sh` itself
maintains once it's in use).

## Windows gotcha: line endings

Cloning mystic-auth with git's `core.autocrlf=true` converts every text file
to CRLF on checkout, which breaks shell scripts and docker-compose's
multi-line `command: |` blocks. Normalize to LF (`sed -i 's/\r$//'` per file,
or `dos2unix`) right after cloning, before diffing or copying anything. This
repo's own `.gitattributes` (`eol=lf` on every text file) protects its own
checkouts, but a fresh clone of mystic-auth itself for the next sync isn't
covered by that, so re-normalize it each time.
