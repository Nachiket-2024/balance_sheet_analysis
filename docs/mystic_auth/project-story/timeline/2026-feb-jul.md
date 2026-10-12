# How It Evolved: February-July 2026

---

### Commit 37: 21 February, 2026

`3e4a3a5`: "Fixed Oauth2 login flow"

- Work resumed after the 4-month gap by fixing the OAuth2 login flow, which hadn't been fully solid before the break.
- The standalone `docker/nginx/` container (its own `Dockerfile` + `nginx.conf`) was also dropped in the same commit: nginx's job folded into the frontend container instead.

*5 files changed · +155/-187 lines*

---

### Commit 38: 26 February, 2026

`78c42bf`: "Login Page updated with Chakra UI ;Tailwind CSS removed"

- The login page rebuilt on Chakra UI, with Tailwind removed (`tailwind.css` deleted).
- `App.tsx` (269 lines), `LoginForm.tsx`, and `LoginPage.tsx` (183 lines) all substantially rewritten.
- The largest of the three Chakra-migration commits.

*10 files changed · +1,987/-404 lines*

---

### Commit 39: 27 February, 2026

`40b816f`: "Signup, Login, Verify Account, Dashboard pages updated with Chakra UI"

- `SignupForm.tsx` rewritten most heavily (315 lines changed).
- `OAuth2LoginButton.tsx` split into logic + a new `OAuth2LoginButtonComponent.tsx`, matching the logic/presentation split `LogoutButton`/`LogoutAllButton` already used.
- `VerifyAccountButton.tsx` and `VerifyAccountPage.tsx` reworked.
- `DashboardPage.tsx` updated.

*17 files changed · +868/-622 lines*

---

### Commit 40: 28 February, 2026

`d17f740`: "Dashboard page modified to show user details ;Sign up page updated"

- Dashboard page modified to show real user details (173 of the 177 changed lines landed here).
- Signup page updated to match.
- Redux was still the frontend state management foundation at this point, and the frontend was moving toward feature-based organization mirroring the backend: auth, dashboard, and profile.

*6 files changed · +177/-51 lines*

---

### Commit 41: 12 April, 2026

`7c06836`: "Refactored role-based tables into a single users table with role enum"

- `access_control/role_checker.py`, `role_permissions.py`, and `role_tables.py` deleted.
- The single generic `role_routes.py` (234 lines) deleted, replaced by `api/user_routes/user_routes.py` (325 lines, new).
- `roles/admin/`, `roles/role1/`, `roles/role2/` model/schema files all deleted, replaced by one `user_table/user_model.py` (82 lines) + `user_schema.py` (87 lines), plus a new `user_crud_modules/user_role_crud.py` (84 lines).
- `scripts/create_system_user.py` added (84 lines): the reserved system-superuser account, since a single-table role model needs one account that can't be demoted by mistake.

*38 files changed · +1,097/-1,072 lines*

---

### Commit 42: 14 April, 2026

`1943f16`: "Added forgot password frontend and improved backend password reset validation"

- A new password-reset-request flow and its own page/form/slice landed (previously reset relied on a single combined flow).
- Nearly every existing auth flow file touched to route through it (`ProtectedRoute.tsx`, `current_user_slice.ts`, login/logout/logout-all/OAuth2/signup/verify-account).
- `PasswordResetConfirmForm.tsx` alone changed by 343 lines.
- The larger of the two password-reset commits.

*49 files changed · +2,400/-1,168 lines*

---

### Commit 43: 14 April, 2026

`946e384`: "Enhanced emails with HTML templates, added cooldown to password reset, fixed loading flashes"

- `taskiq_tasks/email_tasks.py` grew to render HTML rather than plain text.
- `password_reset_service.py` and `account_verification_service.py` both picked up the cooldown logic.
- `PasswordResetRequestForm.tsx` grew by 56 lines to show it.

*8 files changed · +280/-62 lines*

---

### Commit 44: 14 July, 2026

`a66bc91`: "Added PBAC, audit logging, security hardening, frontend updates, CI, tests, and docs"

After a 3-month gap, the biggest single change in the project's history: 364 files touched.

- **role-based access control → PBAC.** Authorization decisions moved off a role column onto assigned policies, allowed actions, resources, and optional conditions; roles became descriptive metadata rather than the source of truth for permissions. Not part of the original design: role-based access control was built first, before the frontend existed, then replaced for clearer and more granular permissions. Since the role-based access control UI wasn't done yet and the backend role-based access control work was minimal, switching didn't break much, and it was worth doing early rather than retrofitting later.
- Audit logging added.
- Security hardening, headers and middleware, and cookie/security handling strengthened.
- CI/CD pipelines set up.
- Extensive backend and frontend testing added.
- Broad documentation written.
- Frontend state management redesigned: Redux replaced with Zustand (client state) and TanStack Query (server state).

*364 files changed · +27,663/-8,184 lines*

---

### Commit 45: 18 July, 2026

`291f3f9`: "Updated documentation, fixed audit findings, and improved app configuration"

- A couple of real session/token bugs fixed: a roleless OAuth2 account getting logged out on refresh, a race condition in refresh-token rotation, an expired-token cleanup that never ran (visible in `jwt_service.py`'s 95-line change and `refresh_token_service.py`'s 52-line change).
- A password-change flow that now asks for the current password and logs out other sessions.
- A handful of smaller admin/config fixes.
- `emails/email_sender.py` introduced (47 lines) to isolate the SMTP transport behind its own module.
- CI got a real coverage gate and dependency scanning for the first time (`.github/workflows/ci.yml` +45 lines).
- `docs/project-story/README.md` (382 lines) and `docs/template-usage.md` (143 lines) both written for the first time in this commit (this is where the project story and template-usage docs actually began).
- The known-issues doc trimmed down to what was still actually true.

*132 files changed · +5,438/-3,197 lines*

---

### Commit 46: 20 July, 2026

`bc8a43f`: "Added Bugsink error monitoring, SDK, restructured frontend; fixed logout, rate limits."

- Running the template against other projects surfaced a couple of small logout and rate-limiter bugs, fixed here: the kind of thing real usage catches that reading the code alone wouldn't.
- Self-hosted error monitoring landed via a new `error_monitoring/sentry_service.py` (110 lines) and frontend `core/errorMonitoring.ts` (46 lines), backed by Bugsink, so real errors get logged somewhere instead of just showing up in server logs.
- `backend/app/sdk.py` (52 lines) and `frontend/src/sdk.ts` (40 lines) introduced: a single file on each side re-exporting the pieces meant to be built on, so future code doesn't have to reach into the template's internals directly.
- The frontend's flat `components/` folder split into top-level `authorization/`, `layout/`, and `ui/` folders, reorganized into proper feature folders.

*136 files changed · +2,388/-364 lines*

---

### Commit 47: 25 July, 2026

`41f43dc`: "Restructured with app/mystic_auth split, sync script, diagrams, env defaults"

- The code split into upstream-owned internals (`backend/mystic_auth/`, `frontend/src/mystic_auth/`) and thin project-owned shells (`backend/app/`, `frontend/src/app/`), with `sdk.py`/`sdk.ts` and `app_sdk.py`/`app_sdk.ts` as the extension surface.
- Docs and tests split the same way.
- `scripts/sync-upstream.sh` added for future template updates.
- Diagrams and env defaults added.
- This is where the repo turned from "reusable codebase" into a real template, mainly because of running it against real downstream projects.

*419 files changed · +2,914/-2,587 lines*

---

### Commit 48: 26 July, 2026

`55907ed`: "Fixed password hash error handling, enabled Bugsink in prod, updated deps and docs"

- Password hash error handling fixed.
- Bugsink enabled in production (`docker-compose.prod.yml` +75 lines).
- Dependencies and docs updated.
- `scripts/test-sync-upstream.sh` (168 lines) added as the sync script's own regression suite.
- `docs/template-usage.md` substantially rewritten (327 of its lines changed).

*44 files changed · +1,233/-635 lines*

---

### Commit 49: 27 July, 2026

`c191f46`: "Added sidebar/SDK extension, multi-origin CORS, Docker CI, and docs fixes"

- `create_system_user.py` grew by 135 lines, and `docs/authentication/system-superuser.md` (72 lines) documented it for the first time.
- `docs/authorization/common-patterns.md` (41 lines) and `docs/docker/validation-history.md` (47 lines) added.
- `docs/template-usage.md` (287 lines) deleted and split into `template-usage/overview.md`, `syncing-upstream.md`, and `worked-example.md`: the first page-per-topic split of what had been one long file.
- `docs/project-story/tools.md` written for the first time (45 lines): "the tools that built it" page.
- CI workflow grew by 156 lines, and `layout/AppLayout.tsx`/`Sidebar.tsx`/`navItems.ts` picked up the sidebar extension points.

*50 files changed · +1,547/-479 lines*

---

### Commit 50: 27 July, 2026

`d608134`: "Unblocked JWT calls in password reset, added role-based access control doc/seed, restructured tests, updated docs"

- JWT calls unblocked in the password reset flow.
- An role-based access control quickstart doc/seed added (`scripts/create_unconditioned_policies.py`, 101 lines; `docs/authorization/unconditioned-policy-quickstart.md`, 51 lines).
- The entire backend unit test suite restructured: `tests/backend/mystic_auth/unit/` moved from one flat folder into per-feature subfolders (`api/`, `auth/login/`, `auth/logout/`, `auth/oauth2/`, `authorization/`, `core/`, `error_monitoring/`, `logging/`, `scripts/`, `user_crud/`, and more): 85 files touched, nearly all of them pure moves with no content change.

*85 files changed · +291/-31 lines*

---

### Commit 51: 28 July, 2026

`b66c63a`: "Added dev-up.sh, fixed Bugsink timeout, and fixed script permissions"

- `scripts/dev-up.sh` added (99 lines) as the quieter default startup path.
- A Bugsink Gunicorn timeout fixed.
- The executable bit restored on `database-backup.sh`/`database-restore.sh`/`sync-upstream.sh`/`test-sync-upstream.sh`: script permissions had silently reverted, the first appearance of the `core.filemode=false` problem this repo's sync tooling would later check for automatically.

*15 files changed · +259/-16 lines*

---

### Commit 52: 28 July, 2026

`8771eb3`: "Upgraded react-router v8 (CSRF fix), fixed DSN race and logging mismatch"

- Caught an `sdk.ts` import bypass.
- Fixed an event-loop-blocking token signature.
- Fixed a deployed OAuth redirect gotcha.
- The stale `react-router-dom` package carrying an unpatched advisory replaced by moving to `react-router` v8, and `npm audit` made blocking again.
- Heavy touch across frontend layout/ui components, integration tests, and the authorization condition modules.

*311 files changed · +2,322/-1,908 lines*

---

### Commit 53: 29 July, 2026

`50a04d5`: "Added and integrated resend-verification email flow with taskiq logging, fixed dev-up scripts"

- A resend-verification email flow added and integrated for users who tried to verify their account after the link had expired: a new `VerificationEmailRequestForm.tsx` (82 lines) and `useVerificationEmailRequestMutation.ts` (21 lines) on the frontend, matching backend changes to `account_verification_handler.py`/`service.py` and `verify_account_schema.py`.
- The background email worker got terminal-visible logging (`logging_config.py` +49 lines).
- A PowerShell `dev-up` bug fixed (plus a new `dev-up.cmd`) so the startup logs it always promised actually showed up.

*39 files changed · +637/-93 lines*

---

See [August 2026](2026-aug.md) for the rest, [2025](2025-sep-oct.md) for the year
before, or [How It Evolved](README.md) for the milestones overview.

---
