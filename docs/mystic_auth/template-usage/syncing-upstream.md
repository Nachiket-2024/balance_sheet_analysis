# Staying in Sync with Upstream Template Updates

"Upstream" just means the original mystic-auth template repo: the one you clicked **Use this template** on. Every so often it gets new fixes or features, and you can pull those into your own project whenever you want. See [Using This Repository as a Template](overview.md) for everything else about building on top of this template; this page is just the sync mechanism itself.

**Before anything else, the thing most people worry about here: this will not fill your project's history with the template's own commits.** Your `git log` stays exactly what it's always been: your own commits, plus one extra commit for whatever you just pulled in after a sync. Upstream's own commit-by-commit history (all the work that went into building this template) never gets attached to your project at all, no matter how many times you sync over the life of your project. What follows is purely about *file changes* landing in your project, not upstream's history becoming part of it.

If you've never pulled updates from a "template" repo into your own project before, that's fine. It's not a common everyday git workflow. Nothing below requires git knowledge beyond `git add` and `git commit`. Just follow the steps in order.

---

## Step by step

### Step 1: Check that you don't have unsaved work

```bash
git status
```

If this lists any files, save your work first: either commit it normally, or run `git stash` to set it aside temporarily. Why: the next steps will write changes into your project files, and if you also have your *own* unsaved changes sitting there at the same time, it gets confusing to tell which change came from where. Starting clean avoids that.

---

### Step 2: Run the sync script

Do this from the main folder of your project (the repo you created from **Use this template**). If you're on Windows, use **Git Bash** or **WSL** to run it, not PowerShell or the regular Command Prompt: it's a bash script and won't run there.

```bash
./scripts/upstream-sync/sync-upstream.sh
```

The very first time you run this, it also quietly sets up a second connection to the original template repo (git calls this a "remote", and this one's named `upstream`). That's just so the script knows where to download updates from. It does not touch your existing GitHub connection (`origin`) and does not push or upload anything anywhere. It only downloads.

---

### Step 3: Read what it found, and say yes or no

You'll see something like this printed:

```
Incoming commits from upstream/main:
a1b2c3d Add rate limiting to login
9f8e7d6 Fix OAuth redirect edge case

Sync these into the current branch now? [y/N]
```

That's the list of what's new upstream since you last synced (or ever, if this is your first time). Type `y` and press Enter if you want to bring those changes in. Type `N` (or just press Enter) if you'd rather wait: nothing will be changed, and you can run the script again later whenever you're ready.

---

### Step 4: The script copies upstream's changes into your files

This step is fully automatic: you don't type or decide anything here. For almost every file, this just quietly works: your code and upstream's code are kept in separate files/folders by design (see [overview.md](overview.md#the-app--mystic_auth-split)'s ownership table), so there's usually nothing to fight over. When it's done, one of four things will have happened, checked automatically in this order:

1. **Something silently failed to apply** (rare): go to [If it reports a silent partial apply](#if-it-reports-a-silent-partial-apply).
2. **It hit what's called a "conflict"**: go to **Step 6**.
3. **It produced two alembic migration heads** (rare, only if this app and upstream both added a migration since your last sync): go to [If it reports multiple alembic heads](#if-it-reports-multiple-alembic-heads).
4. **None of the above -- everything applied cleanly**: go to **Step 5**.

Most syncs hit none of 1-3 and go straight to Step 5. The two "rare" cases are safety nets, not expected steps -- they exist so a bad sync fails loudly instead of quietly.

---

### Step 5: Clean sync: you're basically done

You'll see normal `git commit` output on screen, ending with a message confirming the sync succeeded. Skip ahead to **Step 7**.

---

### If it reports a silent partial apply

Rarely, `git apply`/`git merge` can report a normal result (clean, or an ordinary conflict) while one file in the patch silently fails to apply at all, with nothing in the output distinguishing that from a real success. A changed binary file (a screenshot, an icon) in the middle of an otherwise-large patch is the most common trigger. The script guards against this by comparing the file list the diff says should have changed against what's actually changed/staged/conflicted afterward, and refuses to commit if they don't match:

```
ERROR: the diff said these files should have changed, but none of them show up as changed, staged, or conflicted:
  screenshots/mystic_auth/dashboard.png

This is the 'silent partial apply' failure mode -- ...
Work around it by re-diffing with the listed path(s) excluded (':!path' per file), then applying that instead, e.g. for a single file:
  git diff --binary <sha> upstream/main -- . ':!screenshots/mystic_auth/dashboard.png' | git apply --3way --index -
Then handle the excluded file(s) by hand (e.g. copy the file straight from upstream's working tree).
```

Nothing is committed when this fires -- run the suggested command to apply everything except the problem file(s), then copy the excluded file(s) over by hand (e.g. `git show upstream/main:screenshots/mystic_auth/dashboard.png > screenshots/mystic_auth/dashboard.png`) before committing. Once resolved, run the sync script again to pick up where you left off.

Note: this template's own screenshots live under `screenshots/mystic_auth/`, following the same `app/`/`mystic_auth/` ownership split used everywhere else in the repo (see [overview.md](overview.md#the-app--mystic_auth-split)). Put your own project's screenshots in `screenshots/app/` instead: since upstream never touches that folder, a sync can never collide with anything you put there, which is what causes this failure mode in the first place.

---

### Step 6: Conflict: resolve it

A "conflict" just means: you had made your own edit to a line, and upstream also changed that same line, so git can't automatically decide which version should win and needs a human (you) to pick. This is most likely in `backend/app/main.py` or `frontend/src/app/App.tsx`, since those are the two files you're expected to routinely edit (registering your own routers/routes), and only if you genuinely edited the exact same lines upstream did. It can also happen, less often, in a shared config file neither side "owns" outright: `frontend/package.json`, `backend/requirements.txt`, `docker-compose.yml`, `.env.example`, if you've edited the exact same line upstream touched (e.g. you'd already bumped the same dependency's version, or added your own dependency on the same line upstream reformatted). For most syncs, none of this happens at all. You'll see something like:

```
Conflicts staged above -- resolve them in your working tree, then:
  git add <resolved files>
  git commit -m "Sync upstream template updates (mystic-auth@<sha>)"
```

To fix it:

1. Open the file it mentions in your editor.
2. Look for blocks marked with `<<<<<<<`, `=======`, and `>>>>>>>`. This is git showing you both versions of the same spot: your version above the `=======`, upstream's version below it.
3. Decide what the combined result should look like. Almost always this means **keeping both** changes, just written one after another. Then delete the `<<<<<<<`/`=======`/`>>>>>>>` marker lines themselves.
4. Save the file, then run the two commands the script printed for you (shown above): `git add <the file>`, then `git commit -m "..."` with the message it suggested.

See [Resolving a conflict in `main.py` / `App.tsx`](#resolving-a-conflict-in-mainpy--apptsx) below for a full worked example with real code, if you want to see one before you hit this for real.

**A recurring shape of conflict you'll hit more than once: upstream rewording its own comments.** If upstream cleans up a comment sitting right next to a line you've customized (in `main.py`/`App.tsx`, most often), that shows up as a conflict on every sync until your side changes too, even though there's no real disagreement, just proximity. The sync script turns on [`git rerere`](https://git-scm.com/docs/git-rerere) (git's built-in "remember how I resolved this last time") the first time you run it. Resolve a conflict like that once, and if the exact same shape of conflict shows up on a later sync, git auto-resolves it for you and just tells you it did (`Resolved 'backend/app/main.py' using previous resolution.`) instead of stopping to ask again. You still get a chance to review it in your diff before committing.

---

### If it reports multiple alembic heads

Separately from a git conflict, the script checks whether this sync just produced two alembic migration heads: this app added its own migration on top of the same upstream commit that upstream *also* added a migration on top of. Nothing about a normal git merge would notice this (both files can land with zero conflicts), but `alembic upgrade head` will refuse to run afterward with `Multiple head revisions are present` until it's fixed. You'll see:

```
ERROR: multiple alembic heads detected (2):

  <revision-a>  <first line of that migration's docstring>
    backend/alembic/versions/<file-a>.py
  <revision-b>  <first line of that migration's docstring>
    backend/alembic/versions/<file-b>.py

...

Not committing -- resolve the alembic branch above first, then:
  git add backend/alembic/versions/<merge migration file>
  git commit -m "Sync upstream template updates (mystic-auth@<sha>)"
```

Fix it the same way you'd fix any two-heads alembic history, with a merge migration:

```bash
scripts/docker/backend-exec.sh alembic merge heads -m "merge migration branches"
git add backend/alembic/versions/
git commit -m "Sync upstream template updates (mystic-auth@<sha>)"
```

This check also runs standalone any time you want it, without syncing: `scripts/upstream-sync/check-alembic-heads.sh`.

---

### Step 7: Rebuild and test before you trust any of it

Even a sync that applied with zero conflicts can quietly change how the app behaves, so don't skip this:

```bash
docker compose up -d --build
scripts/docker/backend-exec.sh python -m pytest tests/backend/mystic_auth/unit tests/backend/mystic_auth/integration tests/backend/mystic_auth/security
```

`scripts/docker/backend-exec.sh` wraps `docker compose exec --user root -w /repo backend` with the two workarounds it needs to actually work everywhere: `--user root` (native Linux only, or pytest-cov's coverage output crashes with a permission error) and `MSYS_NO_PATHCONV=1` (Windows Git Bash only, or this fails with `Cwd must be an absolute path`). Both are no-ops on platforms that don't need them, so the one wrapped command is safe to run as-is regardless of what you're on. See [Docker Overview: running a one-off command inside a container](../docker/overview.md#running-a-one-off-command-inside-a-container) for the full explanation of both, if you ever need to run something the wrapper doesn't cover.

**A dependency rename is the sharpest example of why this step matters.** If `frontend/package.json` swaps out a dependency (e.g. `react-router-dom` was retired upstream in favor of `react-router` v8, since the old package stopped receiving security patches), the sync applies that swap to `package.json` and to every import inside `frontend/src/mystic_auth/`, since that's what upstream's own diff touches. It does **not** touch `frontend/src/app/`, your own code, even if it imports the exact same old package. Git sees no conflict there at all: `package.json` merges cleanly, so there's no marker to prompt you. The breakage only shows up as `npm run typecheck`/`npm run build` failing on a now-missing package once you run it, which is exactly what this step is for.

---

### Step 8: Push whenever you're happy with it

At this point you just have one new, ordinary commit sitting on top of your project's history, same as any commit you'd normally make. Push it to your branch, or open your own internal pull request to have a teammate look it over first. There's no PR or step required back against the original template repo; the sync only ever pulls, it never pushes anywhere.

---

## How it stays fast and accurate even after 20+ syncs

Behind the scenes, the script keeps a small tracked file, `.mystic-auth-sync-state`, containing the exact upstream commit you last synced to. It updates that file automatically every time you sync, right alongside the sync commit itself. Each new sync uses that file to look at only what changed upstream *since then*, rather than re-checking your entire codebase from scratch every time. That's what keeps the "what's new" list accurate and keeps unrelated files from ever being flagged, no matter how many releases you've already pulled in. You never read or edit this file yourself; just don't delete it. If it ever does go missing, the next sync safely falls back to checking everything from scratch (same as a first sync) rather than breaking.

`scripts/upstream-sync/sync-upstream.sh` itself is upstream-owned, same rule as [the rest of `mystic_auth/`](overview.md#the-app--mystic_auth-split): don't hand-edit it. If you're contributing a change to the sync mechanism itself, `scripts/upstream-sync/test-sync-upstream.sh` regression-tests it end-to-end against throwaway fake repos, without touching this repo's own history. Run it after any change to `sync-upstream.sh`.

That test suite also asserts every `scripts/**/*.sh` is tracked as mode `755` in this repo's own git index. This repo runs with `core.filemode=false` (common on Windows), so a plain local `chmod +x` never shows up as a diff. If you add a script and forget to make it executable, fix it with `git update-index --chmod=+x path/to/script.sh` instead.

**As a downstream user, you don't need to do anything about this.** A script under `scripts/**/*.sh` can occasionally land non-executable after a sync, for the same `core.filemode=false` reason. `sync-upstream.sh` checks for this and restores it automatically before deciding whether to commit -- you'd only notice from a line in the sync output (`Restoring the executable bit on scripts that lost it during this sync:`), never from a script failing to run.

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

Same process for `App.tsx`'s route list. After committing, rebuild and re-run the test suite before trusting it: see [Testing Overview](../testing/overview.md).
