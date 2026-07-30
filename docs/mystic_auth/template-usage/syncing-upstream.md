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

### Step 2: Run the sync script

Do this from the main folder of your project (the repo you created from **Use this template**). If you're on Windows, use **Git Bash** or **WSL** to run it, not PowerShell or the regular Command Prompt: it's a bash script and won't run there.

```bash
./scripts/sync-upstream.sh
```

The very first time you run this, it also quietly sets up a second connection to the original template repo (git calls this a "remote", and this one's named `upstream`). That's just so the script knows where to download updates from. It does not touch your existing GitHub connection (`origin`) and does not push or upload anything anywhere. It only downloads.

### Step 3: Read what it found, and say yes or no

You'll see something like this printed:

```
Incoming commits from upstream/main:
a1b2c3d Add rate limiting to login
9f8e7d6 Fix OAuth redirect edge case

Sync these into the current branch now? [y/N]
```

That's the list of what's new upstream since you last synced (or ever, if this is your first time). Type `y` and press Enter if you want to bring those changes in. Type `N` (or just press Enter) if you'd rather wait: nothing will be changed, and you can run the script again later whenever you're ready.

### Step 4: The script copies upstream's changes into your files

This step is fully automatic: you don't type or decide anything here. For almost every file, this just quietly works: your code and upstream's code are kept in separate files/folders by design (see [overview.md](overview.md#the-app--mystic_auth-split)'s ownership table), so there's usually nothing to fight over. When it's done, one of two things will have happened:

- Everything applied without a problem: go to **Step 5**.
- It hit what's called a "conflict": go to **Step 6**.

### Step 5: Clean sync: you're basically done

You'll see normal `git commit` output on screen, ending with a message confirming the sync succeeded. Skip ahead to **Step 7**.

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

### Step 7: Rebuild and test before you trust any of it

Even a sync that applied with zero conflicts can quietly change how the app behaves, so don't skip this:

```bash
docker compose up -d --build
docker compose exec --user root -w /repo backend python -m pytest tests/backend/mystic_auth/unit tests/backend/mystic_auth/integration tests/backend/mystic_auth/security
```

(`--user root` is needed on native Linux, or pytest-cov's coverage output crashes with a permission error; on Windows with Git Bash specifically, this can also fail separately with `Cwd must be an absolute path`: see [Docker Overview: running a one-off command inside a container](../docker/overview.md#running-a-one-off-command-inside-a-container) for both and their fixes.)

**A dependency rename is the sharpest example of why this step matters.** If `frontend/package.json` swaps out a dependency (e.g. `react-router-dom` was retired upstream in favor of `react-router` v8, since the old package stopped receiving security patches), the sync applies that swap to `package.json` and to every import inside `frontend/src/mystic_auth/`, since that's what upstream's own diff touches. It does **not** touch `frontend/src/app/`, your own code, even if it imports the exact same old package. Git sees no conflict there at all: `package.json` merges cleanly, so there's no marker to prompt you. The breakage only shows up as `npm run typecheck`/`npm run build` failing on a now-missing package once you run it, which is exactly what this step is for.

### Step 8: Push whenever you're happy with it

At this point you just have one new, ordinary commit sitting on top of your project's history, same as any commit you'd normally make. Push it to your branch, or open your own internal pull request to have a teammate look it over first. There's no PR or step required back against the original template repo; the sync only ever pulls, it never pushes anywhere.

---

<details>
<summary>How it stays fast and accurate even after 20+ syncs (optional, for the curious)</summary>

Behind the scenes, the script keeps a small tracked file, `.mystic-auth-sync-state`, containing the exact upstream commit you last synced to. It updates that file automatically every time you sync, right alongside the sync commit itself. Each new sync uses that file to look at only what changed upstream *since then*, rather than re-checking your entire codebase from scratch every time. That's what keeps the "what's new" list accurate and keeps unrelated files from ever being flagged, no matter how many releases you've already pulled in. You never read or edit this file yourself; just don't delete it. If it ever does go missing, the next sync safely falls back to checking everything from scratch (same as a first sync) rather than breaking.

</details>

`scripts/sync-upstream.sh` itself is upstream-owned, same rule as [the rest of `mystic_auth/`](overview.md#the-app--mystic_auth-split): don't hand-edit it. If you're contributing a change to the sync mechanism itself, `scripts/test-sync-upstream.sh` regression-tests it end-to-end against throwaway fake repos, without touching this repo's own history. Run it after any change to `sync-upstream.sh`.

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
