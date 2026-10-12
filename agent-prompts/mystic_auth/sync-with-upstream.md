Sync this app with the latest mystic-auth template
(https://github.com/Nachiket-2024/mystic-auth) and do the full integration:

1. Read only the COMPOSE_PROJECT_NAME, APP_NAME, and BRAND_COLOR lines from
   env/mystic_auth/.env.dev (or the matching existing dev env file). Use the
   project name wherever the steps below need the name/image prefix, and use
   the app name/brand color when setup-env asks its prompts. These three
   fields are not secrets; do not read, print, or otherwise touch any other
   field in that file.
2. Check how far behind upstream we are and whether upstream did any
   structural reorg (moved/renamed top-level dirs, config files, or
   scripts) since our last sync - check the top-level tree diff directly,
   don't just trust the sync script to handle it silently. On a first sync
   between unrelated histories, downstream-only paths are not incoming
   upstream changes; do not report app paths as ownership violations merely
   because the app split was stashed while satisfying the clean-index rule.
   Before running the sync, check `git diff --cached --quiet`. The script
   uses the index as its apply and commit workspace, so staged downstream
   work must be committed or stashed first. Do not silently commit downstream
   work just to satisfy this precondition. Unstaged and untracked work may
   remain because the script temporarily stashes and restores it.
   Confirm that `scripts/mystic_auth/upstream-sync/sync-upstream.sh` exists in
   the working tree before preserving any work. If it is absent from `HEAD`
   but present locally, never include that file in a preparatory stash: leave
   it in place and stash other paths with an explicit pathspec exclusion. If
   it is staged, unstage only that script without discarding its contents,
   then exclude it from the stash. Do not restore an older stashed copy over
   the current script. If the script is already inside a preserved stash,
   restore only that exact path from the current stash, not the whole stash.
   If no suitable stash has it, fetch the upstream remote and restore the
   script from the fetched upstream branch into the working tree. Do not treat
   split files that remain in the stash and are absent from `HEAD` as a
   first-sync blocker: the first-sync ownership guard intentionally handles
   that unrelated-history layout. Keep the split stash for restoration after
   the sync.
3. Run scripts/mystic_auth/upstream-sync/sync-upstream.sh. It applies
   intentional upstream-owned deletions and renames directly from the fetched
   upstream tree, including when the old path is already absent from the
   downstream index. Pay attention to the explicit `DELETE` and `MOVE` preview:
   those paths are intentionally removed or moved locally too; do not restore
   an old path just because it disappeared. If a deletion/rename unexpectedly
   targets an app-owned path, stop and inspect the ownership violation before
   confirming. Only if the script reports an unexpected hard failure on a
   customized path should you use its printed re-diff/exclude workaround, then
   hand-port app-specific additions into upstream's new file/location.
   If a later sync modifies an upstream-owned file that is missing from
   downstream `HEAD`, the script restores that file from the recorded upstream
   baseline before applying the three-way patch. This supplies Git's missing
   merge base; it does not override direct handling for a true upstream delete
   or rename.
4. Do not blindly resolve every conflict. First classify each changed path
   against docs/mystic_auth/template-usage/ownership-split.md. The upstream-
   owned, never-hand-edit tier includes backend/mystic_auth/,
   frontend/src/mystic_auth/, docs/mystic_auth/, screenshots/mystic_auth/,
   ci/mystic_auth/, scripts/mystic_auth/, agent-prompts/mystic_auth/, local-scripts/mystic_auth/,
   tracked docker/mystic_auth/, tracked env/mystic_auth/*.example,
   makefiles/mystic_auth/, root Makefile/make.ps1, backend/app/sdk.py, and
   frontend/src/app/sdk.ts. A conflict in one of these means the downstream
   repo violated the ownership split or upstream changed a path that should
   be replaceable; do not merge downstream product code into it. Preserve
   upstream's version and report the violation if the path was app-edited.
   The downstream-owned, upstream-never-touches tier includes all of
   backend/app/ except main.py and sdk.py, all of frontend/src/app/ except
   App.tsx and sdk.ts, docs/app/, screenshots/app/, scripts/app/,
   ci/app/, agent-prompts/app/, local-scripts/app/, docker/app/, env/app/,
   makefiles/app/, every tests/**/app/ tree, and the root README.md,
   SECURITY.md, and CONTRIBUTING.md.
   The sync preserves downstream-owned root documentation; upstream changes
   to README.md, SECURITY.md, and CONTRIBUTING.md are reported and ignored so
   they cannot block unrelated template fixes or overwrite downstream copies.
   If the script reports any other downstream-owned path, stop: that is an
   ownership violation and the script must not apply any part of that sync. A
   real conflict in backend/app/main.py or frontend/src/app/App.tsx
   (the shared, extend-in-place files) gets both sides merged. Comment-only
   diffs in shared files take upstream's wording.
   Comment-only maintenance in frontend/src/app/main.tsx and
   frontend/src/app/theme.ts is also allowed; executable-code changes in
   those app-owned files remain blocked.
   The three app-content exceptions are
   frontend/src/mystic_auth/translations/languages/*/{landing,status_pages,legal}.json:
   those JSON values are downstream-owned deployment content even though the
   files remain in the shared language tree. If one conflicts, preserve the
   project's reviewed content and manually add any new upstream keys; review
   upstream copy before accepting it. Never hand-edit the surrounding
   mystic_auth translation code.
   Downstream runtime env files such as env/mystic_auth/.env.dev and
   env/mystic_auth/.env.prod are local deployment state, not upstream source;
   preserve their values through the env workflow. Put app-only configuration
   in env/app/ and app-owned settings code, never in MysticAuth internals.
   Do not classify a failing test solely by path. `tests/**/app/` is for
   downstream additions, but older template reference tests may already be
   there. Compare the path with the recorded upstream baseline: inherited tests
   may receive upstream fixes; newly added downstream tests must still block.
   If an older checkout's guard blocks an inherited baseline test, stop before
   applying anything, verify the path existed at the last sync, update only
   `scripts/mystic_auth/upstream-sync/sync-upstream.sh` from the fetched
   upstream tree, then rerun the sync. Never bypass the guard or weaken it for
   new downstream tests.
   A literal configurable default such as `MysticAuth` or `mystic_auth` is an
   upstream test-compatibility defect. Fix/report the test upstream; do not
   rewrite intentional downstream branding or database configuration.
   The sync's job is to bring all approved upstream-owned MysticAuth changes
   into the downstream project. Do not use the sync to redesign or update the
   app-owned product code. Preserve that work and leave any app-side follow-up
   for a separate task only when the repository owner requests it.
5. Grep our own app-side code/tests for any import path pointing into a
   now-renamed mystic_auth internal module, and fix those.
6. Regenerate every real env file without reading any of its old secret
   values yourself:
   a. Rename each existing file in both env/mystic_auth/ and env/app/ aside
      with a matching .bak suffix (for example env/app/.env.prod to
      env/app/.env.prod.bak) - never delete. Include frontend/.env if it
      exists.
   b. Run scripts/mystic_auth/env-tools/setup-env/setup-env.sh, or its platform
      wrapper, to generate fresh files with newly generated secrets and this
      sync's latest fields. Answer No to its optional Google OAuth and Gmail
      prompts; do not enter real OAuth/email secrets into the agent context
      during a sync.
   c. For each old/new pair, run
      scripts/mystic_auth/env-tools/copy-env-values/copy-env-values.sh OLD NEW
      to copy every field that isn't
      a freshly generated secret back from the old file into the new one. If
      the old file has a blank BACKUP_UPLOAD_COMMAND but the new example has
      a non-blank default, preserve the new value and review the field; never
      copy the blank over the new default.
      Its own output only prints field names, never values - don't read
      the .bak files with cat or anything else yourself.
   d. Show me its "In old file but not in new file" output, if any: that
      means upstream dropped or renamed a field our app depends on, and
      needs a decision from me.
   e. Once I've confirmed the new files are correct, delete the .bak
      files.
7. Check for anything else upstream restructured that our app depends on:
   compose service names, Docker project/image names (must stay
   "<project-name>-*" from step 1, not a generic template name - avoids
   container/network/port collisions on a shared host), doc/README
   references to old paths. When GeoIP is configured, start the production
   or local-prod stack with the `geoip` Compose profile (the dev wrapper adds
   it automatically) so the updater downloads
   `/usr/share/GeoIP/GeoLite2-City.mmdb`; verify its health and the backend
   readiness endpoint before testing login/session location.
   Verify branding after the sync: user-visible product names, browser titles,
   status-page labels, accessible brand labels, and generated descriptions must
   come from the configured `APP_NAME`/`VITE_APP_NAME`, not a literal
   `MysticAuth`. Keep `mystic_auth` unchanged where it is a technical
   namespace, import path, Compose service/path prefix, or documentation code
   reference; do not perform a global rename. Also verify backup and restore
   checks use the configured `POSTGRES_DB` and `POSTGRES_USER`, not a literal
   `mystic_auth` database or `postgres` role, unless the check is deliberately
   testing the template default itself. This includes negative restore-drill
   checks, which must use the same configured role as the positive drill.
   Audit Dockerfiles, Compose modes, CI variables, healthchecks,
   seed/bootstrap commands, and backup commands: pass `APP_NAME`/`VITE_APP_NAME`
   and `POSTGRES_DB`/`POSTGRES_USER` through configuration; retain technical
   `mystic_auth` identifiers. CI fixture values must not become production
   defaults. For inherited frontend checks, treat landing-page copy as
   app-owned: test stable landmarks and behavior, not a template marketing
   sentence or a downstream product name. For browser-only downloads, keep
   jsdom tests at the browser-API boundary so they do not trigger unsupported
   document navigation.
   Setup-env now uses matching `.bak` values as prompt defaults during this
   workflow and derives every generated database URL from that file's
   `POSTGRES_DB`. Verify a non-default database name such as `example_app_db` and
   a downstream `APP_NAME` survive regeneration before deleting the backups.
   Keep host-run URL-derivation fixtures on a non-default database name such as
   `example_app_db`, not the template default, so the test proves the helper
   preserves configured database names while rewriting only host and port.
   Run `alembic upgrade head` before running
   `local-scripts/mystic_auth/seed-user-permission-matrix.py` for the
   real-account browser matrix;
   p4 accounts must expose `users:delete_any` (hard purge), not
   `users:deactivate_any` (soft delete).
8. Run scripts/mystic_auth/upstream-sync/check-alembic-heads.sh; if it reports
   multiple heads, write the merge migration yourself before testing. Also run
   `alembic check` after upgrading the database so model/migration drift is
   caught, not just migration-head collisions.
9. Rebuild and run the current verification surface. At minimum run backend
   ruff/mypy, backend unit + integration + security tests with the cumulative
   90% coverage gate, and the frontend commands through
   `ci/mystic_auth/backend.sh`, `ci/app/backend.sh`, and
   `ci/app/frontend.sh`, matching `.github/workflows/ci.yml`. Run the backend suite in Docker
   as well when the dev stack is available. Run the repository lint/regression
   scripts for split paths, script paths, image digests, service log rotation,
   CI action pinning, read-only root filesystems, env tooling, backups, and
   sync-upstream. Include backup round-trip/restore checks when the Docker
   environment is available. Fix anything broken in app-owned code; if a
   failure traces to an upstream mystic_auth file/test, don't fix it - tell me
   exactly what's broken and why. When validating Docker changes, build the
   backend runtime, frontend production, and backup images and check their
   notice artifacts as CI does. The notice bundle covers Python and npm
   application dependencies, rclone's Go modules, and Debian packages in the
   backup image (see `THIRD_PARTY_NOTICES/README.md`). CI checks the bundles in
   all three images and publishes exact-image SBOMs. The base images' packages
   are represented in those SBOMs, not the generated application notice bundle.
   When auditing a broad integration run, inspect background-worker teardown
   for destructive cleanup of in-flight `todo`/`doing` jobs. Queue cleanup may
   remove only terminal jobs; otherwise deferred authorization audit entries
   can disappear intermittently even though isolated tests pass.
10. Update any of our own doc/README references to the sync (e.g. a
    "currently synced to" line, if we keep one) and any other stale
    doc/README/CI references. Don't touch .mystic-auth-sync-state -
    sync-upstream.sh already updated it as part of step 3.
11. After the sync completes, the current working-tree script will have
    created its own single sync
    commit on a clean successful run. Do not create an additional commit or
    push. Unstaged and untracked downstream work was temporarily stashed,
    including an app split that was not committed yet, then restored after the
    sync commit. Ignored files such as real env files are excluded. If
    restoration conflicts, keep the sync commit and resolve the retained
    stash manually.
    If the owner wants to review the result without keeping that generated
    commit, run `git reset --soft HEAD^` immediately after the successful
    sync, inspect the staged changes, and commit them only after approval.
    Never use `git reset --hard`, and do not run another sync while the
    review changes remain staged.
   If the sync stops
   on a conflict or migration-head problem, leave its staged/pending
   state for me to review and resolve; never delete or reset work. Do not
   start another sync while `.mystic-auth-sync-state`, conflict entries, or
   a soft-reset review are still staged or pending. Resume the existing
   sync by resolving the files, checking Alembic heads, and committing the
   reviewed result first.
   If `HEAD` predates the staged sync result and `.mystic-auth-sync-state` is
   staged but not committed, this is the same pending-review state even when
   there are no conflicts or unstaged files. Inspect and commit the staged
   result before syncing again. Do not stash it or treat the checkout as a
   fresh first sync.
12. Do this yourself directly - no subagents/Task agents for any part of
    this. Work through it inline in this session.
