# Project Story

## Where this started

This project started because I got tired of rebuilding the same authentication and authorization pieces for different startup take-home assignments.

During 2025, while applying to startups, many take-home projects needed similar foundations with slightly different expectations: one needed email/password authentication, another needed OAuth2, another wanted RBAC. Each time, the actual product logic was slowed down because much time went into rebuilding the same authentication foundation.

The original idea was simple:

> Build auth + OAuth2 + a basic authorization layer once, then reuse it.

I assumed this would take a week or two. Almost a year later, after working on it on and off between a master's programme and long gaps where I didn't touch it at all, it's still going. It grew into a full template with PBAC, audit logging, CI/CD, and a real test suite instead of the small module I set out to build.

Authentication looks small from the outside: a login endpoint, a logout endpoint, maybe a token. It quickly becomes its own engineering domain. The project expanded into understanding and implementing:

- refresh token rotation and reuse detection,
- session storage decisions,
- Redis-based session and token management,
- rate limiting,
- brute-force protection,
- cookie security,
- OAuth2 PKCE flows,
- background email delivery through asynchronous workers,
- database migrations,
- CI validation,
- frontend authorization handling.

What started as a shortcut for future projects became a project of its own.

---

## How it evolved

The commit history shows the real evolution, not a fully planned architecture from day one. 53 commits on `main`, from the first on 18 Aug 2025 to the most recent on 29 Jul 2026. There's a 4-month gap between October 2025 and February 2026. Below, days committed back-to-back are grouped into one range; an isolated day stands on its own.

```mermaid
timeline
    title Major milestones (main branch)
    Aug 2025: Auth foundation, role-based tables
            : OAuth2, rate limiting, brute-force lockout
            : Frontend skeleton, Tailwind tried and dropped
    Sep 2025: httpOnly cookies, first full OAuth2 flow end-to-end
            : Token table rework, backend fully commented
            : Logout-all reworked, TokenCRUD/UserCRUD modularized
            : Token tables removed for Redis-only sessions
    Oct 2025: Fully Dockerized (all services together)
            : Celery replaced with Taskiq
            : Frontend flickering fixed, full auth flow reconfirmed
    Feb 2026: Work resumes after 4-month gap
            : Frontend rebuilt on Chakra UI
    Apr 2026: Role tables collapsed into one users table
            : Forgot-password flow, HTML emails
    Jul 2026: PBAC + audit logging + CI/CD (single commit)
            : Follow-up hardening, Bugsink + sdk.py/sdk.ts
            : app / mystic_auth split, docker prod, extension points, CORS
            : react-router fix, dev-up script fix, logging polish, resend-verification
```

### Aug 18-23, 2025

The first version focused on authentication. It started with a bare FastAPI skeleton, then in quick succession: modular auth logic with role-based tables, OAuth2 plus rate limiting and brute-force protection, a refactor of the auth flow and role tables around standard security practices, and a logout-from-all-devices endpoint (both on the 21st).

Then role-based routes landed with `main.py`, and the run closed with a move to generic, permission-injected routes plus the first Alembic migration. That same day, the frontend's first commits appeared: a bare TypeScript + React setup.

Rate limiting and brute-force protection showed up on day three because security concerns became obvious while building the foundation, not because they were planned upfront.

### Aug 26-28, 2025

Tailwind CSS was tried and then replaced by plain CSS. The same day, modular slice/types/button/form files and `store.ts` were added. Auth route pages were wired into `App.tsx`, and all `axios` calls were centralized into a single API folder: the frontend's first pass at having a consistent shape.

The stretch that followed involved the biggest learning curve of the project.

### Aug 30 - Sep 2, 2025

Frontend imports were corrected and Tailwind re-added. Then HTTP-only cookies for tokens landed, and a basic OAuth2 flow started working end-to-end across frontend, backend, Redis, and Postgres: the first time all the moving pieces talked to each other. Auth code was modularized and a basic dashboard integrated into the frontend, and logout was reworked on both the frontend and backend, including component files for the logout/logout-all buttons.

### Sep 4-5, 2025

The token table was changed and cookie-setting modularized. The backend was fully commented, with the token CRUD corrected across its call sites (the largest commit of this stretch, at ~2,000 changed lines). The OAuth2 service logic and the frontend's auth slice/API were updated to match.

### Sep 7, 2025

Single-device OAuth2 login and logout both worked end-to-end with the updated token logic.

### Sep 13-14, 2025

The logout-all handler was reworked alongside a round of backend commenting; its own commit message notes "not done yet". Then `TokenCRUD` and `UserCRUD` were both fully modularized.

### Sep 16, 2025

Logout logic was updated so `is_active` correctly flips to `false` on logout.

### Sep 18, 2025

The token table's field structure changed again: mostly a cleanup, with more lines removed than added as redundant fields were dropped.

### Sep 22-24, 2025

Token tables were removed entirely in favor of Redis-only token management (the last of these commits again flagged "not done yet" mid-migration). OAuth2 login was re-verified against the new logic, and logout/logout-all was confirmed working end-to-end. `UserCRUD` was updated alongside a new signup page, and the stretch closed with logging added across the backend.

This four-week stretch, from late August through late September, was where the project stopped being "just implementing features" and started being about the underlying security decisions. Questions like where tokens should live, how refresh-token reuse detection should work, and what logout-all should actually revoke became architectural decisions, not coding tasks.

### Oct 6, 2025

The app was fully Dockerized, with OAuth2 login and logout tested end-to-end inside containers. This was the first time backend, frontend, PostgreSQL, Redis, background workers, migrations, and environment configuration were all managed together as one system, instead of pieces run separately.

### Oct 10, 2025

Celery was replaced with Taskiq. Celery was considered first because it's widely used, but since the backend was built around async patterns, the worker model created friction. After comparing ARQ, Dramatiq, and Taskiq, Taskiq fit the async-first approach best (ARQ was close, but Taskiq's FastAPI integration was cleaner). This was a large commit (61 files), and its own message admits it left "frontend issues" behind: the swap wasn't clean on the first pass, even though the actual requirement (reliably sending verification and password-reset emails) was simple.

### Oct 14, 2025

The frontend flickering issue from the Taskiq swap was resolved, with signup, login, logout, and logout-all all confirmed working again.

---

### Feb 21, 2026

Work resumed after the 4-month gap by fixing the OAuth2 login flow, which hadn't been fully solid before the break.

### Feb 26-28, 2026

The UI was rebuilt on Chakra UI: the login page first, with Tailwind removed (the largest of the three commits, at ~2,000 changed lines), then signup, verify-account, and dashboard pages, and finally the dashboard updated to show real user details alongside a reworked signup page.

The frontend also moved toward feature-based organization, mirroring the backend: auth, dashboard, and profile. Redux was still the frontend state management foundation at this point.

---

### Apr 12, 2026

Earlier role-based tables were collapsed into a single `users` table with a role enum: the authorization data model's first big simplification.

### Apr 14, 2026

Forgot-password frontend support and stronger backend password-reset validation landed first (the larger of the two commits, at ~2,400 changed lines), followed the same day by HTML email templates, a reset cooldown, and a fix for loading-state flashes in the UI.

---

## Architecture evolution

The architecture wasn't designed perfectly from the beginning. Early on, I explored different structures, including more traditional MVC-style approaches and layouts copied from examples found online.

As the project grew, a problem became obvious: authentication flows aren't isolated files. A single feature could involve API routes, schemas, services, handlers, database models, frontend pages, API clients, state management, and tests. When these pieces were spread across unrelated folders, debugging got harder, because understanding one flow meant jumping across many locations.

So instead of organizing only by technical type:

```text
controllers/
services/
models/
schemas/
```

I moved toward grouping related behavior together, by feature instead of by layer.

Here's the structure right before the PBAC and Claude Code sprint, in the last commit of the manual, ChatGPT-assisted era on 14 Apr 2026:

```text
backend/
  app/
    api/
      auth_routes/
      user_routes/

    auth/
      current_user/
      login/
      logout/
      logout_all/
      oauth2/
      password_logic/
      password_reset_confirm/
      password_reset_request/
      refresh_token_logic/
      security/
      signup/
      token_logic/
      verify_account/

    core/
    database/
    logging/
    redis/
    scripts/
    taskiq_tasks/
    user_crud/
    user_table/

frontend/
  src/
    api/

    auth/
      current_user/
      login/
      logout/
      logout_all/
      oauth2/
      password_reset_confirm/
      password_reset_request/
      signup/
      verify_account/

    core/
    dashboard/
    store/
```

Grouping code around business flows, instead of forcing every feature across separate technical layers, made changes easier: everything needed for a feature lived close together. Changing login behavior meant working mostly inside the authentication area, not hunting across unrelated controller, service, and model folders.

This wasn't chosen because it's the only "correct" architecture. It was chosen because, for this project's size and workflow, it made the system easier to understand, debug, and extend. That decision mattered even more later, when the PBAC and Claude Code sprint below brought the biggest change yet.

---

### Jul 14, 2026

After a 3-month gap, the biggest change happened in a single commit: 364 files touched (+27,663/-8,184 lines), moving the project from a role-based authorization system to Policy-Based Access Control (PBAC). Instead of access being decided by a role column, authorization decisions are now based on assigned policies, allowed actions, resources, and optional conditions. Roles became descriptive metadata rather than the source of truth for permissions. PBAC wasn't part of the original design; it was added once role-based access started showing its limits.

That same commit also added audit logging, security hardening, improved headers and middleware, stronger cookie/security handling, CI/CD pipelines, extensive backend and frontend testing, and complete documentation. The project moved from "a reusable auth module" into a complete authentication and authorization foundation in one pass, not incrementally. Frontend state management was redesigned too, in the same commit: Redux was replaced with Zustand for client state and TanStack Query for server state.

### Jul 18, 2026

A follow-up pass over the 14th's big commit, hardening it further now that it had had a few days to settle. The main fixes: a couple of real session/token bugs (a roleless OAuth2 account getting logged out on refresh, a race condition in refresh-token rotation, an expired-token cleanup that never ran), a password-change flow that now asks for your current password and logs out other sessions, and a handful of smaller admin/config fixes. CI also got a real coverage gate and dependency scanning for the first time. This is roughly where `template-usage.md` and this file were first written, and the known-issues doc got trimmed down to what was still actually true.

### Jul 20, 2026

Running the template against my other projects surfaced a couple of small logout and rate-limiter bugs, fixed here. That's the kind of thing real usage catches that reading the code alone wouldn't. Alongside that, self-hosted error monitoring landed via Bugsink, so real errors get logged somewhere instead of just showing up in server logs. The `sdk.py`/`sdk.ts` files were introduced too, a single file on each side that re-exports the pieces meant to be built on, so future code doesn't have to reach into the template's internals directly. The frontend also got reorganized into proper feature folders.

### Jul 25-29, 2026

This stretch turned the repo from "reusable codebase" into a real template. The code was split into upstream-owned internals (`backend/mystic_auth/`, `frontend/src/mystic_auth/`) and thin project-owned shells (`backend/app/`, `frontend/src/app/`), with `sdk.py`/`sdk.ts` and `app_sdk.py`/`app_sdk.ts` as the extension surface. Docs and tests were split the same way, `scripts/sync-upstream.sh` was added for future template updates, and the template-usage docs grew the ownership model, sync workflow, worked example, RBAC quickstart, and shared sidebar/CORS/nav extension points.

The rest came from running the template against real downstream projects. That caught an `sdk.ts` import bypass, an event-loop-blocking token signature, logout and rate-limiter bugs, a Bugsink Gunicorn timeout issue, a prod OAuth redirect gotcha, and the stale `react-router-dom` package with an unpatched advisory, fixed by moving to `react-router` v8 and making npm audit blocking again. Docker and day-to-day operations were tightened too: `scripts/dev-up.sh` became the quieter default startup path, frontend Compose builds got `pull_policy: build`, `watch_for_late_dsn()` catches Bugsink's DSN after slow cold boots, backend logging became dev-readable and production-structured, and stale docs/comments/config were cleaned up. A resend verification email flow was added for users who tried to verify their account after the verification link had expired, the background email worker got terminal-visible logging, and a PowerShell dev-up bug got fixed so the startup logs it always promised actually showed up.

---

## The tools that built it

Two very different workflows built this project: a manual ChatGPT + VSCode loop for most of it, then an agentic coding loop with Claude Code from July 2026 on and Codex joining from the commit of 28 July (Yeah, I hit my Claude Code weekly limit). The workflow details and diagram live in [The Tools That Built It](tools.md).

---

## Why it is a template now

Somewhere during the infrastructure and security work, this stopped being just a personal shortcut. The problems solved here, authentication, sessions, permissions, security controls, audit trails, email workflows, and testing, come up in almost every application with users.

The point of this template isn't just saving development time. It's a starting point with documented architectural decisions, tested authentication flows, reusable authorization patterns, and security considerations already handled, so a new project can start from a stronger baseline and focus on the actual product being built.

See [Using This Repository as a Template](../template-usage/overview.md) for how to adapt it.