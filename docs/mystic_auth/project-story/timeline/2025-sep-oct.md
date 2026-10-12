# How It Evolved: September-October 2025

---

### Commit 17: 1 September, 2025

`9a88f7c`: "Auth code modularised and corrected ;frontend basic dashboard integrated"

- `auth_routes.py` shrank drastically as its logic moved into dedicated `*_handler.py` files for every flow (`current_user_handler.py` new at 87 lines, plus updated `login_handler.py`, `logout_handler.py`, `logout_all_handler.py`, `oauth2_login_handler.py`, `password_reset_confirm_handler.py`, `password_reset_request_handler.py`, `signup_handler.py`, `account_verification_handler.py`), so routes now just call handlers instead of containing the logic inline.
- On the frontend, `dashboard/DashboardPage.tsx` appeared for the first time (29 lines).

*29 files changed · +1,006/-575 lines*

---

### Commit 18: 2 September, 2025

`ecb9fc0`: "Logout frontend part modified according to updated backend logout logic"

- `LogoutButton.tsx` and `logout_slice.ts` adjusted, `logout_types.ts` trimmed.
- The backend's `password_reset_schema.py` renamed to `password_reset_confirm_schema.py` to match the now-split confirm/request flows.

*10 files changed · +63/-63 lines*

---

### Commit 19: 2 September, 2025

`dedecdd`: "Modularised logout and logout all files along with component files for buttons"

- `LogoutButton.tsx` split into a logic file and a new `LogoutButtonComponent.tsx` for presentation.
- The same pair-of-files pattern applied to a brand-new `logout_all/` folder (`LogoutAllButton.tsx`, `LogoutAllButtonComponent.tsx`, `logout_all_slice.ts`, `logout_all_types.ts`), so logout-all got full frontend support to match the backend endpoint from ten days earlier.

*9 files changed · +359/-121 lines*

---

### Commit 20: 4 September, 2025

`66362cc`: "Token table changed ,files using it modified ;cookie setting modularised"

- `refresh_token_routes.py` shrank sharply (107 lines removed) as its logic moved into a brand-new `auth/refresh_token_logic/` folder (`refresh_token_handler.py`, 98 lines, new; plus `refresh_token_schema.py` and `refresh_token_service.py`), so refresh-token handling now gets the same per-flow treatment every other flow already had.
- `auth/logout_all/` also moved out of `auth/logout/` into its own top-level folder.

*52 files changed · +797/-970 lines*

---

### Commit 21: 4 September, 2025

`da48049`: "Fully commented backend code ;token crud updated, its usage corrected in few files"

- Essentially every backend auth file was touched: `access_control/base_crud.py`, `role_checker.py`, and `token_base_crud.py` grew the most (over 500 combined changed lines), and `jwt_service.py` alone changed by 147 lines.
- The largest commit in this stretch.

*41 files changed · +1,985/-654 lines*

---

### Commit 22: 5 September, 2025

`9487f7a`: "Updated Oauth2 service logic according to token table ;frontend auth slice,api updated"

- `oauth2_service.py` absorbed the bulk of the change (199 of the 227 inserted lines).
- `token_base_crud.py`, `auth_api.ts`, and `login_slice.ts` picked up the rest.

*4 files changed · +227/-180 lines*

---

### Commit 23: 7 September, 2025

`4aeec0e`: "Oauth2 login and logout(single) both work now with updated logic"

- `current_user_handler.py` grew to 89 lines.
- `oauth2_service.py` and `token_cookie_handler.py` were both reworked.
- The frontend's `oauth2_types.ts` was deleted outright (13 lines) as its contents folded into `oauth2_slice.ts`.

*9 files changed · +199/-174 lines*

---

### Commit 24: 13 September, 2025

`a2a4ebd`: "Logout all handler being updated (not done yet) ;backend files commented"

- `refresh_token_service.py` picked up the largest single change (109 lines).
- A new `user_verification_service.py` appeared, splitting verification-specific user updates out of the general account-verification service.
- The commit message itself notes the logout-all work was still in progress.

*37 files changed · +361/-323 lines*

---

### Commit 25: 14 September, 2025

`01c081a`: "Modularised TokenCRUD and UserCRUD fully"

- The old 304-line `access_control/token_base_crud.py` was deleted outright and replaced by a new `token_crud/` package: `token_crud_collector.py` (125 lines) plus `token_crud_modules/` split by token type (`token_access_token_crud.py`, `token_base_crud.py`, `token_email_crud.py`, `token_refresh_token_crud.py`).
- A parallel `user_crud/` package (`user_crud_collector.py`, `user_crud_modules/user_base_crud.py`, `user_email_crud.py`) landed the same way for users.

*15 files changed · +769/-393 lines*

---

### Commit 26: 16 September, 2025

`40ffc31`: "Logout logic files updated ;is_active field becomes false after logout"

- A new method added to `token_refresh_token_crud.py`, called from a trimmed-down `logout_service.py`/`login_service.py` pair.

*4 files changed · +72/-20 lines*

---

### Commit 27: 18 September, 2025

`4fb3511`: "Changed token table field structure and updated code files accordingly"

- The per-role `admin_token_table`, `role1_token_table`, and `role2_token_table` model/schema files all lost fields.
- `logout_handler.py` was simplified.
- The whole `token_refresh_token_crud.py` module added just two days earlier was deleted again (38 lines) as redundant.
- Mostly a cleanup: more lines removed than added.

*9 files changed · +6/-125 lines*

---

### Commit 28: 22 September, 2025

`2804afb`: "Removed token tables to transition to redis-only token management"

- `admin_token_table`, `role1_token_table`, and `role2_token_table` model/schema files all deleted.
- `refresh_token_service.py` and `jwt_service.py` shrank sharply.
- The entire `token_crud/` package added eight days earlier (collector plus `token_access_token_crud.py`) deleted along with it.
- The separate top-level `admin/`, `role1/`, and `role2/` folders consolidated into one `roles/` package (`roles/admin/`, `roles/role1/`, `roles/role2/`) in the same commit.

*32 files changed · +104/-1,073 lines*

---

### Commit 29: 23 September, 2025

`0b9816f`: "Token table logic being replaced by redis only logic with proper comments ;not done yet"

- `jwt_service.py` took the largest single change (241 lines, effectively rewritten for redis-backed sessions).
- The first logging infrastructure appeared: `logging/logging_config.py` and `logging_middleware.py`, new.
- Its own commit message flags the migration as still in progress.

*29 files changed · +839/-852 lines*

---

### Commit 30: 23 September, 2025

`f54f160`: "Oauth2 login works now with updated logic"

- A small follow-up pair (`current_user_handler.py`, `jwt_service.py`) confirming the new redis-only session logic actually holds up specifically for OAuth2-originated logins.

*2 files changed · +44/-42 lines*

---

### Commit 31: 24 September, 2025

`d2fc1d8`: "Logout and Logout all ,both work now with updated token logic"

- `refresh_token_service.py` shrank further (73 lines) as dead code left over from the token-table removal was trimmed, confirming both logout paths against redis-only sessions.

*4 files changed · +37/-73 lines*

---

### Commit 32: 24 September, 2025

`40b343a`: "UserCRUD modified and updated in other files along with signup page in frontend"

- `refresh_token_service.py` grew by 74 lines.
- `account_verification_service.py` was substantially reworked (81 lines).
- On the frontend, `SignupForm.tsx` grew by 119 lines: real signup validation and UX, not just a stub form.

*14 files changed · +342/-212 lines*

---

### Commit 33: 24 September, 2025

`8262388`: "Logging added in backend files"

- A mechanical pass adding a logger call to nearly every backend auth handler/service (login, logout, logout-all, OAuth2, password reset, refresh token, signup, verification, rate limiting, lockout, email tasks), each file touched by a small, uniform ±10-line delta, not a logic change.
- This four-week stretch, from late August through late September, was where the project stopped being "just implementing features" and started being about the underlying security decisions: where tokens should live, how refresh-token reuse detection should work, and what logout-all should actually revoke became architectural decisions, not coding tasks.

*23 files changed · +108/-111 lines*

---

### Commit 34: 6 October, 2025

`6bc7fea`: "Dockerised the app completely ;Tested Oauth2 login and logout successfully"

- A new `docker-compose.yml` (114 lines) coordinated the first `docker/backend.Dockerfile`, `docker/frontend.Dockerfile`, and `docker/nginx/` (Dockerfile + `nginx.conf`), plus a new `.dockerignore`.
- The first time backend, frontend, PostgreSQL, redis, background workers, migrations, and environment configuration were all managed together as one system, instead of pieces run separately.

*14 files changed · +861/-559 lines*

---

### Commit 35: 10 October, 2025

`cdb3012`: "Celery replaced with Taskiq ;Backend ,Docker files modified ;Frontend issues are there"

- `celery_app.py` and `celery/email_tasks.py` (92 lines) deleted outright, replaced by a new `taskiq_tasks/email_tasks.py` (86 lines).
- Celery was considered first because it's widely used, but since the backend was built around async patterns, the worker model created friction. After comparing ARQ, Dramatiq, and Taskiq, Taskiq fit the async-first approach best (ARQ was close, but Taskiq's FastAPI integration was cleaner).
- On the frontend, `App.tsx` grew by 100 lines and `ProtectedRoute.tsx` by 97, and a new `current_user/current_user_slice.ts` (109 lines) appeared.
- The commit's own message admits it left "frontend issues" behind: the swap needed follow-up work, even though the actual requirement (reliably sending verification and password-reset emails) was simple.

*61 files changed · +1,791/-950 lines*

---

### Commit 36: 14 October, 2025

`6bb7b1b`: "Frontend flickering issue resolved ;Signup ,login ,logout ,logout all work now"

- The heaviest rework landed in `login_slice.ts` (207 lines) and `oauth2_slice.ts` (146 lines).
- `App.tsx` (111 lines) and `ProtectedRoute.tsx` (59 lines) both adjusted to fix the render-flicker on auth-state changes.

*13 files changed · +490/-384 lines*


See [August 2025](2025-aug.md) for the start of the year, [2026](2026-feb-jul.md) for what comes
next, or [How It Evolved](README.md) for the milestones overview.

---
