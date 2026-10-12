# Syncing Upstream: Rebuild, Push, and Reference

---

## Step 7: Rebuild and test before you trust any of it

Even a sync that applied with zero conflicts can quietly change how the app behaves, so don't skip this:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev up -d --build
scripts/mystic_auth/docker/dev/backend-exec.sh python -m pytest tests/backend/mystic_auth/unit tests/backend/mystic_auth/integration tests/backend/mystic_auth/security
```

`scripts/mystic_auth/docker/dev/backend-exec.sh` wraps `docker compose exec --user root -w /repo backend` with the two workarounds it needs to actually work everywhere: `--user root` (native Linux only, or pytest-cov's coverage output crashes with a permission error) and `MSYS_NO_PATHCONV=1` (Windows Git Bash only, or this fails with `Cwd must be an absolute path`). Both are no-ops on platforms that don't need them, so the one wrapped command is safe to run as-is regardless of what you're on. See [Docker Overview: running a one-off command inside a container](../../docker/dev-workflow.md#running-a-one-off-command-inside-a-container) for the full explanation of both, if you ever need to run something the wrapper doesn't cover.

**A dependency rename is the sharpest example of why this step matters.** If `frontend/package.json` swaps out a dependency (e.g. `react-router-dom` was retired upstream in favor of `react-router` v8, since the old package stopped receiving security patches), the sync applies that swap to `package.json` and to every import inside `frontend/src/mystic_auth/`, since that's what upstream's own diff touches. It does **not** touch `frontend/src/app/`, your own code, even if it imports the exact same old package. Git sees no conflict there at all: `package.json` merges cleanly, so there's no marker to prompt you. The breakage only shows up as `npm run typecheck`/`npm run build` failing on a now-missing package once you run it, which is exactly what this step is for.

---

## Step 8: Push whenever you're happy with it

At this point you just have one new, ordinary commit sitting on top of your project's history, same as any commit you'd normally make. Push it to your branch, or open your own internal pull request to have a teammate look it over first. There's no PR or step required back against the original template repo; the sync only ever pulls, it never pushes anywhere.

---

## How it stays fast and accurate even after 20+ syncs

Behind the scenes, the script keeps a small tracked file, `.mystic-auth-sync-state`, containing the exact upstream commit you last synced to. It updates that file automatically every time you sync, right alongside the sync commit itself. Each new sync uses that file to look at only what changed upstream *since then*, rather than re-checking your entire codebase from scratch every time. That's what keeps the "what's new" list accurate and keeps unrelated files from ever being flagged, no matter how many releases you've already pulled in. You never read or edit this file yourself; just don't delete it. If it ever does go missing, the next sync safely falls back to checking everything from scratch (same as a first sync) rather than breaking.

`scripts/mystic_auth/upstream-sync/sync-upstream.sh` itself is upstream-owned, same rule as [the rest of `mystic_auth/`](../ownership-split.md): don't hand-edit it. If you're contributing a change to the sync mechanism itself, `tests/scripts/mystic_auth/upstream-sync/test-sync-upstream.sh` regression-tests it end-to-end against throwaway fake repos, without touching this repo's own history. Run it after any change to `sync-upstream.sh`.

`sync-upstream.ps1`/`sync-upstream.cmd` are thin platform entry points, not a second implementation: they locate Git Bash and run the real `sync-upstream.sh` through it, so there's no separate logic for `test-sync-upstream.sh` to cover and nothing to keep in sync by hand. They only need touching if the real script's invocation contract changes (its arguments, or what it expects on stdin for the `y/N` prompt).

That test suite also asserts every `scripts/**/*.sh` is tracked as mode `755` in this repo's own git index. This repo runs with `core.filemode=false` (common on Windows), so a plain local `chmod +x` never shows up as a diff. If you add a script and forget to make it executable, fix it with `git update-index --chmod=+x path/to/script.sh` instead.

**As a downstream user, you don't need to do anything about this.** A script under `scripts/**/*.sh` can occasionally land non-executable after a sync, for the same `core.filemode=false` reason. `sync-upstream.sh` checks for this and restores it automatically before deciding whether to commit; you'd only notice from a line in the sync output (`Restoring the executable bit on scripts that lost it during this sync:`), never from a script failing to run.

---

## Resolving a conflict in `main.py` / `App.tsx`

Before running the sync, it's worth keeping a throwaway copy of any shared file you've edited recently (`cp backend/app/main.py /tmp/main.py.bak`, or just note the output of `git diff HEAD~<n> -- backend/app/main.py` if you know when you last edited it). This is cheap insurance so you have something to compare against if a merge does something unexpected. `git stash` works too, if you'd rather not touch anything until after the merge.

Most of the time this isn't even a real conflict: if your router registration is on its own line and upstream's change landed elsewhere in the file, git applies both changes automatically and you won't see a conflict marker at all. A real conflict only happens when both sides touch the exact same lines, e.g. you both added a new router registration right after the same existing one:

```python
app.include_router(health_router)
<<<<<<< HEAD
app.include_router(projects_router)          # yours
=======
app.include_router(some_new_upstream_router)  # upstream's
>>>>>>> upstream/main
```

Resolve it like any git conflict: decide what the merged result should be, almost always **both** lines, delete the `<<<<<<<`/`=======`/`>>>>>>>` markers, then continue. Neither sync path (squash merge or incremental apply) leaves an in-progress merge state, so "continue" just means staging and committing yourself. There is no `git merge --continue` or `git apply --continue` to run:

```python
app.include_router(health_router)
app.include_router(some_new_upstream_router)
app.include_router(projects_router)          # yours
```

```bash
git add backend/app/main.py
git commit -m "Sync upstream template updates (mystic-auth@<sha>)"
```

Same process for `App.tsx`'s route list. After committing, rebuild and re-run the test suite before trusting it: see [Testing Overview](../../testing/overview.md).

---

See [Syncing Upstream](README.md) for the earlier steps, or [Troubleshooting](troubleshooting.md) for a conflict, a silent partial apply, or multiple alembic heads.

---
