# Project Story
---

## Where this started

This project started because I got tired of rebuilding the same authentication and authorization pieces for different startup take-home assignments.

During 2025, while applying to startups, many take-home projects needed similar foundations with slightly different expectations: one needed email/password authentication, another needed OAuth2, another wanted role-based access control. Each time, the actual product logic was slowed down because much time went into rebuilding the same authentication foundation.

The original idea was simple:

> Build auth + OAuth2 + a basic authorization layer once, then reuse it.

I assumed this would take a week or two. Almost a year later, after working on it on and off between a master's programme and long gaps where I didn't touch it at all, it's still going. It grew into a full template with PBAC, audit logging, CI/CD, and a real test suite instead of the small module I set out to build.

Authentication looks small from the outside: a login endpoint, a logout endpoint, maybe a token. It quickly becomes its own engineering domain. The project expanded into understanding and implementing:

- refresh token rotation and reuse detection,
- session storage decisions,
- Valkey-based session and token management,
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

The commit-by-commit log of what actually happened, from the first commit on 18 August, 2025
through today, got long enough to outgrow this page: see [How It Evolved](timeline/README.md) for the
full timeline and milestone diagram.

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

This was the structure right before the PBAC and Claude Code sprint, in the last commit of the manual, ChatGPT-assisted era on 14 April, 2026:

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
    valkey/
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

This wasn't chosen because it's the only "correct" architecture. It was chosen because, for this project's size and workflow, it made the system easier to understand, debug, and extend. That decision mattered even more later, when a single commit on 14 July, 2026 moved the project from role-based access to PBAC, the biggest change the codebase went through: see [How It Evolved](timeline/2026-feb-jul.md#commit-44-14-july-2026) for that commit and everything after it, day by day.

---

## The tools that built it

Two very different workflows built this project: a manual ChatGPT + VSCode loop for most of it, then an agentic coding loop with Claude Code from July 2026 on and Codex joining from the commit of 28 July, 2026 (Yeah, I hit my Claude Code weekly limit) for a few days until I exhausted my free Codex credits. The workflow details and diagram live in [The Tools That Built It](tools.md).

---

## Why it is a template now

Somewhere during the infrastructure and security work, this stopped being just a personal shortcut. The problems solved here, authentication, sessions, permissions, security controls, audit trails, email workflows, and testing, come up in almost every application with users.

The point of this template isn't just saving development time. It's a starting point with documented architectural decisions, tested authentication flows, reusable authorization patterns, and security considerations already handled, so a new project can start from a stronger baseline and focus on the actual product being built.

See [Using This Repository as a Template](../template-usage/overview.md) for how to adapt it.

---
