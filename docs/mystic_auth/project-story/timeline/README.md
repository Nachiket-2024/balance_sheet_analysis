# How It Evolved

---

Companion to the [Project Story](../README.md). That page covers *why* this exists and how its
architecture settled into its current shape; this one is the day-by-day (well, commit-by-commit)
log of what actually happened, split out on its own since it only ever grows longer while the rest
of the story doesn't.

The commit history shows the real evolution, not a fully planned architecture from day one. The
first commit was on 18 August, 2025, and there's a 4-month gap between October 2025 and February
2026.

Completed entries below follow the same convention. Before a manual commit, the next change set
is recorded as a prospective numbered entry: it has the next `### Commit N: <date>` heading, a
quoted proposed subject, and concise bullets, but no hash or statistics until the commit exists.
The preceding entry is then completed with the real hash and exact `git show --shortstat` output.

Each completed entry below follows the same convention:

- Its own `### Commit N: <date>` heading, numbered sequentially across the whole history in commit
  order regardless of which of the five pages it lands on. No grouping by date range, and no
  relying on the date alone as a heading, since several days carry more than one commit. The
  numbering is split across five pages (see [Pages](#pages) below) purely to keep each file a
  readable size; it isn't a second, competing grouping.
- Opens with that commit's actual message in quotes.
- Then a bulleted list of what it actually did, checked against the real diff (`git show --stat`
  plus a real read of the changed files), not just the commit message: a terse or incomplete
  commit message doesn't excuse a terse or incomplete entry. Always `-` bullets, never numbered
  (the points are parallel facts about the commit, not ordered steps) and never prose paragraphs,
  so the format stays uniform across a one-line fix and a 591-file rewrite alike.
- Closes with its exact files-changed count (and, once the commit actually exists, its
  lines-changed count too) from `git show --shortstat`: a short entry is a small commit, a long one
  is a large or architecturally significant commit, not an editorial choice about how interesting
  the day was.

---

```mermaid
%%{init: {"themeVariables":{"fontSize":"16px","lineColor":"#334155","cScale0":"#0284c7","cScale1":"#16a34a","cScale2":"#d97706","cScale3":"#dc2626","cScale4":"#7c3aed","cScale5":"#0d9488","cScale6":"#db2777","cScale7":"#4338ca","cScaleLabel0":"#ffffff","cScaleLabel1":"#ffffff","cScaleLabel2":"#ffffff","cScaleLabel3":"#ffffff","cScaleLabel4":"#ffffff","cScaleLabel5":"#ffffff","cScaleLabel6":"#ffffff","cScaleLabel7":"#ffffff"}} }%%
timeline
    title Major milestones (main branch)
    August 2025: Auth foundation, role-based tables
                : OAuth2, rate limiting, brute-force lockout
                : Frontend skeleton, Tailwind tried and dropped
    September 2025: httpOnly cookies, first full OAuth2 flow end-to-end
                   : Token table rework, backend fully commented
                   : Logout-all reworked, TokenCRUD/UserCRUD modularized
                   : Token tables removed for Redis-only sessions
    October 2025: Fully Dockerized (all services together)
                 : Celery replaced with Taskiq
                 : Frontend flickering fixed, full auth flow reconfirmed
    February 2026: Work resumes after 4-month gap
                  : Frontend rebuilt on Chakra UI
    April 2026: Role tables collapsed into one users table
               : Forgot-password flow, HTML emails
    July 2026: PBAC, audit logging, CI/CD, tests, docs
              : Refresh-token race fixes, password-change session revocation
              : Bugsink error monitoring and SDK exports
              : app / mystic_auth template split
              : Template docs, sync workflow, Docker/dev-up, logging
    August 2026: UI, backend changes, session/logout-all fixes
                : Codebase restructure, PBAC/reset-token security fixes
                : Language toggle and i18n addition
                : Account deletion/purge, PBAC grant guard, command palette
                : Replaced Taskiq with Procrastinate, added rate-limit dashboard, geolocation
                : Brand color, legal consent pages, least-privilege DB role
                : PBAC granularity, live security testing, backup scheduling
    September 2026: Local-prod tunnel modes added for ngrok, Tailscale Funnel
                   : Playwright E2E tests, pg_dump backups
                   : Self-role escalation fix, patched security headers, Docker images
                   : Live security audit, Alpine base image, login-lockout race fix
                   : Fixed i18n namespace mutation, multi-fork Docker collision avoidance
                   : Env-file bootstrap/sync tooling, AI agent setup prompts
                   : docker/env split into app/mystic_auth, Makefile
                   : Frontend migrated to shadcn/Radix
                   : Backblaze B2 backup verification, boot-shell, mobile LCP fixes
    October 2026: Coverage increase, backend tooling, backup, sync hardening
                  : Durable token revocation, lifecycle event queue, backup HMAC verification
                  : Split CI ownership, downstream validation fixes
                  : Runtime hardening, dependency notices, production validation, and documentation corrections
```

---

## Pages

- [August 2025](2025-aug.md): commits 1-16, 18 August, 2025 to 31 August, 2025.
- [September-October 2025](2025-sep-oct.md): commits 17-36, 1 September, 2025 to 14 October, 2025.
- [February-July 2026](2026-feb-jul.md): commits 37-53, 21 February, 2026 to 29 July, 2026.
- [August 2026](2026-aug.md): commits 54-69, 2 August, 2026 to 29 August, 2026.
- [September 2026](2026-sep.md): commits 70-77, 4 September, 2026 to 29 September, 2026.
- [October 2026](2026-oct.md): commits 78-81, 1 October, 2026 to 11 October, 2026.

---

## The tools that built it

See [The Tools That Built It](../tools.md) for the two workflows: manual ChatGPT + VS Code for most of it, then Claude Code (and briefly Codex) from July 2026 on.

---
