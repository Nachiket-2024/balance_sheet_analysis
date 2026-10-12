# Agent Prompts

Ready-to-paste starting prompts for handing common mystic-auth-template
tasks to an AI coding agent (Claude Code, Codex, or similar) instead of
following the docs by hand.

| File | Use when | Assumes |
|---|---|---|
| [`new-project-setup.md`](new-project-setup.md) | You just clicked "Use this template" and cloned your new repo for the first time. See [Template Usage: Quickstart](../../docs/mystic_auth/template-usage/quickstart.md) for what each step does. | Docker installed, agent has a shell in the repo root. Tell it your app name/brand color when you hand it the file, or it'll ask. |
| [`sync-with-upstream.md`](sync-with-upstream.md) | Your project already exists and you want to pull in the latest mystic-auth template fixes/features. See [Staying in Sync with Upstream Template Updates](../../docs/mystic_auth/template-usage/syncing-upstream/README.md) for the manual version this automates, and [agent-prompt.md](../../docs/mystic_auth/template-usage/syncing-upstream/agent-prompt.md) for the reasoning behind it. | A clean Git index, Docker, and an upstream remote or network access. Unstaged and untracked work is temporarily preserved by the sync script; staged work must be committed or stashed first. The script creates one sync commit; use the documented soft-reset review flow if the owner wants to inspect it before committing. It reads only the non-secret project name, app name, and brand color from the dev env file, and uses the current CI checks as the verification baseline, including configured database roles, app-neutral browser assertions, and safe background-job cleanup. |

Each file is nothing but the prompt itself: hand the whole file to your
agent (e.g. "read new-project-setup.md and follow it") and it needs
nothing else added, beyond whatever the "Assumes" column above calls out.

---

## Why these avoid putting real secrets in the agent's context

Both prompts eventually touch env files that hold real credentials
(`GOOGLE_CLIENT_SECRET`, `GMAIL_APP_PASSWORD`, database passwords, ...). An
agent's tool output becomes part of its own context and transcript, so
having it `cat` a file full of secrets to "read them, then write them
somewhere else" puts those values somewhere they don't need to be, for no
real benefit over just moving them directly.

Both prompts route around this the same way: `scripts/mystic_auth/env-tools/setup-env/`,
`scripts/mystic_auth/env-tools/copy-env-values/`, and `scripts/mystic_auth/env-tools/set-env-field/` do the actual
reading and writing themselves, and none of them ever print a secret
value to their own output, only field *names*. The agent runs the script
and reports which fields still need a real value; a human fills those in
directly, either straight into the env file or into
`scripts/mystic_auth/env-tools/set-env-field/shared-values.env` (a copy of that folder's
`shared-values.env.example`, gitignored) so one edit reaches every mode at once. See
[Environment Configuration](../../docs/mystic_auth/environment/README.md) for
what each script actually does.
