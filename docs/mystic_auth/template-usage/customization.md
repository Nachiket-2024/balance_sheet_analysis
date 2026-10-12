# Building On This Template

---

*Part of [Using This Repository as a Template](overview.md). This page covers extending the frontend and backend, protecting a route with PBAC, and replacing the frontend entirely.*

## Frontend customization

Theme, pages, routing, state, and your own code under `frontend/src/app/`, plus the shared-chrome
extension points (`extraNavItems`, `extraNavbarContent`, the command palette's `extraSearchItems`,
and `AuditLogPage`'s `extraResourceTypes`/`extraActions`) that let your own routes plug into
mystic_auth/-owned UI without editing it directly. See
[Frontend Customization](frontend-customization.md) for the full details.

---

## Backend customization

- **New domain/resource**: a new top-level package under `backend/app/` (sibling to `mystic_auth/`) with its own model/schema/CRUD/router, mounted in `backend/app/main.py`, importing from `backend/app/sdk.py`. See [Backend Architecture](../architecture/backend.md#module-layout) for the shape to follow.
- **Database changes**: an Alembic migration under `backend/alembic/versions/`: no `create_all()`. See [Database Design](../database/design.md#migrations).
- **Configuration**: template settings live in the upstream-owned `backend/mystic_auth/core/settings.py` and are re-exported from `sdk.py` as `settings`; do not add downstream fields there. Put your app's variables in the matching `env/app/.env.dev` or `env/app/.env.<mode>` file and read them from the app-owned `backend/app/core/settings.py` (extend that `BaseSettings` class) or another app-owned settings module under `backend/app/core/`. Compose loads both env-file halves, and `extra="ignore"` on the template settings lets app-only variables coexist without editing MysticAuth. See [Environment Configuration](../environment/README.md#the-mystic_auth--app-split).
- **Authorization condition extensions**: keep a custom handler and validator under `backend/app/` and register them from `backend/app/app_sdk.py` with `register_condition_type()`; do not edit the registry or validator under `backend/mystic_auth/`. See [Adding Condition Handlers](../authorization/adding-condition-handlers.md).
- **Background-task extensions**: keep task modules under `backend/app/`, list them in the app-owned `PROCRASTINATE_TASK_IMPORT_PATHS` setting, and import the queue app and lifecycle APIs from `app.sdk`. See [Background Email Delivery: Downstream task and worker extensions](../background-workers/procrastinate.md#downstream-task-and-worker-extensions).
- **Bootstrap scripts**: app-owned one-time setup scripts may use `policy_repository`, `user_crud`, `database`, and `get_logger` from `app.sdk`; do not import those Mystic Auth implementation modules directly. Keep product-specific policy names and workflow in `backend/app/`.
- **Integration secrets**: keep product-specific providers under `backend/app/` (for example `backend/app/integrations/`), test them under `tests/backend/app/`, and use only `SecretProvider`/`EnvironmentSecretProvider` from `app.sdk`; never edit `backend/mystic_auth/core/secret_provider.py` or put product credentials in JSON settings, migrations, task arguments, or logs. See [Downstream Integration Secrets](../security/integration-secrets.md).

## First-feature tutorial

This small example adds a product-owned `projects` resource without editing
the template internals. Replace the names with your own domain; the locations
and direction of the imports are the important part.

### 1. Create the app-owned folders

```text
backend/app/projects/
  __init__.py
  models.py
  schemas.py
  repository.py
  routes.py
frontend/src/app/projects/
  ProjectsPage.tsx
tests/backend/app/projects/
  test_projects_routes.py
tests/frontend/app/projects/
  ProjectsPage.test.tsx
```

Keep reusable authentication and PBAC implementation in `mystic_auth/`. Your
project imports the stable backend surface from `backend/app/sdk.py` (or
`app.sdk` inside Docker), and the stable frontend surface from
`frontend/src/app/sdk.ts`.

### 2. Add app-owned configuration, if needed

Add a field to `backend/app/core/settings.py`, not to
`backend/mystic_auth/core/settings.py`:

```python
class AppSettings(BaseSettings):
    PROJECTS_PAGE_SIZE: int = 50
```

Add the value only to the matching app env files, for example
`env/app/.env.dev` and `env/app/.env.prod`. The template env files are not the
place for product-specific settings. In code, import `app_settings` from
`backend.app.core.settings` in native tests and `app.core.settings` in the
container, or expose the value through your own app module.

### 3. Protect the route through PBAC

```python
from fastapi import APIRouter, Depends
from app.sdk import Permission, database, require_authorization

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("")
async def list_projects(
    current_user=Depends(require_authorization("projects:read", "projects")),
    db=Depends(database.get_session),
):
    return await project_repository.list_for_user(db, current_user["email"])
```

Register the router in the shared `backend/app/main.py` entry point. Add an
app-owned migration under `backend/alembic/versions/` for tables and an
app-owned seed/policy path for the first `projects:read` grant. Do not add the
action to the template permission catalog unless it becomes reusable
MysticAuth behavior.

### 4. Add the frontend route through the app shell

Import `ProtectedRoute`, `useCan`/`useAuthorization`, and shared UI from
`frontend/src/app/sdk.ts`. Add the page and route in the shared
`frontend/src/app/App.tsx`; add an app-owned navigation item through the
documented extension point where possible. The frontend may hide a control,
but the backend authorization dependency remains authoritative.

### 5. Test the complete boundary

Add route tests under `tests/backend/app/` and UI tests under
`tests/frontend/app/`. Cover an allowed request, a denied request, an
unassigned user, and the app setting's default/override behavior. Before
opening a PR, run the backend unit suite, frontend tests, `ruff`, `mypy`, and
the split/path checks listed in the [command cheat sheet](cheatsheet.md).

### 6. Add deployment overrides only when necessary

If the feature needs a service or volume, add it in
`docker/app/compose/docker-compose.<mode>.yml`; do not copy and edit the
whole MysticAuth Compose file. If it needs a script, add it under
`scripts/app/`. Start the stack with both Compose files and both env files, in
this order:

```bash
docker compose \
  -f docker/mystic_auth/compose/docker-compose.dev.yml \
  -f docker/app/compose/docker-compose.dev.yml \
  --env-file env/mystic_auth/.env.dev \
  --env-file env/app/.env.dev \
  up -d --build
```

This is the repeatable downstream workflow: app code and configuration stay in
the app tree, while MysticAuth remains replaceable by a future upstream sync.

---

## PBAC usage

Protecting a route always goes through `require_authorization(action, resource_type)`: never a role check:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.sdk import require_authorization, Permission, database

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("/")
async def list_all_projects(
    current_user: dict = Depends(require_authorization("projects:list_all", "projects")),
    db: AsyncSession = Depends(database.get_session)
):
    return await project_crud.get_all(db)
```

`resource_type`/`action` don't need to be `Permission` enum values: any non-empty string works, granted via a policy (see [Writing and Testing Policies](../authorization/writing-testing-policies.md#policy-creation-workflow)). Custom actions remain app-owned and do not need to be added to `mystic_auth/` or its catalog. The backend grant guard still applies to every action, including custom ones, so the first bootstrap grant must come from an app-owned migration/seed path; later policy creation, editing, assignment, and direct grants require the caller to already hold the actions involved. Build any custom action catalog or access picker under `backend/app/` and `frontend/src/app/`.

### Custom actions, from definition to assignment

Use this sequence when adding an application permission such as `projects:archive`.

1. Define the action in an app-owned module, for example `backend/app/access/permissions.py`. Keep the name stable and use a clear format such as `projects:archive`. If the frontend displays or selects it, define the matching value under `frontend/src/app/` too. Do not add it to `backend/mystic_auth/authorization/permissions.py` unless it is actually a MysticAuth feature.
2. Protect the application route with the same action and resource type:

   ```python
   Depends(require_authorization("projects:archive", "projects"))
   ```

   The resource type must match the policy resource type. A policy that grants `projects:archive` on `projects` does not grant it on `documents`.
3. Create the first policy through an app-owned migration or a trusted system operator. A migration is best for a repeatable deployment. A holder of the protected `system_superuser` policy may also create the first custom policy or direct grant. A caller with only `policies:create`, `policies:assign`, or `permissions:grant` cannot invent and grant an unheld custom action.
4. Assign the policy or direct grant to the first policy holder who needs it. The same backend guard applies to custom actions as to built-in actions. A caller can later create, edit, assign, or revoke a custom action only when that caller already holds the action.
5. Give non-technical policy users an app-owned screen with named permissions and explanations. MysticAuth's built-in permission catalog contains MysticAuth actions only. It does not know the names, descriptions, or business meaning of application actions. The app screen should hide actions the caller cannot grant and explain disabled actions when they are visible.

For a simple deployment, the migration can create a policy named `project_archiver` with `actions=["projects:archive"]` and `resource_type="projects"`, then assign it to the intended policy holder. For a deployment where policy users manage access themselves, seed the action and initial policy first, then let the protected system policy holder use the app's access screen for later assignments. Never ask a non-technical policy user to type raw action strings.

If a custom grant returns `403`, check three things in order: the caller holds the policy-management action needed for the endpoint, the caller already holds the exact custom action, and the policy uses the exact resource type checked by the route. The exception is the protected system policy holder, which is the intended bootstrap path.

See [Worked Example: Adding a New Domain, End to End](worked-example.md) for all of the above: model, schema, router, migration, policy, frontend page, route, and nav link, wired together for one fake domain as a copy-and-rename starting point for your first feature.

Don't need PBAC's full generality (conditions or per-resource scoping)? Use unconditioned policies with the same action/resource vocabulary; there is no separate access mechanism to learn.

---

## Replacing the frontend entirely

The backend is a stateless JSON API with no frontend-specific coupling: deleting `frontend/` and building a different client against it is supported. It expects cookie-based JWT auth (`access_token` + `refresh_token`, both httpOnly/secure/`SameSite=Strict`) from an origin matching `FRONTEND_BASE_URL`. Full route contract: [API Reference](../api/reference.md).

---

See [Using This Repository as a Template](overview.md) for the rest: quickstart, environment configuration, the ownership split, deployment, and staying in sync with upstream.

---
