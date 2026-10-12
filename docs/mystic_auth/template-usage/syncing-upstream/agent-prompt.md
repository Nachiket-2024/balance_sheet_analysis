# Syncing with an AI Coding Agent

---

The steps in [README](README.md)/[Rebuild, Push, and Reference](rebuild-and-push.md)/[Troubleshooting](troubleshooting.md) are written for a person to follow by hand. If you'd rather hand the whole thing to an agentic coding tool (Claude Code, Codex, or similar) and review the result, use [`agent-prompts/sync-with-upstream.md`](../../../../agent-prompts/mystic_auth/sync-with-upstream.md) at the repo root: a copy-paste starting prompt for exactly that. This page is the reasoning behind it.

## What to give the agent

Paste the prompt from [`agent-prompts/mystic_auth/sync-with-upstream.md`](../../../../agent-prompts/mystic_auth/sync-with-upstream.md) while the agent is working in the downstream repository. Before it runs anything, tell it which branch to update if that is not obvious. The agent should:

1. Work from the downstream repository root.
2. Review `git status` and refuse to proceed with staged changes. Commit or stash staged downstream work first. Unstaged and untracked work can be preserved by the sync script, which temporarily stashes it and restores it after the sync commit.
3. Keep the app split available when checking ownership. If the app split is stashed for a first sync, downstream-only files are still not incoming upstream changes.
4. Ask for confirmation at the script's sync prompt; do not silently accept it.
5. Stop on ownership violations, conflicts, failed validation, or multiple Alembic heads. Do not force a partial sync.

The sync completes the upstream-owned MysticAuth update. It preserves
downstream app code and does not redesign or update app-owned product files as
part of the sync. Handle app-side follow-up separately only when the
repository owner requests it.

Before stashing preparatory work, confirm that
`scripts/mystic_auth/upstream-sync/sync-upstream.sh` exists in the working
tree. If it is not in `HEAD` but exists locally, preserve that current script
and exclude it from any stash of downstream work. If it is staged, unstage only
that script without discarding it. Never restore an older stashed script over
the current one. If the script exists only in a preserved stash, restore only
that path from the current stash, or restore it from the fetched upstream
branch. Do not restore the whole split stash before the first sync, and do not
treat app files absent from `HEAD` as a blocker for the unrelated-history
first-sync path.

The script creates one sync commit on success. If the repository owner wants
to review the sync without keeping that generated commit, run
`git reset --soft HEAD^` immediately afterward, inspect the staged changes,
and commit them only after approval. Never use `git reset --hard`, and do not
run another sync while the review changes remain staged. The same rule applies
to a conflict or migration-head failure: resolve and commit the existing
staged sync state before starting another sync. If `HEAD` predates the staged
result and `.mystic-auth-sync-state` is staged but not committed, treat that
as the same pending review even when there are no conflicts or unstaged files.
Do not stash it or rerun the sync as a fresh first sync.

The prompt is an operating procedure, not permission to edit upstream-owned Mystic Auth internals in the downstream project. A defect in `backend/mystic_auth/`, the official sync tooling, or template-owned deployment files belongs in this repository and should be reported or fixed here.

Do not classify a failing test solely by path. `tests/**/app/` is for downstream
additions, but older template reference tests may already be there. Compare the
path with the recorded upstream baseline: inherited tests may receive upstream
fixes; newly added downstream tests remain protected. A literal configurable
default such as `MysticAuth` or `mystic_auth` is an upstream compatibility
defect; fix/report the test upstream instead of changing intentional downstream
branding or database configuration. If an older guard blocks an inherited
baseline test, stop, verify the path existed at the last sync, update only
`scripts/mystic_auth/upstream-sync/sync-upstream.sh` from the fetched upstream
tree, and rerun. Never bypass the guard or weaken it for new downstream tests.

Branding has the same boundary: check that user-visible product names, browser
titles, status-page labels, accessible brand labels, and generated descriptions
derive from `APP_NAME`/`VITE_APP_NAME`, rather than a literal `MysticAuth`.
Keep `mystic_auth` intact when it is a technical namespace, import path,
Compose service/path prefix, or documentation code reference; never perform a
global rename of that namespace. Backup and restore checks should likewise use
the configured `POSTGRES_DB` and `POSTGRES_USER`, including negative
restore-drill checks, except when a test is intentionally testing the template
default itself.

Include Dockerfiles, Compose modes, CI variables, healthchecks, seed/bootstrap,
and backup commands in that audit. They should pass `APP_NAME`/`VITE_APP_NAME`
and `POSTGRES_DB`/`POSTGRES_USER` through configuration; technical
`mystic_auth` identifiers remain unchanged. Inherited landing-page checks
should assert stable landmarks and behavior rather than template marketing
copy or a downstream product name. Browser-only download tests should mock
the jsdom browser API boundary so they do not trigger unsupported document
navigation. CI fixture values must not become production defaults.

When a broad integration run intermittently loses deferred audit entries,
inspect worker teardown before changing application behavior. Cleanup may
remove only terminal background-job rows; deleting in-flight `todo`/`doing`
jobs can make successful authorization decisions disappear while isolated
tests still pass.

---

## Why this isn't just "sync and rebuild"

A real sync can hit several things that don't show up in a first-time read of the mechanism: upstream reorganizing a shared config file, a real merge conflict in a file both sides touch, two Alembic heads, or your own app-side code importing something upstream renamed. An agent prompt for this needs to name those failure modes up front, or the agent has no way to know that a `docker-compose.dev.yml` conflict and a `backend/mystic_auth/` conflict need completely different handling.

---

## Keeping secrets out of the agent's context

Regenerating env files is part of a full sync (fresh secrets, upstream's latest fields), but an agent reading your real `GOOGLE_CLIENT_SECRET`, `GMAIL_APP_PASSWORD`, or `DATABASE_URL` to "carry them forward" puts those values into its context and transcript for no real reason. The prompt routes around this with two scripts, neither of which ever prints a secret value to its own output, only field *names*:

1. The agent **renames** each real env file in both `env/mystic_auth/` and
   `env/app/` aside (`.env` to `.env.bak`, and so on), plus `frontend/.env` if
   present - never deletes - so nothing is lost.
2. The agent runs `scripts/mystic_auth/env-tools/setup-env/setup-env.sh` (`.ps1`/`.cmd`). Since the real files no longer exist under their normal names, it generates fresh files from the current `.example` files, with newly generated secrets and this sync's latest fields.
3. The agent runs `scripts/mystic_auth/env-tools/copy-env-values/copy-env-values.sh OLD NEW` (`.ps1`/`.cmd`) for each old/new pair. It copies every field from the old file into the new one, except the handful setup-env just generated fresh (secrets, and the DB URLs that embed them). If an older file has a blank `BACKUP_UPLOAD_COMMAND` but the new example supplies a non-blank default, it preserves the new value and reports that field for review. The tool reports only which field *names* it moved, never their values, and flags any field that existed in the old file but not the new one (upstream may have dropped or renamed it) for you to decide on by hand.
4. Once you've confirmed the new files are correct, the agent tells you to delete the `.bak` files yourself.

The sync prompt reads only `COMPOSE_PROJECT_NAME`, `APP_NAME`, and
`BRAND_COLOR` from the existing dev env file so it can preserve the project's
identity when answering `setup-env`'s prompts. It never reads secret values.

The sync script also enforces the ownership table before applying a patch:
upstream changes to downstream-owned code, CI, or app folders block the whole sync,
while root `README.md`, `SECURITY.md`, and `CONTRIBUTING.md` changes are
reported, excluded, and preserved locally.
The prompt therefore tells the agent to classify conflicts by ownership
instead of blindly merging every conflict.

The first sync is different because a template repository and a downstream
repository do not share normal Git ancestry. The script treats the upstream
tree as the source of incoming changes and ignores paths that exist only in
the downstream project. This remains safe when a downstream app split was
stashed to satisfy the clean index requirement. Later syncs use
`.mystic-auth-sync-state` as the exact upstream baseline and inspect only
changes since the previous sync.
If an upstream-owned file from that baseline is missing from downstream
`HEAD`, the script restores the baseline file for the three-way apply. Real
upstream deletes and renames still use the direct structural path handling.

See [Environment Configuration](../../environment/README.md) for what both scripts do in full.

---

See [Rebuild, Push, and Reference](rebuild-and-push.md) and [Troubleshooting](troubleshooting.md) for what each numbered step in the prompt is actually doing under the hood, if the agent (or you, reviewing its work) needs the full explanation behind a given step.

The sync script requires a clean Git index before it starts, then intentionally
creates one sync commit when it succeeds. The prompt therefore asks the agent
not to add another commit or push; a conflict
or migration-head failure remains for human review instead. The agent should
show the resulting commit and validation summary, but leave pushing to the
repository owner. If the script reports that saved downstream work could not
be restored cleanly, keep the sync commit, resolve the worktree conflict, and
retain the stash until the restored files have been verified.
